import io
from typing import Literal

import img2pdf
from PIL import Image, ImageOps
from pydantic import BaseModel, Field

from doctool.tools.base import Tool, ToolError, ToolInput, ToolOutput, registry
from doctool.tools.imageutil import verify_image
from doctool.tools.pages import stem

PAGE_SIZES_PT = {"A4": (595.2756, 841.8898), "letter": (612.0, 792.0)}


class ImagePdfParams(BaseModel):
    page_size: Literal["fit", "A4", "letter"] = Field("fit", description="fit = page matches image")
    orientation: Literal["auto", "portrait", "landscape"] = "auto"
    margin: int = Field(0, ge=0, le=200, description="points")
    merge: bool = Field(True, description="one PDF with all images (else one PDF per image)")


class ImagePdfTool(Tool):
    id = "imagepdf"
    title = "Images to PDF"
    group = "convert"
    description = "Turn JPG, PNG, WEBP, GIF, BMP or TIFF images into a PDF."
    Params = ImagePdfParams
    min_files = 1
    max_files = None
    accepts = "image"

    def check_input(self, data: bytes) -> None:
        verify_image(data)

    def run(self, inputs: list[ToolInput], params: ImagePdfParams) -> list[ToolOutput]:
        layout = self._layout(params)
        prepared = [(i.name, _normalize(i)) for i in inputs]
        if params.merge:
            pdf = img2pdf.convert([data for _, data in prepared], layout_fun=layout)
            return [ToolOutput("images.pdf", pdf)]
        return [
            ToolOutput(f"{stem(name)}.pdf", img2pdf.convert(data, layout_fun=layout))
            for name, data in prepared
        ]

    @staticmethod
    def _layout(params: ImagePdfParams):
        if params.page_size == "fit":
            return img2pdf.get_layout_fun(None, border=(params.margin, params.margin))
        width, height = PAGE_SIZES_PT[params.page_size]
        if params.orientation == "landscape":
            width, height = height, width
        return img2pdf.get_layout_fun(
            (width, height),
            border=(params.margin, params.margin),
            fit=img2pdf.FitMode.into,
            auto_orient=params.orientation == "auto",
        )


def _normalize(item: ToolInput) -> bytes:
    """Hand img2pdf only what it embeds losslessly: baseline JPEG, or opaque RGB/L PNG."""
    try:
        with Image.open(io.BytesIO(item.data)) as img:
            img.load()
            fmt = img.format
            if fmt == "JPEG" and img.mode in ("RGB", "L") and not _has_exif_rotation(img):
                return item.data
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "LA", "P") and (img.mode != "P" or "transparency" in img.info):
                rgba = img.convert("RGBA")
                flat = Image.new("RGB", rgba.size, "white")
                flat.paste(rgba, mask=rgba.getchannel("A"))
                img = flat
            elif img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, "PNG")
            return buf.getvalue()
    except (OSError, ValueError) as exc:
        raise ToolError("damaged", f"cannot read image '{item.name}'") from exc


def _has_exif_rotation(img: Image.Image) -> bool:
    return img.getexif().get(0x0112, 1) not in (1, None)


registry.register(ImagePdfTool())
