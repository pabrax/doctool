"""Create the PDFs used by the e2e suite: python make_pdfs.py <out_dir>."""

import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def make(path: Path, pages: int, label: str) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    for i in range(1, pages + 1):
        c.setFont("Helvetica", 28)
        c.drawString(72, 750, f"{label} {i}")
        c.showPage()
    c.save()


def make_office(out: Path) -> None:
    """Fixtures for e2e/office.spec.ts (python-docx, openpyxl, python-pptx are api deps)."""
    from docx import Document
    from openpyxl import Workbook
    from pptx import Presentation
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    d = Document()
    d.add_heading("Office e2e", level=1)
    d.add_paragraph("Hello from a Word document.")
    d.save(out / "letter.docx")

    wb = Workbook()
    wb.active.title = "Data"
    wb.active.append(["name", "value"])
    wb.active.append(["uno", 1])
    hidden = wb.create_sheet("Secret")
    hidden["A1"] = "hidden"
    hidden.sheet_state = "hidden"
    wb.save(out / "book.xlsx")

    prs = Presentation()
    for i in range(3):
        prs.slides.add_slide(prs.slide_layouts[5]).shapes.title.text = f"Slide {i + 1}"
    prs.save(out / "deck.pptx")

    (out / "page.html").write_text(
        "<html><body><h1>Invoice</h1><img src='http://example.invalid/logo.png'>"
        "<script>document.write('x')</script><p>Total 42</p></body></html>",
        encoding="utf-8",
    )

    c = canvas.Canvas(str(out / "table.pdf"), pagesize=A4)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(72, 780, "Report")
    c.setFont("Helvetica", 11)
    c.drawString(72, 750, "Totals per region.")
    t = Table([["Region", "Total"], ["North", "42"], ["South", "7"]], colWidths=[120, 80])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.8, colors.black)]))
    t.wrapOn(c, 400, 200)
    t.drawOn(c, 72, 640)
    c.showPage()
    c.save()


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
make(out / "alpha.pdf", 2, "Alpha")
make(out / "beta.pdf", 3, "Beta")
make_office(out)
