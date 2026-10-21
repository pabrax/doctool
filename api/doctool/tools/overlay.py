"""Draw overlays (watermarks, page numbers) with reportlab and merge them with pikepdf.

Overlays are drawn in the *visual* frame of the page (what the reader sees), so stamps land in the
right place even when the page carries a /Rotate entry (qpdf compensates the rotation).
"""

import io
from collections.abc import Callable

import pikepdf
from reportlab.pdfgen.canvas import Canvas

Draw = Callable[[Canvas, float, float], None]  # (canvas, visual_width, visual_height)

POSITIONS_9 = (
    "top-left",
    "top-center",
    "top-right",
    "middle-left",
    "center",
    "middle-right",
    "bottom-left",
    "bottom-center",
    "bottom-right",
)


def hex_to_rgb(color: str) -> tuple[float, float, float]:
    return tuple(int(color[i : i + 2], 16) / 255 for i in (1, 3, 5))  # type: ignore[return-value]


def anchor(position: str, vw: float, vh: float, margin: float) -> tuple[float, float]:
    vertical, _, horizontal = position.partition("-")
    if position == "center":
        return vw / 2, vh / 2
    x = {"left": margin, "center": vw / 2, "right": vw - margin}[horizontal]
    y = {"top": vh - margin, "middle": vh / 2, "bottom": margin}[vertical]
    return x, y


def _page_size(page: pikepdf.Page) -> tuple[float, float, int]:
    box = page.mediabox
    w = float(box[2]) - float(box[0])
    h = float(box[3]) - float(box[1])
    return w, h, int(page.obj.get("/Rotate", 0)) % 360


def make_overlay(w: float, h: float, rotate: int, draw: Draw) -> pikepdf.Pdf:
    """qpdf already counter-rotates overlays for /Rotate pages, so draw at the visual size."""
    vw, vh = (h, w) if rotate in (90, 270) else (w, h)
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=(vw, vh))
    draw(c, vw, vh)
    c.showPage()
    c.save()
    return pikepdf.open(io.BytesIO(buf.getvalue()))


def stamp_page(page: pikepdf.Page, draw: Draw, below: bool = False) -> None:
    w, h, rotate = _page_size(page)
    overlay = make_overlay(w, h, rotate, draw)
    page.add_underlay(overlay.pages[0]) if below else page.add_overlay(overlay.pages[0])
