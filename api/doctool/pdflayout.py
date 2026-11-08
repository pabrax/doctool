"""PDF post-processing for converted documents: page size fitting, n-up handouts, font facts."""

from __future__ import annotations

import io
import math
import re

import pikepdf
from pikepdf import Rectangle

SIZES = {"a4": (595.276, 841.89), "letter": (612.0, 792.0)}
# handout layout: slides per page -> (columns, rows)
GRIDS = {2: (1, 2), 3: (1, 3), 4: (2, 2), 6: (2, 3), 9: (3, 3)}
_MARGIN = 36.0
_GAP = 14.0


def _norm(name: str) -> str:
    """'ABCDEF+Arial-BoldMT' -> 'arial'; 'Calibri Light' -> 'calibrilight'."""
    name = name.lstrip("/").split("+", 1)[-1]
    name = re.sub(r"(PSMT|MT|PS)$", "", name.split("-")[0].split(",")[0])
    return re.sub(r"[^a-z0-9]", "", name.lower())


def pdf_fonts(data: bytes) -> set[str]:
    found: set[str] = set()
    with pikepdf.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            fonts = page.Resources.get("/Font") if "/Resources" in page else None
            for _, font in (fonts or {}).items():
                if base := font.get("/BaseFont"):
                    found.add(str(base))
    return found


def substituted_fonts(used: set[str], in_pdf: set[str]) -> list[str]:
    """Fonts the document asks for that do not appear in the PDF (LibreOffice used another).
    Style variants are matched loosely: 'Calibri Light' matches 'Calibri-Light'."""
    have = {_norm(f) for f in in_pdf}
    full = {re.sub(r"[^a-z0-9]", "", f.lstrip("/").split("+", 1)[-1].lower()) for f in in_pdf}
    missing = []
    for font in sorted(used):
        key = re.sub(r"[^a-z0-9]", "", font.lower())
        if key and key not in have and key not in full and not any(k.startswith(key) for k in full):
            missing.append(font)
    return missing


def _size(page: pikepdf.Page) -> tuple[float, float]:
    mb = page.mediabox
    return float(mb[2]) - float(mb[0]), float(mb[3]) - float(mb[1])


def _place(
    dst: pikepdf.Page, src: pikepdf.Page, box: Rectangle, frame: bool = False
) -> None:
    """Draw `src` centred in `box`, keeping its proportions; optionally with a thin frame."""
    pw, ph = _size(src)
    scale = min(box.width / pw, box.height / ph)
    w, h = pw * scale, ph * scale
    x = box.llx + (box.width - w) / 2
    y = box.lly + (box.height - h) / 2
    dst.add_overlay(src, Rectangle(x, y, x + w, y + h))
    if frame:
        ops = f"q 0.6 G 0.5 w {x:.2f} {y:.2f} {w:.2f} {h:.2f} re S Q".encode()
        dst.contents_add(ops, prepend=False)


def fit_to_size(data: bytes, size: str) -> bytes:
    """Scale every page into an A4/Letter page (same orientation as the source page)."""
    w, h = SIZES[size]
    with pikepdf.open(io.BytesIO(data)) as src, pikepdf.new() as out:
        for page in src.pages:
            pw, ph = _size(page)
            tw, th = (h, w) if pw > ph else (w, h)
            new = out.add_blank_page(page_size=(tw, th))
            _place(new, page, Rectangle(0, 0, tw, th))
        buf = io.BytesIO()
        out.save(buf)
        return buf.getvalue()


def nup(data: bytes, per_page: int, size: str = "a4") -> bytes:
    """Handouts: `per_page` slides on each portrait page, left-to-right, top-to-bottom."""
    cols, rows = GRIDS[per_page]
    w, h = SIZES[size]
    cell_w = (w - 2 * _MARGIN - (cols - 1) * _GAP) / cols
    cell_h = (h - 2 * _MARGIN - (rows - 1) * _GAP) / rows
    with pikepdf.open(io.BytesIO(data)) as src, pikepdf.new() as out:
        pages = list(src.pages)
        for sheet in range(math.ceil(len(pages) / per_page)):
            dst = out.add_blank_page(page_size=(w, h))
            for slot, page in enumerate(pages[sheet * per_page : (sheet + 1) * per_page]):
                c, r = slot % cols, slot // cols
                x0 = _MARGIN + c * (cell_w + _GAP)
                y1 = h - _MARGIN - r * (cell_h + _GAP)
                _place(dst, page, Rectangle(x0, y1 - cell_h, x0 + cell_w, y1), frame=True)
        buf = io.BytesIO()
        out.save(buf)
        return buf.getvalue()
