import io
from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field, model_validator

from doctool.tools.base import Tool, ToolError, ToolInput, ToolOutput, registry
from doctool.tools.imagecore import (
    available_formats,
    encode,
    load_image,
    output_name,
    to_target_mode,
)
from doctool.tools.imageutil import MAX_PIXELS, verify_image

_KEEP = {"JPEG": "jpeg", "MPO": "jpeg", "PNG": "png", "WEBP": "webp", "AVIF": "avif"}
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
        1920, ge=1, description="Width in pixels. Pictures are never enlarged, only reduced."
    )
    height: int | None = Field(
        None,
        ge=1,
        description=(
            "Height in pixels. Optional when fitting inside a size; required for an exact "
            "size, where the proportions may change."
        ),
    )
    percent: int = Field(50, ge=1, le=100, description="Percentage of the original size.")

    @model_validator(mode="after")
    def _exact_needs_height(self):
        if self.mode == "exact" and self.height is None:
            raise ValueError("height is required for an exact size")
        return self


class ImageResizeTool(Tool):
    id = "imageresize"
    title = "Resize image"
    group = "images"
    description = "Change the width and height of a picture."
    Params = ImageResizeParams
    min_files = 1
    max_files = None
    accepts = "image"

    def check_input(self, data: bytes) -> None:
        verify_image(data)

    def run(self, inputs: list[ToolInput], params: ImageResizeParams) -> list[ToolOutput]:
        used: set[str] = set()
        outs: list[ToolOutput] = []
        for item in inputs:
            fmt = _target_format(item.data)
            img = load_image(item.data, item.name)
            icc = img.info.get("icc_profile")
            img = to_target_mode(img, fmt)
            size = _target_size(img.size, params)
            if size[0] * size[1] > MAX_PIXELS:
                raise ToolError("too_large", f"image '{item.name}' is too large")
            if size != img.size:
                img = img.resize(size, Image.Resampling.LANCZOS)
            data = encode(img, fmt, _QUALITY, False, icc)
            outs.append(ToolOutput(_unique(output_name(item.name, fmt), used), data))
        return outs


def _target_size(src: tuple[int, int], p: ImageResizeParams) -> tuple[int, int]:
    w, h = src
    if p.mode == "percent":
        return max(1, round(w * p.percent / 100)), max(1, round(h * p.percent / 100))
    if p.mode == "exact":
        return min(p.width, w), min(p.height or h, h)
    scale = min(1.0, p.width / w, (p.height / h) if p.height else 1.0)
    return max(1, round(w * scale)), max(1, round(h * scale))


def _target_format(data: bytes) -> str:
    """Keep the input format when we can write it, otherwise PNG."""
    with Image.open(io.BytesIO(data)) as probe:
        fmt = _KEEP.get(probe.format or "", "png")
    return fmt if fmt in available_formats() else "png"


def _unique(name: str, used: set[str]) -> str:
    stem, dot, ext = name.rpartition(".")
    candidate, n = name, 1
    while candidate.lower() in used:
        n += 1
        candidate = f"{stem}-{n}{dot}{ext}"
    used.add(candidate.lower())
    return candidate


registry.register(ImageResizeTool())
