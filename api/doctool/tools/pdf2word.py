import io
from typing import Literal

from docx import Document
from docx.shared import Emu, Pt
from pydantic import BaseModel, Field

from doctool import pdfextract
from doctool.config import Settings
from doctool.tools.base import Tool, ToolError, ToolInput, ToolOutput, registry
from doctool.tools.officebase import LibreOfficeMixin, output_name

_EMU_PER_PT = 12700
_MARGIN_PT = 54  # 0.75 in


class Pdf2WordParams(BaseModel):
    fidelity: Literal["editable", "keep_look"] = Field(
        "editable",
        description=(
            "Editable text flows like a normal Word document. Keep the look follows the page "
            "more closely but is harder to edit (needs LibreOffice)."
        ),
    )
    include_images: bool = Field(
        True, description="Pictures that can be extracted are placed in the document."
    )


def no_text_warning(missing: list[int]) -> list[dict]:
    """Pages (1-based) that are pictures only: suggest OCR when the tool exists."""
    if not missing:
        return []
    warning: dict = {"code": "no_text_layer", "params": {"pages": pdfextract.page_list(missing)}}
    if registry.get("ocr"):
        warning["action"] = {"tool": "ocr"}
    return [warning]


def check_pages(total: int) -> None:
    cap = Settings.from_env().office_max_pdf_pages
    if total > cap:
        raise ToolError("too_large", f"the PDF has {total} pages; the limit is {cap}")


class Pdf2WordTool(LibreOfficeMixin, Tool):
    id = "pdf2word"
    title = "PDF to Word"
    group = "office"
    description = "Make an editable Word copy of a PDF."
    Params = Pdf2WordParams

    def run(self, inputs: list[ToolInput], params: Pdf2WordParams) -> list[ToolOutput]:
        item = inputs[0]
        data = pdfextract.decrypt(item.data, item.password)
        total = pdfextract.page_count(data)
        check_pages(total)
        name = output_name(item.name, "docx")
        if params.fidelity == "keep_look":
            with self.lo_session() as convert:
                docx = convert(data, "pdf", "docx:MS Word 2007 XML", infilter="writer_pdf_import")
            return [ToolOutput(name, docx)]
        pages = pdfextract.extract(data, list(range(total)), images=params.include_images)
        missing = [p.index + 1 for p in pages if not p.has_text]
        if len(missing) == total:
            raise ToolError("no_text", "the PDF has no text: it looks scanned. Use OCR first.")
        return [ToolOutput(name, build_docx(pages), warnings=no_text_warning(missing))]


def build_docx(pages: list[pdfextract.PageContent]) -> bytes:
    doc = Document()
    section = doc.sections[0]
    first = pages[0]
    section.page_width = Emu(int(first.width * _EMU_PER_PT))
    section.page_height = Emu(int(first.height * _EMU_PER_PT))
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, side, Pt(_MARGIN_PT))
    text_width = int((first.width - 2 * _MARGIN_PT) * _EMU_PER_PT)
    for n, page in enumerate(pages):
        if n:
            doc.add_page_break()
        for block in page.blocks:
            if block.kind == "heading":
                doc.add_heading(block.text, level=block.level)
            elif block.kind == "para":
                doc.add_paragraph(block.text)
            elif block.kind == "table":
                cols = max(len(r) for r in block.rows)
                table = doc.add_table(rows=len(block.rows), cols=cols)
                table.style = "Table Grid"
                for r, row in enumerate(block.rows):
                    for c, value in enumerate(row):
                        table.cell(r, c).text = value
            elif block.kind == "image":
                width = min(int(block.width * _EMU_PER_PT), text_width)
                doc.add_picture(io.BytesIO(block.png), width=Emu(width))
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


registry.register(Pdf2WordTool())
