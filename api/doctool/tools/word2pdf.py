from typing import Literal

from pydantic import BaseModel, Field

from doctool import pdflayout
from doctool.tools.base import ToolInput, ToolOutput, registry
from doctool.tools.officebase import OfficeTool, font_warning, output_name, prepare_package


class Word2PdfParams(BaseModel):
    page_size: Literal["original", "a4", "letter"] = Field(
        "original",
        description=(
            "Keeps the size set in the document. Change it only if the receiver needs A4 or "
            "Letter: pages are scaled to fit."
        ),
    )


class Word2PdfTool(OfficeTool):
    id = "word2pdf"
    title = "Word to PDF"
    group = "office"
    description = "Convert Word, ODT, RTF or text documents to PDF."
    Params = Word2PdfParams
    extensions = ("docx", "doc", "odt", "rtf", "txt")

    def run(self, inputs: list[ToolInput], params: Word2PdfParams) -> list[ToolOutput]:
        item = inputs[0]
        ext = self.source_ext(item.name)
        data, warnings = prepare_package(item.data, ext)
        with self.lo_session() as convert:
            pdf = convert(data, ext, "pdf")
        if params.page_size != "original":
            pdf = pdflayout.fit_to_size(pdf, params.page_size)
        warnings += font_warning(item.data, ext, pdf)
        return [ToolOutput(output_name(item.name, "pdf"), pdf, warnings=warnings)]


registry.register(Word2PdfTool())
