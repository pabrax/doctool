import io

from PIL import Image, UnidentifiedImageError

MAX_PIXELS = 100_000_000  # decompression-bomb guard for any image we decode


def verify_image(data: bytes) -> None:
    """Raise ValueError unless `data` is a decodable raster image of sane size."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.width * img.height > MAX_PIXELS:
                raise ValueError("image is too large")
            img.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("not a supported image") from exc
