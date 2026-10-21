from typing import Literal

from pydantic import BaseModel, Field, field_validator

from doctool.tools.base import Tool, ToolInput, ToolOutput, open_pdf, registry, save_pdf
from doctool.tools.overlay import anchor, hex_to_rgb, stamp_page
from doctool.tools.pages import parse_pages


class PageNumberParams(BaseModel):
    position: Literal[
        "top-left", "top-center", "top-right", "bottom-left", "bottom-center", "bottom-right"
    ] = "bottom-center"
    format: str = Field("{n}", max_length=100, description="{n} = number, {total} = page count")
    start: int = Field(1, ge=0, le=100000)
    pages: str = Field("all", description="'all' or ranges such as 2-10")
    skip_first: bool = Field(False, description="leave the cover page unnumbered")
    font: Literal["Helvetica", "Times-Roman", "Courier"] = "Helvetica"
    font_size: int = Field(11, ge=6, le=72)
    color: str = Field("#000000", pattern=r"^#[0-9a-fA-F]{6}$")
    margin: int = Field(24, ge=0, le=200)

    @field_validator("format")
    @classmethod
    def _needs_n(cls, value: str) -> str:
        if "{n}" not in value:
            raise ValueError("format must contain {n}")
        try:
            value.encode("cp1252")
        except UnicodeEncodeError as exc:
            raise ValueError("format supports Latin characters only") from exc
        return value


class PageNumberTool(Tool):
    id = "pagenumber"
    title = "Add page numbers"
    group = "edit"
    description = "Number the pages with a custom format, start value and position."
    Params = PageNumberParams

    def run(self, inputs: list[ToolInput], params: PageNumberParams) -> list[ToolOutput]:
        item = inputs[0]
        rgb = hex_to_rgb(params.color)
        with open_pdf(item.data, item.password) as pdf:
            total = len(pdf.pages)
            selected = parse_pages(params.pages, total)
            if params.skip_first:
                selected = [i for i in selected if i != 0]
            for rank, index in enumerate(selected):
                label = params.format.replace("{n}", str(params.start + rank)).replace(
                    "{total}", str(total)
                )
                stamp_page(pdf.pages[index], self._drawer(params, rgb, label))
            return [ToolOutput(item.name, save_pdf(pdf))]

    @staticmethod
    def _drawer(params: PageNumberParams, rgb, label: str):
        def draw(c, vw, vh):
            c.setFillColorRGB(*rgb)
            c.setFont(params.font, params.font_size)
            x, y = anchor(params.position, vw, vh, params.margin)
            if params.position.startswith("top"):
                y -= params.font_size
            if params.position.endswith("left"):
                c.drawString(x, y, label)
            elif params.position.endswith("right"):
                c.drawRightString(x, y, label)
            else:
                c.drawCentredString(x, y, label)

        return draw


registry.register(PageNumberTool())
