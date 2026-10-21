import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from doctool.db import Document, Task, TaskFile, Version
from doctool.pdfio import inspect_pdf
from doctool.storage import BlobStore

_BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe_filename(name: str, default: str = "document.pdf") -> str:
    """Never used as a path; only as a label and a Content-Disposition name."""
    name = _BAD.sub("_", name.strip().split("/")[-1].split("\\")[-1])[:200].strip(". ")
    return name or default


def add_version(
    db: Session,
    blobs: BlobStore,
    document: Document,
    data: bytes,
    filename: str,
    parent: Version | None = None,
    tool: str | None = None,
    params: dict | None = None,
) -> Version:
    info = inspect_pdf(data)
    sha = blobs.put(data)
    seq = (document.versions[-1].seq + 1) if document.versions else 1
    version = Version(
        document_id=document.id,
        seq=seq,
        parent_version_id=parent.id if parent else None,
        filename=safe_filename(filename),
        sha256=sha,
        size=len(data),
        pages=info.pages,
        encrypted=info.encrypted,
        tool=tool,
        params=params,
    )
    document.versions.append(version)
    db.flush()
    return version


def create_document(db: Session, blobs: BlobStore, data: bytes, filename: str) -> Document:
    filename = safe_filename(filename)
    doc = Document(name=filename, tags=[])
    db.add(doc)
    db.flush()
    add_version(db, blobs, doc, data, filename)
    db.commit()
    return doc


def list_documents(db: Session) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())))


def gc_blob(db: Session, blobs: BlobStore, sha: str | None) -> None:
    """Delete a blob only when no version and no task file references it."""
    if not sha:
        return
    used = db.scalar(select(Version.id).where(Version.sha256 == sha).limit(1)) or db.scalar(
        select(TaskFile.id).where(TaskFile.sha256 == sha).limit(1)
    )
    if not used:
        blobs.delete(sha)


def delete_document(db: Session, blobs: BlobStore, doc: Document) -> None:
    shas = {v.sha256 for v in doc.versions}
    db.delete(doc)
    db.commit()
    for sha in shas:
        gc_blob(db, blobs, sha)


def purge_expired_tasks(db: Session, blobs: BlobStore, ttl_hours: int) -> int:
    """Delete tasks older than the TTL and blobs nothing else references; library is untouched."""
    cutoff = datetime.now(UTC) - timedelta(hours=ttl_hours)
    old = list(db.scalars(select(Task).where(Task.created_at < cutoff)))
    shas = {f.sha256 for t in old for f in t.files}
    for task in old:
        db.delete(task)
    db.commit()
    for sha in shas:
        gc_blob(db, blobs, sha)
    return len(old)
