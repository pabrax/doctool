import io

from pydantic import BaseModel

from doctool.tools.base import Tool, ToolInput, ToolOutput, registry
from doctool.tools.imagecore import (
    check_image,
    encode,
    load_image,
    output_name,
    preflight,
    to_target_mode,
)
from doctool.tools.imageutil import IMAGE_MAX_FILES, open_image

_FORMATS = {"JPEG": "jpeg", "PNG": "png", "WEBP": "webp", "AVIF": "avif"}
_QUALITY = {"jpeg": 95, "webp": 95, "avif": 90, "png": 95}


class ImageCleanParams(BaseModel):
    pass


class ImageCleanTool(Tool):
    id = "imageclean"
    title = "Remove photo info"
    group = "images"
    description = "Strips hidden data such as location, camera and date."
    Params = ImageCleanParams
    min_files = 1
    max_files = IMAGE_MAX_FILES
    accepts = "image"

    def check_input(self, data: bytes) -> None:
        check_image(data)

    def run(self, inputs: list[ToolInput], params: ImageCleanParams) -> list[ToolOutput]:
        preflight(inputs)
        used: set[str] = set()
        outs: list[ToolOutput] = []
        for item in inputs:
            img = load_image(item.data, item.name)
            fmt, rotated = _source_info(item.data)
            icc = img.info.get("icc_profile")
            data = _keep_jpeg(item.data, icc) if fmt == "jpeg" and not rotated else None
            if data is None:
                img = to_target_mode(img, fmt)
                img.info.pop("comment", None)  # Pillow would re-write a JPEG comment from info
                data = encode(img, fmt, _QUALITY[fmt], False, icc, file=item.name)
            outs.append(ToolOutput(_unique(output_name(item.name, fmt), used), data))
        return outs


def _source_info(data: bytes) -> tuple[str, bool]:
    """Output format for the source and whether EXIF orientation changes the pixels."""
    with open_image(data) as img:
        return _FORMATS.get(img.format or "", "png"), img.getexif().get(0x0112, 1) != 1


def _keep_jpeg(data: bytes, icc: bytes | None) -> bytes | None:
    """Re-save keeping the original quantization tables; None when Pillow cannot."""
    try:
        with open_image(data) as img:
            img.load()
            kwargs: dict = {"quality": "keep", "optimize": True, "progressive": True,
                            "comment": b""}
            if icc:
                kwargs["icc_profile"] = icc
            buf = io.BytesIO()
            img.save(buf, "JPEG", **kwargs)
            return buf.getvalue()
    except (ValueError, OSError, KeyError):
        return None


def _unique(name: str, used: set[str]) -> str:
    stem, dot, ext = name.rpartition(".")
    candidate, n = name, 1
    while candidate.lower() in used:
        n += 1
        candidate = f"{stem}-{n}{dot}{ext}"
    used.add(candidate.lower())
    return candidate


registry.register(ImageCleanTool())
