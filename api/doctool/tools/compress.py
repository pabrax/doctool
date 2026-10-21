import io
from typing import Literal

import pikepdf
from pikepdf import Name
from PIL import Image
from pydantic import BaseModel

from doctool.tools.base import Tool, ToolInput, ToolOutput, open_pdf, registry, save_pdf
from doctool.tools.imageutil import MAX_PIXELS

# level -> (jpeg quality, max pixels on the long side); None = lossless structural pass only
LEVELS: dict[str, tuple[int, int] | None] = {
    "low": None,
    "recommended": (75, 2000),
    "extreme": (45, 1200),
}


class CompressParams(BaseModel):
    level: Literal["low", "recommended", "extreme"] = "recommended"


class CompressTool(Tool):
    id = "compress"
    title = "Compress PDF"
    group = "optimize"
    description = "Reduce file size: lossless cleanup, optionally recompressing images."
    Params = CompressParams

    def run(self, inputs: list[ToolInput], params: CompressParams) -> list[ToolOutput]:
        item = inputs[0]
        with open_pdf(item.data, item.password) as pdf:
            setting = LEVELS[params.level]
            if setting:
                _recompress_images(pdf, *setting)
            out = save_pdf(
                pdf,
                compress_streams=True,
                recompress_flate=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
            )
        # Never hand back something bigger than what we were given.
        return [ToolOutput(item.name, out if len(out) < len(item.data) else item.data)]


def _recompress_images(pdf: pikepdf.Pdf, quality: int, max_px: int) -> None:
    seen: set[tuple[int, int]] = set()
    for obj in pdf.objects:
        if not isinstance(obj, pikepdf.Stream) or obj.get("/Subtype") != Name.Image:
            continue
        if obj.objgen in seen:
            continue
        seen.add(obj.objgen)
        _recompress_one(obj, quality, max_px)


def _recompress_one(obj: pikepdf.Stream, quality: int, max_px: int) -> None:
    if obj.get("/ImageMask") or "/Mask" in obj or int(obj.get("/BitsPerComponent", 8)) != 8:
        return
    if int(obj.get("/Width", 0)) * int(obj.get("/Height", 0)) > MAX_PIXELS:
        return
    original_size = len(obj.read_raw_bytes())
    try:
        pil = pikepdf.PdfImage(obj).as_pil_image()
        if pil.mode not in ("RGB", "L"):
            return
        if max(pil.size) > max_px:
            ratio = max_px / max(pil.size)
            pil = pil.resize(
                (max(1, round(pil.width * ratio)), max(1, round(pil.height * ratio))),
                Image.Resampling.LANCZOS,
            )
        buf = io.BytesIO()
        pil.save(buf, "JPEG", quality=quality, optimize=True)
    except Exception:  # noqa: BLE001 - exotic encodings (JPX, odd filters) are left untouched
        return
    jpeg = buf.getvalue()
    if len(jpeg) >= original_size:
        return
    obj.write(jpeg, filter=Name.DCTDecode)
    obj.Width, obj.Height = pil.width, pil.height
    obj.BitsPerComponent = 8
    if "/DecodeParms" in obj:
        del obj["/DecodeParms"]


registry.register(CompressTool())
