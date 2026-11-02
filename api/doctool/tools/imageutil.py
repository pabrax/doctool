import io
import struct
import zlib

from PIL import Image, UnidentifiedImageError

from doctool.config import Settings

MAX_PIXELS = 100_000_000  # decompression-bomb guard for any image we decode
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

# Per-image and per-task caps for the image tools (env-overridable, see config.Settings).
_LIMITS = Settings.from_env()
IMAGE_MAX_PIXELS = _LIMITS.image_max_pixels
IMAGE_TASK_MAX_PIXELS = _LIMITS.image_task_max_pixels
IMAGE_MAX_FILES = _LIMITS.image_max_files

# Pillow opens ~43 formats (EPS shells out to Ghostscript, PSD/ICO/... have a big attack
# surface). Only these are ever decoded; every Image.open in the API goes via open_image().
ALLOWED_FORMATS = ("JPEG", "MPO", "PNG", "WEBP", "AVIF", "GIF", "BMP", "TIFF")


def open_image(data: bytes) -> Image.Image:
    """Image.open restricted to ALLOWED_FORMATS (raises UnidentifiedImageError otherwise)."""
    Image.init()
    # Newer Pillow no longer registers "MPO" (the JPEG plugin returns MPO files itself), and an
    # unregistered id would raise KeyError, so pass only the ids this install knows.
    known = tuple(f for f in ALLOWED_FORMATS if f in Image.OPEN)
    return Image.open(io.BytesIO(data), formats=known)


class InputError(ValueError):
    """An uploaded image cannot be used; `state` is the documented per-file state."""

    def __init__(self, state: str, message: str):
        super().__init__(message)
        self.state = state


def verify_image(data: bytes, max_pixels: int | None = None) -> None:
    """Raise InputError unless `data` is a decodable raster image of sane size."""
    cap = max_pixels or MAX_PIXELS
    try:
        with open_image(data) as img:
            if img.width * img.height > cap:
                raise InputError("too_large", "image is too large")
            img.verify()
    except InputError:
        raise
    except Image.DecompressionBombError as exc:
        raise InputError("too_large", "image is too large") from exc
    except UnidentifiedImageError as exc:
        raise InputError("not_image", "not a supported image") from exc
    except ValueError as exc:
        raise InputError("not_image", "not a supported image") from exc
    except (OSError, SyntaxError, EOFError, zlib.error, struct.error) as exc:
        raise InputError("damaged", "the image is damaged or incomplete") from exc
