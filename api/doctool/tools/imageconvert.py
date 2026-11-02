from typing import Literal

from pydantic import BaseModel, Field

from doctool.tools.base import Tool, ToolInput, ToolOutput, registry
from doctool.tools.imagecore import (
    available_formats,
    encode,
    load_image,
    output_name,
    to_target_mode,
)
from doctool.tools.imageutil import verify_image

# Evaluated once at import: an install without AVIF simply does not offer it.
Target = Literal[tuple(available_formats())]  # type: ignore[valid-type]


class ImageConvertParams(BaseModel):
    target: Target = Field(description="output format")  # type: ignore[valid-type]
    quality: int = Field(85, ge=1, le=100, description="lossy quality (JPEG, WebP, AVIF)")
    background: str = Field(
        "#ffffff",
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="colour that replaces transparency when the target has no alpha",
    )
    keep_metadata: bool = Field(False, description="keep EXIF/GPS data (removed by default)")


class ImageConvertTool(Tool):
    id = "imageconvert"
    title = "Convert images"
    group = "images"
    description = "Convert images between PNG, JPEG, WebP and (when available) AVIF."
    Params = ImageConvertParams
    min_files = 1
    max_files = None
    accepts = "image"

    def check_input(self, data: bytes) -> None:
        verify_image(data)

    def run(self, inputs: list[ToolInput], params: ImageConvertParams) -> list[ToolOutput]:
        fmt = params.target
        used: set[str] = set()
        outs: list[ToolOutput] = []
        for item in inputs:
            img = load_image(item.data, item.name)
            icc = img.info.get("icc_profile")
            img = to_target_mode(img, fmt, params.background)
            data = encode(img, fmt, params.quality, params.keep_metadata, icc)
            outs.append(ToolOutput(_unique(output_name(item.name, fmt), used), data))
        return outs


def _unique(name: str, used: set[str]) -> str:
    stem, dot, ext = name.rpartition(".")
    candidate, n = name, 1
    while candidate.lower() in used:
        n += 1
        candidate = f"{stem}-{n}{dot}{ext}"
    used.add(candidate.lower())
    return candidate


registry.register(ImageConvertTool())
