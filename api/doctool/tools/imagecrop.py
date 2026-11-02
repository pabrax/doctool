import io
from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field, model_validator

from doctool.tools.base import Tool, ToolError, ToolInput, ToolOutput, registry
from doctool.tools.imagecore import encode, load_image, output_name, to_target_mode
from doctool.tools.imageutil import verify_image

_RATIOS = {"1-1": (1, 1), "4-3": (4, 3), "3-2": (3, 2), "16-9": (16, 9)}
_FORMATS = {"JPEG": "jpeg", "PNG": "png", "WEBP": "webp", "AVIF": "avif"}


class ImageCropParams(BaseModel):
    mode: Literal["ratio", "box"] = Field(
        "ratio", description="crop to a centered aspect ratio or to an exact pixel box"
    )
    ratio: Literal["1-1", "4-3", "3-2", "16-9"] = Field(
        "1-1",
        description="Keeps the biggest area from the center.",
        json_schema_extra={"show_when": {"mode": ["ratio"]}},
    )
    x: int = Field(
        0,
        ge=0,
        description="box mode: distance from the left edge (px)",
        json_schema_extra={"show_when": {"mode": ["box"]}},
    )
    y: int = Field(
        0,
        ge=0,
        description="box mode: distance from the top edge (px)",
        json_schema_extra={"show_when": {"mode": ["box"]}},
    )
    width: int | None = Field(
        None,
        ge=1,
        description="box mode: width of the box (px)",
        json_schema_extra={"show_when": {"mode": ["box"]}},
    )
    height: int | None = Field(
        None,
        ge=1,
        description="box mode: height of the box (px)",
        json_schema_extra={"show_when": {"mode": ["box"]}},
    )

    @model_validator(mode="after")
    def _box_needs_size(self):
        if self.mode == "box" and (self.width is None or self.height is None):
            raise ValueError("width and height are required in box mode")
        return self


class ImageCropTool(Tool):
    id = "imagecrop"
    title = "Crop image"
    group = "images"
    description = "Cut a picture to a shape or a pixel box."
    Params = ImageCropParams
    min_files = 1
    max_files = None
    accepts = "image"

    def check_input(self, data: bytes) -> None:
        verify_image(data)

    def run(self, inputs: list[ToolInput], params: ImageCropParams) -> list[ToolOutput]:
        used: set[str] = set()
        outs: list[ToolOutput] = []
        for item in inputs:
            img = load_image(item.data, item.name)
            fmt = _source_format(item.data)
            icc = img.info.get("icc_profile")
            box = _box_for(img.size, params, item.name)
            img = to_target_mode(img.crop(box), fmt)
            data = encode(img, fmt, 90, False, icc)
            outs.append(ToolOutput(_unique(output_name(item.name, fmt), used), data))
        return outs


def _source_format(data: bytes) -> str:
    with Image.open(io.BytesIO(data)) as img:
        return _FORMATS.get(img.format or "", "png")


def _box_for(size: tuple[int, int], p: ImageCropParams, name: str) -> tuple[int, int, int, int]:
    w, h = size
    if p.mode == "box":
        if p.width is None or p.height is None:
            raise ToolError("out_of_range", "box mode needs both width and height")
        if p.x + p.width > w or p.y + p.height > h:
            raise ToolError(
                "out_of_range",
                f"the box (x={p.x}, y={p.y}, {p.width}x{p.height}) does not fit inside "
                f"'{name}', which is {w}x{h} px",
            )
        return (p.x, p.y, p.x + p.width, p.y + p.height)
    a, b = _RATIOS[p.ratio]
    if h > w:  # portrait sources keep the portrait orientation of the ratio
        a, b = b, a
    if w * b >= h * a:  # image is wider than the ratio: height is the limit
        cw, ch = max(1, h * a // b), h
    else:
        cw, ch = w, max(1, w * b // a)
    left, top = (w - cw) // 2, (h - ch) // 2
    return (left, top, left + cw, top + ch)


def _unique(name: str, used: set[str]) -> str:
    stem, dot, ext = name.rpartition(".")
    candidate, n = name, 1
    while candidate.lower() in used:
        n += 1
        candidate = f"{stem}-{n}{dot}{ext}"
    used.add(candidate.lower())
    return candidate


registry.register(ImageCropTool())
