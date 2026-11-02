from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field, ValidationInfo, field_validator

from doctool.tools import imageutil
from doctool.tools.base import Tool, ToolError, ToolInput, ToolOutput, registry
from doctool.tools.imagecore import (
    check_image,
    encode,
    load_image,
    output_name,
    preflight,
    target_format,
    to_target_mode,
    unique_name,
)
from doctool.tools.imageutil import IMAGE_MAX_FILES

_QUALITY = 90


class ImageResizeParams(BaseModel):
    mode: Literal["fit_box", "exact", "percent"] = Field(
        "fit_box",
        description=(
            "Fit inside a size keeps the proportions; exact size can change them; "
            "percentage scales the whole picture."
        ),
    )
    width: int = Field(
        1920,
        ge=1,
        description="Width in pixels. Pictures are never enlarged, only reduced.",
        json_schema_extra={"show_when": {"mode": ["fit_box", "exact"]}},
    )
    height: int | None = Field(
        None,
        ge=1,
        validate_default=True,
        description=(
            "Height in pixels. Optional when fitting inside a size; required for an exact "
            "size, where the proportions may change."
        ),
        json_schema_extra={"show_when": {"mode": ["fit_box", "exact"]}},
    )
    percent: int = Field(
        50,
        ge=1,
        le=100,
        description="Percentage of the original size.",
        json_schema_extra={"show_when": {"mode": ["percent"]}},
    )

    @field_validator("height")
    @classmethod
    def _exact_needs_height(cls, v: int | None, info: ValidationInfo):
        # Field-level so the 422 `loc` names the missing field.
        if v is None and info.data.get("mode") == "exact":
            raise ValueError("height is required for an exact size")
        return v


class ImageResizeTool(Tool):
    id = "imageresize"
    title = "Resize image"
    group = "images"
    description = "Change the width and height of a picture."
    Params = ImageResizeParams
    min_files = 1
    max_files = IMAGE_MAX_FILES
    accepts = "image"

    def check_input(self, data: bytes) -> None:
        check_image(data)

    def run(self, inputs: list[ToolInput], params: ImageResizeParams) -> list[ToolOutput]:
        preflight(inputs)
        used: set[str] = set()
        outs: list[ToolOutput] = []
        for item in inputs:
            fmt = target_format(item.data)
            img = load_image(item.data, item.name)
            img = to_target_mode(img, fmt)
            icc = img.info.get("icc_profile")
            size = _target_size(img.size, params)
            if size[0] * size[1] > imageutil.IMAGE_MAX_PIXELS:
                raise ToolError("too_large", f"image '{item.name}' is too large", file=item.name)
            if size != img.size:
                img = img.resize(size, Image.Resampling.LANCZOS)
            data = encode(img, fmt, _QUALITY, False, icc, file=item.name)
            outs.append(ToolOutput(unique_name(output_name(item.name, fmt), used), data))
        return outs


def _target_size(src: tuple[int, int], p: ImageResizeParams) -> tuple[int, int]:
    w, h = src
    if p.mode == "percent":
        return max(1, round(w * p.percent / 100)), max(1, round(h * p.percent / 100))
    if p.mode == "exact":
        return min(p.width, w), min(p.height or h, h)
    scale = min(1.0, p.width / w, (p.height / h) if p.height else 1.0)
    return max(1, round(w * scale)), max(1, round(h * scale))




registry.register(ImageResizeTool())
