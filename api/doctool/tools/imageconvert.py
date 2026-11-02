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
_TO_INTERNAL = {"jpg": "jpeg"}
Target = Literal[  # type: ignore[valid-type]
    tuple("jpg" if f == "jpeg" else f for f in available_formats())
]


class ImageConvertParams(BaseModel):
    format: Target = Field(  # type: ignore[valid-type]
        description="JPG works everywhere. WebP is smaller but some old apps cannot open it."
    )
    quality: int = Field(85, ge=1, le=100, description="lossy quality (JPEG, WebP, AVIF)")
    background: str = Field(
        "#ffffff",
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="colour that replaces transparency when the target has no alpha",
    )
    keep_metadata: bool = Field(False, description="keep EXIF/GPS data (removed by default)")


class ImageConvertTool(Tool):
    id = "imageconvert"
    title = "Convert image"
    group = "images"
    description = "Change a picture to JPG, PNG or WebP."
    Params = ImageConvertParams
    min_files = 1
    max_files = None
    accepts = "image"

    def check_input(self, data: bytes) -> None:
        verify_image(data)

    def run(self, inputs: list[ToolInput], params: ImageConvertParams) -> list[ToolOutput]:
        fmt = _TO_INTERNAL.get(params.format, params.format)
        used: set[str] = set()
        outs: list[ToolOutput] = []
        for item in inputs:
            img = load_image(item.data, item.name)
            icc = img.info.get("icc_profile")
            exif = None
            if params.keep_metadata:
                own = img.getexif()
                exif = own.tobytes() if len(own) else None
            img = to_target_mode(img, fmt, params.background)
            data = encode(img, fmt, params.quality, params.keep_metadata, icc, exif)
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
