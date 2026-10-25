import io
from typing import Literal

import pypdfium2 as pdfium
from pydantic import BaseModel, Field

from doctool.pdfio import PDFIUM_LOCK
from doctool.tools.base import Tool, ToolError, ToolInput, ToolOutput, registry
from doctool.tools.pages import parse_pages, stem

MAX_RENDER_PIXELS = 150_000_000


class PdfImageParams(BaseModel):
    format: Literal["png", "jpg"] = "png"
    dpi: int = Field(150, ge=36, le=600)
    pages: str = Field("all", description="'all' or ranges such as 1-3,5")
    quality: int = Field(85, ge=30, le=100, description="JPEG quality")


class PdfImageTool(Tool):
    id = "pdfimage"
    title = "PDF to images"
    group = "convert"
    description = "Render pages to PNG or JPG."
    Params = PdfImageParams

    def run(self, inputs: list[ToolInput], params: PdfImageParams) -> list[ToolOutput]:
        with PDFIUM_LOCK:
            return self._render(inputs[0], params)

    def _render(self, item: ToolInput, params: PdfImageParams) -> list[ToolOutput]:
        try:
            pdf = pdfium.PdfDocument(item.data, password=item.password)
        except pdfium.PdfiumError as exc:
            if "password" in str(exc).lower():
                raise ToolError("wrong_password", "password required or incorrect", True) from exc
            raise ToolError("damaged", f"cannot open PDF: {exc}") from exc
        try:
            indexes = parse_pages(params.pages, len(pdf))
            scale = params.dpi / 72
            outputs = []
            for i in indexes:
                page = pdf[i]
                w, h = page.get_size()
                if w * h * scale * scale > MAX_RENDER_PIXELS:
                    raise ToolError("too_large", f"page {i + 1} is too large at {params.dpi} dpi")
                image = page.render(scale=scale).to_pil().convert("RGB")
                buf = io.BytesIO()
                if params.format == "jpg":
                    image.save(buf, "JPEG", quality=params.quality, optimize=True)
                else:
                    image.save(buf, "PNG", optimize=True)
                ext = "jpg" if params.format == "jpg" else "png"
                outputs.append(ToolOutput(f"{stem(item.name)}_page{i + 1}.{ext}", buf.getvalue()))
            return outputs
        finally:
            pdf.close()


registry.register(PdfImageTool())
