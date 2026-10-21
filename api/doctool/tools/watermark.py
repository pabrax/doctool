import io
from typing import Literal

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, model_validator
from reportlab.lib.utils import ImageReader

from doctool.pdfio import inspect_pdf
from doctool.tools.base import Tool, ToolError, ToolInput, ToolOutput, open_pdf, registry, save_pdf
from doctool.tools.overlay import POSITIONS_9, anchor, hex_to_rgb, stamp_page
from doctool.tools.pages import parse_pages

Position = Literal[
    "top-left",
    "top-center",
    "top-right",
    "middle-left",
    "center",
    "middle-right",
    "bottom-left",
    "bottom-center",
    "bottom-right",
]
assert set(Position.__args__) == set(POSITIONS_9)  # type: ignore[attr-defined]


class WatermarkParams(BaseModel):
    mode: Literal["text", "image"] = "text"
    text: str = Field("", json_schema_extra={"show_when": {"mode": ["text"]}})
    font: Literal["Helvetica", "Helvetica-Bold", "Times-Roman", "Courier"] = Field(
        "Helvetica-Bold", json_schema_extra={"show_when": {"mode": ["text"]}}
    )
    font_size: int = Field(48, ge=6, le=300, json_schema_extra={"show_when": {"mode": ["text"]}})
    color: str = Field("#808080", pattern=r"^#[0-9a-fA-F]{6}$")
    opacity: float = Field(0.3, gt=0, le=1)
    rotation: int = Field(45, ge=-180, le=180)
    position: Position = "center"
    mosaic: bool = Field(False, description="repeat across the whole page")
    layer: Literal["above", "below"] = "above"
    pages: str = Field("all", description="'all' or ranges such as 1-3,5")
    scale: float = Field(
        0.4,
        gt=0,
        le=1,
        description="image width as a fraction of the page",
        json_schema_extra={"show_when": {"mode": ["image"]}},
    )

    @model_validator(mode="after")
    def _check_text(self):
        if self.mode == "text":
            if not self.text.strip():
                raise ValueError("text is required in text mode")
            try:
                self.text.encode("cp1252")
            except UnicodeEncodeError as exc:
                raise ValueError(
                    "text supports Latin characters only (built-in PDF fonts)"
                ) from exc
        return self


class WatermarkTool(Tool):
    id = "watermark"
    title = "Add watermark"
    group = "edit"
    description = "Stamp text, or an image (second file), over or under the pages."
    Params = WatermarkParams
    min_files = 1
    max_files = 2
    accepts = "pdf+image"

    def check_input(self, data: bytes) -> None:
        if data.lstrip()[:5] == b"%PDF-":
            inspect_pdf(data)
            return
        try:
            Image.open(io.BytesIO(data)).verify()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValueError("not a PDF or a supported image") from exc

    def run(self, inputs: list[ToolInput], params: WatermarkParams) -> list[ToolOutput]:
        pdf_in = next((i for i in inputs if i.data.lstrip()[:5] == b"%PDF-"), None)
        if pdf_in is None:
            raise ToolError("damaged", "no PDF among the inputs")
        image = None
        if params.mode == "image":
            img_in = next((i for i in inputs if i is not pdf_in), None)
            if img_in is None:
                raise ToolError("no_images", "image mode needs an image as the second file")
            try:
                image = Image.open(io.BytesIO(img_in.data)).convert("RGBA")
            except (UnidentifiedImageError, OSError) as exc:
                raise ToolError("no_images", "the second file is not a supported image") from exc
        rgb = hex_to_rgb(params.color)

        def draw(c, vw, vh):
            c.setFillColorRGB(*rgb)
            c.setFillAlpha(params.opacity)
            if image is not None:
                w = vw * params.scale
                h = w * image.height / image.width
                points = _grid(vw, vh, w * 1.3, h * 1.8) if params.mosaic else [_at(params, vw, vh)]
                reader = ImageReader(image)
                for x, y in points:
                    c.saveState()
                    c.translate(x, y)
                    c.rotate(params.rotation)
                    c.drawImage(reader, -w / 2, -h / 2, w, h, mask="auto")
                    c.restoreState()
                return
            c.setFont(params.font, params.font_size)
            tw = c.stringWidth(params.text, params.font, params.font_size)
            if params.mosaic:
                points = _grid(vw, vh, tw * 1.5, params.font_size * 4)
            else:
                points = [_at(params, vw, vh)]
            for x, y in points:
                c.saveState()
                c.translate(x, y)
                c.rotate(params.rotation)
                c.drawCentredString(0, -params.font_size * 0.35, params.text)
                c.restoreState()

        with open_pdf(pdf_in.data, pdf_in.password) as pdf:
            for i in parse_pages(params.pages, len(pdf.pages)):
                stamp_page(pdf.pages[i], draw, below=params.layer == "below")
            return [ToolOutput(pdf_in.name, save_pdf(pdf))]


def _at(params: WatermarkParams, vw: float, vh: float) -> tuple[float, float]:
    margin = params.font_size if params.mode == "text" else vw * 0.05
    return anchor(params.position, vw, vh, margin)


def _grid(vw: float, vh: float, step_x: float, step_y: float) -> list[tuple[float, float]]:
    points = []
    row = 0
    y = step_y / 2
    while y < vh + step_y:
        x = step_x / 2 + (step_x / 2 if row % 2 else 0)
        while x < vw + step_x:
            points.append((x, y))
            x += step_x
        y += step_y
        row += 1
    return points


registry.register(WatermarkTool())
