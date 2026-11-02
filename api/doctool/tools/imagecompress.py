from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field

from doctool.tools.base import Tool, ToolInput, ToolOutput, registry
from doctool.tools.imagecore import (
    check_image,
    encode,
    has_private_metadata,
    load_image,
    output_name,
    preflight,
    target_format,
    to_target_mode,
    unique_name,
)
from doctool.tools.imageutil import IMAGE_MAX_FILES

# preset -> (quality, longest side cap in px)
_PRESETS = {"web": (82, 2560), "email": (72, 1600), "max": (60, 1280)}


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
    max_files = IMAGE_MAX_FILES
    accepts = "image"

    def check_input(self, data: bytes) -> None:
        check_image(data)

    def run(self, inputs: list[ToolInput], params: ImageCompressParams) -> list[ToolOutput]:
        preflight(inputs)
        quality, cap = _PRESETS[params.preset]
        used: set[str] = set()
        outs: list[ToolOutput] = []
        for item in inputs:
            fmt = target_format(item.data)
            img = load_image(item.data, item.name)
            img = to_target_mode(img, fmt)
            icc = img.info.get("icc_profile")
            longest = max(img.size)
            if longest > cap:  # only ever shrink
                scale = cap / longest
                size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
                img = img.resize(size, Image.Resampling.LANCZOS)
            data = encode(img, fmt, quality, False, icc, file=item.name)
            if len(data) >= len(item.data) and not has_private_metadata(item.data):
                # never grow: hand back the original untouched. A file with private metadata
                # (EXIF/GPS, XMP, comments) gets the metadata-free copy even when it is larger.
                outs.append(ToolOutput(unique_name(item.name, used), item.data))
            else:
                outs.append(ToolOutput(unique_name(output_name(item.name, fmt), used), data))
        return outs




registry.register(ImageCompressTool())
