"""Shared, Pillow-only image helpers: safe load, mode handling, encode, naming."""

import io
import re
from pathlib import PurePath

from PIL import Image, ImageOps, UnidentifiedImageError, features

from doctool.tools.base import ToolError
from doctool.tools.imageutil import MAX_PIXELS, open_image, verify_image

_CHECKS = {"png": "zlib", "jpeg": "jpg", "webp": "webp", "avif": "avif"}
_PIL_NAMES = {"png": "PNG", "jpeg": "JPEG", "webp": "WEBP", "avif": "AVIF"}
_EXTENSIONS = {"png": "png", "jpeg": "jpg", "webp": "webp", "avif": "avif"}
_ALPHA_FORMATS = {"png", "webp", "avif"}
_MAX_SIDE = {"webp": (16383, "WebP"), "jpeg": (65500, "JPEG")}


def available_formats() -> list[str]:
    """Output formats this install can encode; AVIF only when Pillow reports support."""
    return [fmt for fmt, feature in _CHECKS.items() if features.check(feature)]


def load_image(data: bytes, name: str) -> Image.Image:
    """Decode fully, reject animation, apply EXIF orientation. Raises ToolError."""
    try:
        verify_image(data)
    except ValueError as exc:
        raise ToolError("damaged", f"cannot read image '{name}': {exc}") from exc
    try:
        with open_image(data) as img:
            if img.width * img.height > MAX_PIXELS:
                raise ToolError("too_large", f"image '{name}' is too large")
            if getattr(img, "n_frames", 1) > 1:
                raise ToolError("unsupported", "animated images are not supported yet")
            img.load()
            return ImageOps.exif_transpose(img)
    except ToolError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, EOFError,
            Image.DecompressionBombError) as exc:
        raise ToolError("damaged", f"cannot read image '{name}'") from exc


def to_target_mode(img: Image.Image, fmt: str, background: str = "#ffffff") -> Image.Image:
    """Return an image in a mode `fmt` can store, flattening alpha for JPEG."""
    has_alpha = img.mode in ("RGBA", "LA", "PA") or (
        img.mode == "P" and "transparency" in img.info
    )
    if img.mode in ("I;16", "I;16L", "I;16B", "I"):
        img = img.point(lambda v: v / 256, "L") if img.mode == "I" else _from_16bit(img)
        has_alpha = False
    if has_alpha:
        rgba = img.convert("RGBA")
        if fmt in _ALPHA_FORMATS:
            return rgba
        flat = Image.new("RGB", rgba.size, background)
        flat.paste(rgba, mask=rgba.getchannel("A"))
        flat.info.update({k: v for k, v in img.info.items() if k == "icc_profile"})
        return flat
    if img.mode == "L" or (img.mode == "RGB"):
        return img
    return img.convert("RGB")


def _from_16bit(img: Image.Image) -> Image.Image:
    return img.convert("I").point(lambda v: v / 256, "L")


def encode(
    img: Image.Image,
    fmt: str,
    quality: int = 85,
    keep_metadata: bool = False,
    icc_profile: bytes | None = None,
    exif: bytes | None = None,
) -> bytes:
    limit = _MAX_SIDE.get(fmt)
    if limit and max(img.size) > limit[0]:
        raise ToolError(
            "unsupported", f"{limit[1]} images can be at most {limit[0]} px on each side"
        )
    kwargs: dict = {}
    if fmt == "jpeg":
        kwargs.update(quality=quality, optimize=True, progressive=True)
    elif fmt == "webp":
        kwargs.update(quality=quality, method=4)
    elif fmt == "avif":
        kwargs.update(quality=quality, speed=6)
    elif fmt == "png":
        kwargs.update(optimize=True)
    else:
        raise ToolError("unsupported", f"unsupported output format '{fmt}'")
    if icc_profile:
        kwargs["icc_profile"] = icc_profile
    if keep_metadata:
        if exif is None:
            own = img.getexif()
            exif = own.tobytes() if len(own) else None
        if exif:
            kwargs["exif"] = exif
    buf = io.BytesIO()
    try:
        # exif/XMP are only written when passed explicitly, so they are dropped by default
        img.save(buf, _PIL_NAMES[fmt], **kwargs)
    except (OSError, ValueError, KeyError) as exc:
        raise ToolError("damaged", f"cannot encode image as {fmt}") from exc
    return buf.getvalue()


def output_name(name: str, fmt: str) -> str:
    """Stem of `name` (no path parts, safe characters) plus the extension for `fmt`."""
    stem = PurePath(name.replace("\\", "/")).stem
    stem = re.sub(r"[^\w.\- ]", "_", stem).strip(" .") or "image"
    return f"{stem[:100]}.{_EXTENSIONS[fmt]}"
