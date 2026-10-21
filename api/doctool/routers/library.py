import io

import pikepdf
import pypdfium2 as pdfium
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from doctool import library
from doctool.config import Settings
from doctool.db import Document, Version
from doctool.deps import get_blobs, get_db, get_settings
from doctool.http import content_disposition
from doctool.pdfio import InvalidPdf, read_info
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


def get_version_or_404(db: Session, blobs: BlobStore, version_id: str) -> Version:
    version = db.get(Version, version_id)
    if not version or not blobs.exists(version.sha256):
        raise HTTPException(404, "version not found")
    return version


@router.get("/versions/{version_id}/download")
def download_version(
    version_id: str,
    inline: bool = Query(False, description="show in the browser instead of downloading"),
    db: Session = Depends(get_db),
    blobs: BlobStore = Depends(get_blobs),
):
    version = get_version_or_404(db, blobs, version_id)
    return Response(
        blobs.read(version.sha256),
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition(version.filename, inline)},
    )


@router.get("/versions/{version_id}/thumbnail/{page}")
def version_thumbnail(
    version_id: str,
    page: int,
    width: int = Query(240, ge=32, le=1600),
    db: Session = Depends(get_db),
    blobs: BlobStore = Depends(get_blobs),
):
    version = get_version_or_404(db, blobs, version_id)
    if version.encrypted:
        raise HTTPException(409, "document is encrypted; unlock it first")
    if not version.pages or not 1 <= page <= version.pages:
        raise HTTPException(404, "page not found")
    pdf = pdfium.PdfDocument(blobs.read(version.sha256))
    try:
        pdf_page = pdf[page - 1]
        page_width, _ = pdf_page.get_size()
        image = pdf_page.render(scale=width / page_width).to_pil().convert("RGB")
    finally:
        pdf.close()
    if image.width != width:  # pdfium rounds; make the requested width exact
        image = image.resize((width, max(1, round(image.height * width / image.width))))
    buf = io.BytesIO()
    image.save(buf, "PNG")
    return Response(
        buf.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},  # blobs are immutable
    )


@router.get("/versions/{version_id}/pages")
def version_pages(
    version_id: str, db: Session = Depends(get_db), blobs: BlobStore = Depends(get_blobs)
):
    version = get_version_or_404(db, blobs, version_id)
    if version.encrypted:
        raise HTTPException(409, "document is encrypted; unlock it first")
    with pikepdf.open(io.BytesIO(blobs.read(version.sha256))) as pdf:
        out = []
        for i, page in enumerate(pdf.pages, 1):
            box = page.mediabox
            w, h = float(box[2]) - float(box[0]), float(box[3]) - float(box[1])
            rotate = int(page.obj.get("/Rotate", 0)) % 360
            if rotate in (90, 270):
                w, h = h, w
            out.append({"index": i, "width": w, "height": h, "rotate": rotate})
    return out


@router.get("/versions/{version_id}/metadata")
def version_metadata(
    version_id: str, db: Session = Depends(get_db), blobs: BlobStore = Depends(get_blobs)
):
    version = get_version_or_404(db, blobs, version_id)
    if version.encrypted:
        raise HTTPException(409, "document is encrypted; unlock it first")
    try:
        info = read_info(blobs.read(version.sha256))
    except InvalidPdf as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"pages": version.pages, "size": version.size, "encrypted": False, "info": info}
