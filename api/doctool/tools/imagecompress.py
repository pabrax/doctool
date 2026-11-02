from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field

from doctool.tools.base import Tool, ToolInput, ToolOutput, registry
from doctool.tools.imagecore import (
    available_formats,
    encode,
    load_image,
    output_name,
    to_target_mode,
)
from doctool.tools.imageutil import open_image, verify_image

# preset -> (quality, longest side cap in px)
_PRESETS = {"web": (82, 2560), "email": (72, 1600), "max": (60, 1280)}
_KEEP = {"JPEG": "jpeg", "MPO": "jpeg", "PNG": "png", "WEBP": "webp", "AVIF": "avif"}


class ImageCompressParams(BaseModel):
    preset: Literal["web", "email", "max"] = Field(
        "web", description="We never return a file bigger than the original."
    )


class ImageCompressTool(Tool):
    id = "imagecompress"
    title = "Compress image"
    group = "images"
    description = "Make photos lighter to share or upload."
    Params = ImageCompressParams
    min_files = 1
    max_files = None
    accepts = "image"

    def check_input(self, data: bytes) -> None:
        verify_image(data)

    def run(self, inputs: list[ToolInput], params: ImageCompressParams) -> list[ToolOutput]:
        quality, cap = _PRESETS[params.preset]
        used: set[str] = set()
        outs: list[ToolOutput] = []
        for item in inputs:
            fmt = _target_format(item.data)
            img = load_image(item.data, item.name)
            icc = img.info.get("icc_profile")
            img = to_target_mode(img, fmt)
            longest = max(img.size)
            if longest > cap:  # only ever shrink
                scale = cap / longest
                size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
                img = img.resize(size, Image.Resampling.LANCZOS)
            data = encode(img, fmt, quality, False, icc)
            if len(data) >= len(item.data):  # never grow: hand back the original untouched
                outs.append(ToolOutput(_unique(item.name, used), item.data))
            else:
                outs.append(ToolOutput(_unique(output_name(item.name, fmt), used), data))
        return outs


def _target_format(data: bytes) -> str:
    """Keep the input format when we can write it, otherwise PNG."""
    with open_image(data) as probe:
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


registry.register(ImageCompressTool())
