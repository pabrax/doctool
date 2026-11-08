from typing import Literal

from pydantic import BaseModel, Field

from doctool import ooxml, pdflayout
from doctool.tools.base import ToolInput, ToolOutput, registry
from doctool.tools.officebase import (
    OfficeTool,
    count_warning,
    font_warning,
    output_name,
    pdf_filter,
    prepare_package,
)

_FILTER = "impress_pdf_Export"


class Ppt2PdfParams(BaseModel):
    handout: Literal["slides", "h2", "h3", "h4", "h6", "h9"] = Field(
        "slides",
        description=(
            "One slide per page is the normal PDF. Handouts fit several small slides on each "
            "page for printing."
        ),
    )
    include_notes: bool = Field(
        False,
        description="Adds each slide's notes under it.",
        json_schema_extra={"show_when": {"handout": ["slides"]}},
    )
    include_hidden: bool = Field(
        False, description="Hidden slides are skipped unless you tick this."
    )


class Ppt2PdfTool(OfficeTool):
    id = "ppt2pdf"
    title = "PowerPoint to PDF"
    group = "office"
    description = "Turn presentations into a PDF, as slides or handouts."
    Params = Ppt2PdfParams
    extensions = ("pptx", "ppt", "odp")

    def run(self, inputs: list[ToolInput], params: Ppt2PdfParams) -> list[ToolOutput]:
        item = inputs[0]
        ext = self.source_ext(item.name)
        data, warnings = prepare_package(item.data, ext)
        options: dict = {}
        if params.include_hidden:
            options["ExportHiddenSlides"] = True
        if params.include_notes and params.handout == "slides":
            options.update(ExportNotesPages=True, ExportOnlyNotesPages=True)
        with self.lo_session() as convert:
            pdf = convert(data, ext, pdf_filter(_FILTER, **options))
        if params.handout != "slides":
            pdf = pdflayout.nup(pdf, int(params.handout[1:]))
        if ext == "pptx" and not params.include_hidden:
            warnings += count_warning("hidden_skipped", ooxml.pptx_hidden_slides(item.data))
        warnings += font_warning(item.data, ext, pdf)
        return [ToolOutput(output_name(item.name, "pdf"), pdf, warnings=warnings)]


registry.register(Ppt2PdfTool())
