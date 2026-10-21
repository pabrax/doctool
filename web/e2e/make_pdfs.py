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


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
make(out / "alpha.pdf", 2, "Alpha")
make(out / "beta.pdf", 3, "Beta")
