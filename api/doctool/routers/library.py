from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from doctool import library
from doctool.config import Settings
from doctool.db import Document, Version
from doctool.deps import get_blobs, get_db, get_settings
from doctool.pdfio import InvalidPdf
from doctool.schemas import DocumentOut, DocumentPatch, VersionOut
from doctool.storage import BlobStore

router = APIRouter(prefix="/api/v1", tags=["library"])


def to_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        name=doc.name,
        tags=doc.tags or [],
        created_at=doc.created_at,
        latest_version=VersionOut.model_validate(doc.versions[-1]),
    )


def get_doc_or_404(db: Session, doc_id: str) -> Document:
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "document not found")
    return doc


async def read_upload(file: UploadFile, settings: Settings) -> bytes:
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, "file too large")
    return data


@router.post("/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    blobs: BlobStore = Depends(get_blobs),
    settings: Settings = Depends(get_settings),
):
    data = await read_upload(file, settings)
    try:
        doc = library.create_document(db, blobs, data, file.filename or "document.pdf")
    except InvalidPdf as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    return to_out(doc)


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    return [to_out(d) for d in library.list_documents(db)]


@router.get("/documents/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: str, db: Session = Depends(get_db)):
    return to_out(get_doc_or_404(db, doc_id))


@router.patch("/documents/{doc_id}", response_model=DocumentOut)
def patch_document(doc_id: str, body: DocumentPatch, db: Session = Depends(get_db)):
    doc = get_doc_or_404(db, doc_id)
    if body.name is not None:
        doc.name = library.safe_filename(body.name)
    if body.tags is not None:
        doc.tags = sorted({t.strip() for t in body.tags if t.strip()})
    db.commit()
    return to_out(doc)


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(
    doc_id: str, db: Session = Depends(get_db), blobs: BlobStore = Depends(get_blobs)
):
    library.delete_document(db, blobs, get_doc_or_404(db, doc_id))
    return Response(status_code=204)


@router.get("/documents/{doc_id}/versions", response_model=list[VersionOut])
def list_versions(doc_id: str, db: Session = Depends(get_db)):
    return get_doc_or_404(db, doc_id).versions


@router.get("/versions/{version_id}/download")
def download_version(
    version_id: str, db: Session = Depends(get_db), blobs: BlobStore = Depends(get_blobs)
):
    version = db.get(Version, version_id)
    if not version or not blobs.exists(version.sha256):
        raise HTTPException(404, "version not found")
    return Response(
        blobs.read(version.sha256),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{version.filename}"'},
    )
