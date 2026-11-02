import io
import struct
import zlib

from PIL import Image, UnidentifiedImageError

MAX_PIXELS = 100_000_000  # decompression-bomb guard for any image we decode


class InputError(ValueError):
    """An uploaded image cannot be used; `state` is the documented per-file state."""

    def __init__(self, state: str, message: str):
        super().__init__(message)
        self.state = state


def verify_image(data: bytes) -> None:
    """Raise InputError unless `data` is a decodable raster image of sane size."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.width * img.height > MAX_PIXELS:
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
