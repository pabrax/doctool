from typing import Literal

from pydantic import BaseModel, Field

from doctool.tools.base import Tool, ToolInput, ToolOutput, open_pdf, registry, save_pdf
from doctool.tools.pages import parse_pages


class RotateParams(BaseModel):
    angle: Literal[90, 180, 270] = Field(90, description="clockwise degrees")
    pages: str = Field("all", description="'all' or ranges such as 1-3,5")


class RotateTool(Tool):
    id = "rotate"
    title = "Rotate PDF"
    group = "organize"
    description = "Rotate all or selected pages clockwise."
    Params = RotateParams

    def run(self, inputs: list[ToolInput], params: RotateParams) -> list[ToolOutput]:
        item = inputs[0]
        with open_pdf(item.data, item.password) as pdf:
            for i in parse_pages(params.pages, len(pdf.pages)):
                page = pdf.pages[i]
                current = int(page.obj.get("/Rotate", 0))
                page.obj["/Rotate"] = (current + params.angle) % 360
            return [ToolOutput(item.name, save_pdf(pdf))]


registry.register(RotateTool())
