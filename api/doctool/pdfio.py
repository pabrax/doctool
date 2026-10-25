import io
import threading
from dataclasses import dataclass

import pikepdf

# PDFium is not thread-safe: every pdfium call must hold this lock.
PDFIUM_LOCK = threading.Lock()


class InvalidPdf(ValueError):
    pass


@dataclass(frozen=True)
class PdfInfo:
    pages: int | None
    encrypted: bool


def inspect_pdf(data: bytes) -> PdfInfo:
    """Validate that data is a parseable PDF. Encrypted files are accepted (pages unknown)."""
    if not data.lstrip()[:1024].startswith(b"%PDF-") and b"%PDF-" not in data[:1024]:
        raise InvalidPdf("not a PDF file")
    try:
        with pikepdf.open(io.BytesIO(data)) as pdf:
            return PdfInfo(pages=len(pdf.pages), encrypted=pdf.is_encrypted)
    except pikepdf.PasswordError:
        return PdfInfo(pages=None, encrypted=True)
    except (pikepdf.PdfError, ValueError) as exc:
        raise InvalidPdf(f"damaged PDF: {exc}") from exc


def read_info(data: bytes) -> dict[str, str]:
    """Document-info dictionary as plain strings. Encrypted files raise InvalidPdf."""
    try:
        with pikepdf.open(io.BytesIO(data)) as pdf:
            return {str(k).lstrip("/"): str(v) for k, v in pdf.docinfo.items()}
    except pikepdf.PasswordError as exc:
        raise InvalidPdf("encrypted") from exc
    except (pikepdf.PdfError, ValueError) as exc:
        raise InvalidPdf(f"damaged PDF: {exc}") from exc
