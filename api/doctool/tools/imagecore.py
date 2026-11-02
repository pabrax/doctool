"""Shared, Pillow-only image helpers: safe load, mode handling, encode, naming."""

import io
import re
from pathlib import PurePath

from PIL import Image, ImageOps, UnidentifiedImageError, features

from doctool.tools import imageutil
from doctool.tools.base import ToolError, ToolInput
from doctool.tools.imageutil import InputError, open_image, verify_image

_CHECKS = {"png": "zlib", "jpeg": "jpg", "webp": "webp", "avif": "avif"}
_PIL_NAMES = {"png": "PNG", "jpeg": "JPEG", "webp": "WEBP", "avif": "AVIF"}
_EXTENSIONS = {"png": "png", "jpeg": "jpg", "webp": "webp", "avif": "avif"}
_ALPHA_FORMATS = {"png", "webp", "avif"}
_MAX_SIDE = {"webp": (16383, "WebP"), "jpeg": (65500, "JPEG")}


def available_formats() -> list[str]:
    """Output formats this install can encode; AVIF only when Pillow reports support."""
    return [fmt for fmt, feature in _CHECKS.items() if features.check(feature)]


def check_image(data: bytes) -> None:
    """Upload check for the image tools: decodable, allowed format, under the per-image cap."""
    verify_image(data, imageutil.IMAGE_MAX_PIXELS)


def preflight(inputs: list[ToolInput]) -> None:
    """Enforce the pixel caps from the headers alone, before anything is decoded."""
    total = 0
    for item in inputs:
        try:
            with open_image(item.data) as img:
                pixels = img.width * img.height
        except Image.DecompressionBombError as exc:
            raise ToolError(
                "too_large", f"image '{item.name}' is too large", file=item.name
            ) from exc
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError, EOFError) as exc:
            raise ToolError(
                "damaged", f"cannot read image '{item.name}'", file=item.name
            ) from exc
        if pixels > imageutil.IMAGE_MAX_PIXELS:
            raise ToolError(
                "too_large",
                f"image '{item.name}' is too large ({pixels / 1e6:.0f} megapixels, "
                f"the limit is {imageutil.IMAGE_MAX_PIXELS / 1e6:.0f})",
                file=item.name,
            )
        total += pixels
        if total > imageutil.IMAGE_TASK_MAX_PIXELS:
            raise ToolError(
                "too_large",
                f"the pictures are too big to process together; '{item.name}' goes over "
                f"the limit of {imageutil.IMAGE_TASK_MAX_PIXELS / 1e6:.0f} megapixels in total",
                file=item.name,
            )


def load_image(data: bytes, name: str) -> Image.Image:
    """Decode fully, reject animation, apply EXIF orientation. Raises ToolError."""
    try:
        verify_image(data, imageutil.IMAGE_MAX_PIXELS)
    except InputError as exc:  # keep the documented state (too_large, not_image, damaged)
        raise ToolError(exc.state, f"cannot read image '{name}': {exc}", file=name) from exc
    except ValueError as exc:
        raise ToolError("damaged", f"cannot read image '{name}': {exc}", file=name) from exc
    try:
        with open_image(data) as img:
            if img.width * img.height > imageutil.IMAGE_MAX_PIXELS:
                raise ToolError("too_large", f"image '{name}' is too large", file=name)
            if getattr(img, "n_frames", 1) > 1:
                raise ToolError(
                    "unsupported", f"'{name}' is animated; animated images are not supported yet",
                    file=name,
                )
            img.load()
            return ImageOps.exif_transpose(img)
    except ToolError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, EOFError,
            Image.DecompressionBombError) as exc:
        raise ToolError("damaged", f"cannot read image '{name}'", file=name) from exc


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
    file: str | None = None,
) -> bytes:
    limit = _MAX_SIDE.get(fmt)
    if limit and max(img.size) > limit[0]:
        raise ToolError(
            "unsupported", f"{limit[1]} images can be at most {limit[0]} px on each side",
            file=file,
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
        raise ToolError("unsupported", f"unsupported output format '{fmt}'", file=file)
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
        raise ToolError("damaged", f"cannot encode image as {fmt}", file=file) from exc
    return buf.getvalue()


def output_name(name: str, fmt: str) -> str:
    """Stem of `name` (no path parts, safe characters) plus the extension for `fmt`."""
    stem = PurePath(name.replace("\\", "/")).stem
    stem = re.sub(r"[^\w.\- ]", "_", stem).strip(" .") or "image"
    return f"{stem[:100]}.{_EXTENSIONS[fmt]}"
