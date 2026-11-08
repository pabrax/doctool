"""Turn PDF pages into structured content (headings, paragraphs, tables, pictures) in reading
order, for the PDF -> Word/Excel/PowerPoint tools. Text and tables come from pdfplumber (pure
Python); pictures are cut from a PDFium rendering, so any image encoding works.

Assumes one text column; multi-column pages keep their text but the order may interleave."""

from __future__ import annotations

import io
import re
import statistics
from dataclasses import dataclass, field

import pdfplumber
import pypdfium2 as pdfium

from doctool import pdfio
from doctool.pdfio import PDFIUM_LOCK
from doctool.tools.base import ToolError, open_pdf, save_pdf

MIN_IMAGE_PT = 24  # smaller pictures are decorations (bullets, rules)
MAX_RENDER_PIXELS = pdfio.MAX_RENDER_PIXELS  # per page (module attribute: tests lower it)
_HEADING_RATIO = 1.3
_TITLE_RATIO = 1.6
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass
class Block:
    kind: str  # heading | para | table | image
    top: float
    text: str = ""
    level: int = 0
    rows: list[list[str]] = field(default_factory=list)
    png: bytes = b""
    width: float = 0.0  # points


@dataclass
class PageContent:
    index: int  # 0-based
    width: float
    height: float
    has_text: bool
    blocks: list[Block] = field(default_factory=list)
    image_boxes: list[tuple[float, float, float, float]] = field(default_factory=list)
    images_skipped: int = 0  # pictures found but not carried (page too large to render)


def clean(text: str) -> str:
    """Remove characters that are not allowed in Office XML."""
    return _CONTROL.sub("", text)


def decrypt(data: bytes, password: str | None) -> bytes:
    """Plain copy of the PDF (raises ToolError wrong_password / damaged)."""
    with open_pdf(data, password) as pdf:
        return save_pdf(pdf, encryption=False) if pdf.is_encrypted else data


def page_count(data: bytes) -> int:
    with pdfplumber.open(io.BytesIO(data)) as pl:
        return len(pl.pages)


def _line_size(line: dict) -> float:
    sizes = [c["size"] for c in line.get("chars", []) if c["text"].strip()]
    return statistics.median(sizes) if sizes else 0.0


def _paragraphs(lines: list[dict], base: float) -> list[Block]:
    out: list[Block] = []
    cur: Block | None = None
    last_bottom = last_size = 0.0
    for line in lines:
        text = clean(line["text"].strip())
        if not text:
            continue
        size = _line_size(line) or base
        if size >= base * _HEADING_RATIO and len(text) <= 120:
            level = 1 if size >= base * _TITLE_RATIO else 2
            out.append(Block("heading", line["top"], text=text, level=level))
            cur = None
        elif cur and line["top"] - last_bottom <= size and abs(size - last_size) < 0.6:
            cur.text = cur.text[:-1] + text if cur.text.endswith("-") else f"{cur.text} {text}"
        else:
            cur = Block("para", line["top"], text=text)
            out.append(cur)
        last_bottom, last_size = line["bottom"], size
    return out


def _inside(obj: dict, boxes: list[tuple]) -> bool:
    return any(
        obj["x0"] >= b[0] - 1
        and obj["x1"] <= b[2] + 1
        and obj["top"] >= b[1] - 1
        and obj["bottom"] <= b[3] + 1
        for b in boxes
    )


def extract(data: bytes, indexes: list[int], *, images: bool, dpi: int = 150) -> list[PageContent]:
    """Structured content of the given pages (0-based), blocks sorted top to bottom."""
    pages: list[PageContent] = []
    with pdfplumber.open(io.BytesIO(data)) as pl:
        for i in indexes:
            page = pl.pages[i]
            pc = PageContent(
                i,
                float(page.width),
                float(page.height),
                has_text=any(c["text"].strip() for c in page.chars),
            )
            tables = page.find_tables()
            boxes = [t.bbox for t in tables]
            for t in tables:
                rows = [[clean((cell or "").strip()) for cell in row] for row in t.extract()]
                rows = [r for r in rows if any(r)]
                if rows:
                    pc.blocks.append(Block("table", t.bbox[1], rows=rows))
            # pdfplumber filters lazily: bind this page's boxes now
            body = page.filter(lambda o, b=boxes: not _inside(o, b)) if boxes else page
            sizes = [c["size"] for c in body.chars if c["text"].strip()]
            if sizes:
                pc.blocks += _paragraphs(
                    body.extract_text_lines(return_chars=True), statistics.median(sizes)
                )
            if images:
                for im in page.images:
                    if (
                        im["x1"] - im["x0"] >= MIN_IMAGE_PT
                        and im["bottom"] - im["top"] >= MIN_IMAGE_PT
                    ):
                        pc.image_boxes.append((im["x0"], im["top"], im["x1"], im["bottom"]))
            pages.append(pc)
    if images:
        _cut_images(data, pages, dpi)
    for pc in pages:
        pc.blocks.sort(key=lambda b: b.top)
    return pages


def _cut_images(data: bytes, pages: list[PageContent], dpi: int) -> None:
    scale = dpi / 72
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(data)
        try:
            for pc in pages:
                if not pc.image_boxes:
                    continue
                if pc.width * pc.height * scale * scale > MAX_RENDER_PIXELS:
                    pc.images_skipped += len(pc.image_boxes)
                    continue
                bitmap = doc[pc.index].render(scale=scale).to_pil().convert("RGB")
                for x0, top, x1, bottom in pc.image_boxes:
                    box = (
                        max(0, int(x0 * scale)),
                        max(0, int(top * scale)),
                        min(bitmap.width, int(x1 * scale)),
                        min(bitmap.height, int(bottom * scale)),
                    )
                    if box[2] - box[0] < 2 or box[3] - box[1] < 2:
                        continue
                    buf = io.BytesIO()
                    bitmap.crop(box).save(buf, "PNG", optimize=True)
                    pc.blocks.append(Block("image", top, png=buf.getvalue(), width=x1 - x0))
        finally:
            doc.close()


def render_pages(
    data: bytes, indexes: list[int], dpi: int, budget: int | None = None
) -> list[tuple[bytes, str, float, float]]:
    """(png, plain text, width pt, height pt) per page, for picture slides.

    `budget` caps the pixels of all pages together (memory and time stay bounded)."""
    scale = dpi / 72
    out = []
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(data)
        try:
            if budget is not None:
                total = sum(doc[i].get_size()[0] * doc[i].get_size()[1] for i in indexes)
                if total * scale * scale > budget:
                    raise ToolError(
                        "too_large", f"too many pages to render at {dpi} dpi; lower the resolution"
                    )
            for i in indexes:
                page = doc[i]
                w, h = page.get_size()
                if w * h * scale * scale > MAX_RENDER_PIXELS:
                    raise ToolError("too_large", f"page {i + 1} is too large at {dpi} dpi")
                buf = io.BytesIO()
                page.render(scale=scale).to_pil().convert("RGB").save(buf, "PNG", optimize=True)
                out.append((buf.getvalue(), clean(page.get_textpage().get_text_range()), w, h))
        finally:
            doc.close()
    return out


def page_list(numbers: list[int]) -> str:
    """[1, 2, 3, 5] -> '1-3, 5' (1-based input)."""
    runs: list[list[int]] = []
    for n in sorted(set(numbers)):
        if runs and n == runs[-1][1] + 1:
            runs[-1][1] = n
        else:
            runs.append([n, n])
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in runs)
