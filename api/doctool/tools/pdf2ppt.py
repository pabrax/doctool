import io
from typing import Literal

from pptx import Presentation
from pptx.util import Emu, Pt
from pydantic import BaseModel, Field

from doctool import pdfextract
from doctool.config import Settings
from doctool.tools.base import Tool, ToolInput, ToolOutput, registry
from doctool.tools.officebase import output_name
from doctool.tools.pdf2word import check_pages

_EMU_PER_PT = 12700
_MIN_EMU, _MAX_EMU = 914_400, 51_206_400  # PowerPoint slide size limits: 1 in .. 56 in
_BLANK_LAYOUT = 6


class Pdf2PptParams(BaseModel):
    slide_content: Literal["picture", "picture_text"] = Field(
        "picture",
        description=(
            "Picture looks exactly like the page but cannot be edited. Picture and text also adds "
            "the page text behind the picture so it can be searched and copied."
        ),
    )
    dpi: int = Field(150, ge=72, le=300, description="Higher is sharper but makes a bigger file.")


def slide_size(width_pt: float, height_pt: float) -> tuple[int, int]:
    """Slide size in EMU with the page's proportions, inside PowerPoint's limits."""
    w, h = width_pt * _EMU_PER_PT, height_pt * _EMU_PER_PT
    scale = min(1.0, _MAX_EMU / max(w, h))
    scale = max(scale, _MIN_EMU / min(w, h)) if min(w, h) * scale < _MIN_EMU else scale
    return int(w * scale), int(h * scale)


class Pdf2PptTool(Tool):
    id = "pdf2ppt"
    title = "PDF to PowerPoint"
    group = "office"
    description = "Make a presentation with one slide per PDF page."
    Params = Pdf2PptParams

    def run(self, inputs: list[ToolInput], params: Pdf2PptParams) -> list[ToolOutput]:
        item = inputs[0]
        data = pdfextract.decrypt(item.data, item.password)
        total = pdfextract.page_count(data)
        check_pages(total)
        budget = Settings.from_env().office_render_budget_pixels
        rendered = pdfextract.render_pages(data, list(range(total)), params.dpi, budget)
        prs = Presentation()
        sw, sh = slide_size(rendered[0][2], rendered[0][3])
        prs.slide_width, prs.slide_height = Emu(sw), Emu(sh)
        for png, text, w, h in rendered:
            slide = prs.slides.add_slide(prs.slide_layouts[_BLANK_LAYOUT])
            scale = min(sw / w, sh / h)
            pw, ph = int(w * scale), int(h * scale)
            left, top = (sw - pw) // 2, (sh - ph) // 2
            if params.slide_content == "picture_text" and text.strip():
                box = slide.shapes.add_textbox(Emu(left), Emu(top), Emu(pw), Emu(ph))
                box.text_frame.word_wrap = True
                box.text_frame.text = text
                for paragraph in box.text_frame.paragraphs:
                    for run in paragraph.runs:
                        run.font.size = Pt(8)
            slide.shapes.add_picture(io.BytesIO(png), Emu(left), Emu(top), Emu(pw), Emu(ph))
        buf = io.BytesIO()
        prs.save(buf)
        return [ToolOutput(output_name(item.name, "pptx"), buf.getvalue())]


registry.register(Pdf2PptTool())
