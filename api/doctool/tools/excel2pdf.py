import csv
from typing import Literal

from pydantic import BaseModel, Field

from doctool import ooxml
from doctool.tools.base import ToolInput, ToolOutput, registry
from doctool.tools.officebase import (
    OfficeTool,
    count_warning,
    font_warning,
    output_name,
    prepare_package,
)

_XLSX = "xlsx:Calc Office Open XML"
_CSV_SNIFF = 64 * 1024


class Excel2PdfParams(BaseModel):
    sheets: str = Field(
        "",
        max_length=500,
        description=(
            "Sheet names or numbers separated by commas, for example 1,3 or Summary. Leave empty "
            "for all sheets. Hidden sheets are skipped."
        ),
    )
    orientation: Literal["auto", "portrait", "landscape"] = Field(
        "auto", description="Auto picks landscape for wide sheets."
    )
    fit_width: bool = Field(
        True, description="Shrinks wide sheets so no column is cut off to another page."
    )
    fit_sheet: bool = Field(
        False,
        description="Each sheet becomes a single page. Large sheets get very small text.",
    )


def csv_infilter(data: bytes) -> str:
    """LibreOffice CSV import options: detected delimiter, double quote, UTF-8 (76)."""
    sample = data[:_CSV_SNIFF].decode("utf-8", errors="replace")
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delim = ","
    # tokens: separator, quote, UTF-8, first line 1, cell formats, language,
    # quoted as text, detect special numbers, -, -, trim spaces, -, evaluate formulas (off)
    tokens = f"{ord(delim)},34,76,1,,0,false,true,false,false,false,0,false"
    return f"CSV Text - txt - csv (StarCalc):{tokens}"


class Excel2PdfTool(OfficeTool):
    id = "excel2pdf"
    title = "Excel to PDF"
    group = "office"
    description = "Turn spreadsheets (XLSX, XLS, ODS, CSV) into a PDF."
    Params = Excel2PdfParams
    extensions = ("xlsx", "xls", "ods", "csv")

    def run(self, inputs: list[ToolInput], params: Excel2PdfParams) -> list[ToolOutput]:
        item = inputs[0]
        ext = self.source_ext(item.name)
        data, warnings = prepare_package(item.data, ext)
        wanted = [s for s in params.sheets.split(",") if s.strip()] or None
        with self.lo_session() as convert:
            if ext != "xlsx":  # normalise so the print settings are applied in one way
                infilter = csv_infilter(data) if ext == "csv" else None
                data = convert(data, ext, _XLSX, infilter=infilter)
            data, setup = ooxml.xlsx_page_setup(
                data,
                sheets=wanted,
                orientation=params.orientation,
                fit_width=params.fit_width,
                fit_sheet=params.fit_sheet,
            )
            pdf = convert(data, "xlsx", "pdf")
        warnings += count_warning("hidden_skipped", setup.hidden_skipped)
        warnings += font_warning(data, "xlsx", pdf)
        return [ToolOutput(output_name(item.name, "pdf"), pdf, warnings=warnings)]


registry.register(Excel2PdfTool())
