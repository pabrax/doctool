"""Fixture PDF builders (generated at test time, no binary fixtures in git)."""

import io

import pikepdf
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def make_pdf(pages: int = 3, prefix: str = "Page") -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for i in range(1, pages + 1):
        c.drawString(72, 750, f"{prefix} {i}")
        c.showPage()
    c.save()
    return buf.getvalue()


def page_count(data: bytes) -> int:
    with pikepdf.open(io.BytesIO(data)) as pdf:
        return len(pdf.pages)


def page_text(data: bytes) -> list[str]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    try:
        return [p.get_textpage().get_text_range().strip() for p in pdf]
    finally:
        pdf.close()
