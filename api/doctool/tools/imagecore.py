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
_KEEP = {"JPEG": "jpeg", "MPO": "jpeg", "PNG": "png", "WEBP": "webp", "AVIF": "avif"}
_MAX_SIDE = {"webp": (16383, "WebP"), "jpeg": (65500, "JPEG")}


def available_formats() -> list[str]:
    """Output formats this install can encode; AVIF only when Pillow reports support."""
    return [fmt for fmt, feature in _CHECKS.items() if features.check(feature)]


def unique_name(name: str, used: set[str]) -> str:
    """`name`, or `stem-2.ext`, `stem-3.ext`... when a case-insensitive twin is already used."""
    stem, dot, ext = name.rpartition(".")
    candidate, n = name, 1
    while candidate.lower() in used:
        n += 1
        candidate = f"{stem}-{n}{dot}{ext}"
    used.add(candidate.lower())
    return candidate


def source_format(data: bytes) -> str:
    """Our name for the input's own format (MPO counts as jpeg); png when unknown."""
    with open_image(data) as img:
        return _KEEP.get(img.format or "", "png")


def target_format(data: bytes) -> str:
    """Keep the input format when we can write it, otherwise PNG."""
    fmt = source_format(data)
    return fmt if fmt in available_formats() else "png"


# ALLOWLIST scans of the ORIGINAL bytes: anything not known to be harmless counts as private,
# and a file we cannot parse is private too (the caller then returns the metadata-free copy).
_PNG_OK = {
    b"IHDR", b"PLTE", b"IDAT", b"IEND", b"gAMA", b"cHRM", b"sRGB", b"iCCP", b"pHYs", b"sBIT",
    b"bKGD", b"tRNS", b"cICP", b"cLLI", b"mDCV",
}
_WEBP_OK = {b"VP8 ", b"VP8L", b"VP8X", b"ALPH", b"ANIM", b"ANMF", b"ICCP"}
_AVIF_MARKERS = (b"Exif", b"mime", b"jumb", b"rdf+xml", b"xmp", b"XMP", b"c2pa", b"cabx")


def _jpeg_private(data: bytes) -> bool:
    pos, n = 2, len(data)
    while pos + 2 <= n:
        if data[pos] != 0xFF:
            return True  # malformed or stray bytes: do not trust it
        marker = data[pos + 1]
        if marker == 0xFF:
            pos += 1
            continue
        if marker == 0xD9:  # EOI: nothing may follow
            return pos + 2 != n
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            pos += 2
            continue
        if pos + 4 > n:
            return True
        end = pos + 2 + int.from_bytes(data[pos + 2 : pos + 4], "big")
        if end > n:
            return True
        payload = data[pos + 4 : end]
        if marker == 0xE0:
            if not payload.startswith(b"JFIF"):
                return True
        elif marker == 0xE2:
            if not payload.startswith(b"ICC_PROFILE"):
                return True
        elif 0xE1 <= marker <= 0xEF and marker != 0xEE or marker == 0xFE:
            return True  # APP1..APP15 (except Adobe APP14) and comments
        pos = end
        if marker == 0xDA:  # skip entropy-coded data up to the next real marker
            while True:
                pos = data.find(bytes([0xFF]), pos)
                if pos < 0 or pos + 1 >= n:
                    return True
                nxt = data[pos + 1]
                if nxt == 0 or nxt == 0xFF or 0xD0 <= nxt <= 0xD7:
                    pos += 1 if nxt == 0xFF else 2
                    continue
                break
    return True


def _png_private(data: bytes) -> bool:
    pos, n = 8, len(data)
    while pos + 12 <= n:
        size = int.from_bytes(data[pos : pos + 4], "big")
        kind = data[pos + 4 : pos + 8]
        if kind not in _PNG_OK or pos + 12 + size > n:
            return True
        pos += 12 + size
        if kind == b"IEND":
            return pos != n  # nothing may follow
    return True


def _webp_private(data: bytes) -> bool:
    pos, n = 12, len(data)
    while pos < n:
        if pos + 8 > n or data[pos : pos + 4] not in _WEBP_OK:
            return True
        size = int.from_bytes(data[pos + 4 : pos + 8], "little")
        if pos + 8 + size > n:
            return True
        pos += 8 + size + (size & 1)
    return False


def _avif_private(data: bytes) -> bool:
    pos, n = 0, len(data)
    seen = set()
    while pos < n:
        if pos + 8 > n:
            return True
        size = int.from_bytes(data[pos : pos + 4], "big")
        kind = data[pos + 4 : pos + 8]
        head = 8
        if size == 1:
            size, head = int.from_bytes(data[pos + 8 : pos + 16], "big"), 16
        elif size == 0:
            size = n - pos
        if kind not in (b"ftyp", b"meta", b"mdat") or size < head or pos + size > n:
            return True
        if kind == b"meta" and any(m in data[pos : pos + size] for m in _AVIF_MARKERS):
            return True
        seen.add(kind)
        pos += size
    return not {b"ftyp", b"meta"} <= seen


def has_private_metadata(data: bytes) -> bool:
    """Allowlist scan of the ORIGINAL file: True unless it carries only known-harmless parts.

    True also when the file is not JPEG/PNG/WebP/AVIF (GIF, BMP, TIFF, MPO are re-encoded to
    another format anyway, so their original bytes are never handed back) or cannot be parsed.
    """
    try:
        with open_image(data) as img:
            fmt = img.format
    except Exception:  # unreadable or truncated: private, so the caller sends the clean copy
        return True
    scan = {
        "JPEG": _jpeg_private, "PNG": _png_private, "WEBP": _webp_private, "AVIF": _avif_private,
    }.get(fmt or "")
    if scan is None:
        return True
    try:
        return scan(data)
    except (IndexError, ValueError):
        return True


def check_image(data: bytes) -> None:
    """Upload check for the image tools: decodable, allowed format, under the per-image cap."""
    verify_image(data, imageutil.IMAGE_MAX_PIXELS)


_TASK_CAP = object()


def preflight(
    inputs: list[ToolInput],
    per_image_cap: int | None = None,
    task_cap: "int | None | object" = _TASK_CAP,
) -> None:
    """Enforce the pixel caps from the headers alone, before anything is decoded.

    `task_cap` is the limit on the summed pixels; None switches the task-wide check off.
    """
    cap = per_image_cap or imageutil.IMAGE_MAX_PIXELS
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
        if pixels > cap:
            raise ToolError(
                "too_large",
                f"image '{item.name}' is too large ({pixels / 1e6:.0f} megapixels, "
                f"the limit is {cap / 1e6:.0f})",
                file=item.name,
            )
        total += pixels
        limit = imageutil.IMAGE_TASK_MAX_PIXELS if task_cap is _TASK_CAP else task_cap
        if limit is not None and total > limit:
            raise ToolError(
                "too_large",
                f"the pictures are too big to process together; '{item.name}' goes over "
                f"the limit of {limit / 1e6:.0f} megapixels in total",
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
    converted = img.convert("RGB")
    if img.mode == "CMYK":  # a CMYK profile does not describe the RGB pixels
        converted.info.pop("icc_profile", None)
    return converted


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
        # comment=b"" stops Pillow re-writing a comment it kept in img.info
        kwargs.update(quality=quality, optimize=True, progressive=True, comment=b"")
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
