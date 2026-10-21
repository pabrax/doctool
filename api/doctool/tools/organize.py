from typing import Literal

import pikepdf
from pydantic import BaseModel, Field, model_validator

from doctool.tools.base import Tool, ToolError, ToolInput, ToolOutput, open_pdf, registry, save_pdf
from doctool.tools.pages import stem


class OrganizeParams(BaseModel):
    order: list[int | Literal["blank"]] = Field(
        min_length=1,
        description="Output page sequence: 1-based source pages (repeat = duplicate, omit = "
        "delete) or 'blank' for an empty page.",
    )
    rotations: dict[int, Literal[0, 90, 180, 270]] = Field(
        default_factory=dict,
        description="Extra clockwise rotation per source page number, applied to every copy.",
    )
    rotate: list[Literal[0, 90, 180, 270]] | None = Field(
        None,
        description="Extra clockwise rotation for each entry of `order` (same length), "
        "added to the source page's own rotation.",
    )

    @model_validator(mode="after")
    def _rotate_matches_order(self):
        if self.rotate is not None and len(self.rotate) != len(self.order):
            raise ValueError("rotate must have the same length as order")
        return self


class OrganizeTool(Tool):
    id = "organize"
    title = "Organize pages"
    group = "organize"
    description = "Reorder, delete, duplicate, rotate pages and insert blank pages."
    Params = OrganizeParams

    def run(self, inputs: list[ToolInput], params: OrganizeParams) -> list[ToolOutput]:
        item = inputs[0]
        with open_pdf(item.data, item.password) as src:
            total = len(src.pages)
            for entry in params.order:
                if entry != "blank" and not 1 <= entry <= total:
                    raise ToolError("out_of_range", f"page {entry} is outside 1-{total}")
            for page_no in params.rotations:
                if not 1 <= page_no <= total:
                    raise ToolError("out_of_range", f"rotation page {page_no} is outside 1-{total}")
            with pikepdf.new() as dst:
                first = src.pages[0].mediabox
                size = (float(first[2]) - float(first[0]), float(first[3]) - float(first[1]))
                for i, entry in enumerate(params.order):
                    per_copy = params.rotate[i] if params.rotate else 0
                    if entry == "blank":
                        dst.add_blank_page(page_size=size)
                        if per_copy:
                            dst.pages[-1].obj["/Rotate"] = per_copy % 360
                        continue
                    page = src.pages[entry - 1]
                    dst.pages.append(page)
                    extra = params.rotations.get(entry, 0) + per_copy
                    if extra:
                        new = dst.pages[-1]
                        base = int(page.obj.get("/Rotate", 0))
                        new.obj["/Rotate"] = (base + extra) % 360
                return [ToolOutput(f"{stem(item.name)}_organized.pdf", save_pdf(dst))]


registry.register(OrganizeTool())
