from typing import Literal

from pydantic import BaseModel, Field

from doctool import htmlsafe
from doctool.tools.base import ToolInput, ToolOutput, registry
from doctool.tools.officebase import OfficeTool, count_warning, output_name


class Html2PdfParams(BaseModel):
    page_size: Literal["a4", "letter"] = Field("a4", description="Paper size of the PDF.")
    orientation: Literal["auto", "portrait", "landscape"] = Field(
        "auto", description="Auto keeps portrait unless the page asks for landscape."
    )
    print_backgrounds: bool = Field(True, description="Turn off to save ink when printing.")


class Html2PdfTool(OfficeTool):
    id = "html2pdf"
    title = "HTML to PDF"
    group = "office"
    description = (
        "Print a saved web page (HTML file) as PDF. Nothing is downloaded from the internet."
    )
    Params = Html2PdfParams
    extensions = ("html", "htm")

    def run(self, inputs: list[ToolInput], params: Html2PdfParams) -> list[ToolOutput]:
        item = inputs[0]
        safe, blocked = htmlsafe.sanitize(
            item.data,
            page_size=params.page_size,
            orientation=params.orientation,
            backgrounds=params.print_backgrounds,
        )
        with self.lo_session() as convert:
            pdf = convert(safe, "html", "pdf")
        warnings = count_warning("external_links_blocked", blocked)
        return [ToolOutput(output_name(item.name, "pdf"), pdf, warnings=warnings)]


registry.register(Html2PdfTool())
