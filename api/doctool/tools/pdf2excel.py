import io
import re
from typing import Literal

from openpyxl import Workbook
from openpyxl.styles import Font
from pydantic import BaseModel, Field

from doctool import pdfextract
from doctool.tools.base import Tool, ToolError, ToolInput, ToolOutput, registry
from doctool.tools.officebase import output_name
from doctool.tools.pages import parse_pages
from doctool.tools.pdf2word import check_pages

_INT = re.compile(r"^-?\d{1,15}$")
_FLOAT = re.compile(r"^-?\d{1,15}\.\d{1,15}$")


class Pdf2ExcelParams(BaseModel):
    table_layout: Literal["per_sheet", "one_sheet"] = Field(
        "per_sheet",
        description=(
            "One table per sheet keeps each table clean. All tables on one sheet stacks them "
            "top to bottom."
        ),
    )
    pages: str = Field(
        "",
        max_length=200,
        description="Pages to search for tables, for example 1-3, 5. Leave empty for all pages.",
    )


def put(ws, row: int, col: int, value: str) -> None:
    """Numbers become numbers; everything else is stored as text, never as a formula."""
    cell = ws.cell(row=row, column=col)
    plain = value.replace(" ", "")
    if _INT.match(plain):
        cell.value = int(plain)
    elif _FLOAT.match(plain):
        cell.value = float(plain)
    else:
        cell.value = value
        cell.data_type = "s"  # "=1+1" from a PDF is text, not a formula to evaluate


class Pdf2ExcelTool(Tool):
    id = "pdf2excel"
    title = "PDF to Excel"
    group = "office"
    description = "Pull the tables of a PDF into a spreadsheet."
    Params = Pdf2ExcelParams

    def run(self, inputs: list[ToolInput], params: Pdf2ExcelParams) -> list[ToolOutput]:
        item = inputs[0]
        data = pdfextract.decrypt(item.data, item.password)
        total = pdfextract.page_count(data)
        indexes = parse_pages(params.pages.strip() or "all", total)
        check_pages(len(indexes))
        found = [
            (page.index + 1, block.rows)
            for page in pdfextract.extract(data, indexes, images=False)
            for block in page.blocks
            if block.kind == "table"
        ]
        if not found:
            raise ToolError("no_tables", "no tables were found on the selected pages")
        wb = Workbook()
        if params.table_layout == "one_sheet":
            ws = wb.active
            ws.title = "Tables"
            row = 1
            for n, (page, rows) in enumerate(found, start=1):
                ws.cell(row=row, column=1, value=f"Page {page}, table {n}").font = Font(bold=True)
                row += 1
                for values in rows:
                    for col, value in enumerate(values, start=1):
                        put(ws, row, col, value)
                    row += 1
                row += 1
        else:
            wb.remove(wb.active)
            for n, (page, rows) in enumerate(found, start=1):
                ws = wb.create_sheet(f"P{page} T{n}"[:31])
                for r, values in enumerate(rows, start=1):
                    for c, value in enumerate(values, start=1):
                        put(ws, r, c, value)
        buf = io.BytesIO()
        wb.save(buf)
        return [ToolOutput(output_name(item.name, "xlsx"), buf.getvalue())]


registry.register(Pdf2ExcelTool())
