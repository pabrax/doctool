"""O5: word2pdf, excel2pdf, ppt2pdf, html2pdf end to end through the API with real LibreOffice."""

import io

import pikepdf
import pypdfium2 as pdfium
import pytest
from docx import Document
from openpyxl import Workbook
from pptx import Presentation

from doctool import officecore
from tests.test_office_helpers import docx_with_external_image

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(officecore.find_soffice() is None, reason="LibreOffice not installed"),
]


def run_tool(client, tool, name, data, **params):
    r = client.post("/api/v1/tasks", json={"tool": tool, "params": params})
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    r = client.post(f"/api/v1/tasks/{tid}/files", files={"file": (name, data)})
    assert r.status_code == 201, r.text
    r = client.post(f"/api/v1/tasks/{tid}/process")
    assert r.status_code == 200, r.text
    task = r.json()
    pdf = client.get(f"/api/v1/tasks/{tid}/download").content
    assert pdf.startswith(b"%PDF")
    return task, pdf


def n_pages(pdf: bytes) -> int:
    with pikepdf.open(io.BytesIO(pdf)) as p:
        return len(p.pages)


def first_size(pdf: bytes) -> tuple[int, int]:
    with pikepdf.open(io.BytesIO(pdf)) as p:
        mb = p.pages[0].mediabox
        return round(float(mb[2]) - float(mb[0])), round(float(mb[3]) - float(mb[1]))


def text(pdf: bytes) -> str:
    d = pdfium.PdfDocument(pdf)
    return " ".join(d[i].get_textpage().get_text_range() for i in range(len(d)))


def codes(task) -> dict:
    return {w["code"]: w.get("params", {}) for w in task["warnings"]}


def test_tools_are_listed_in_the_office_group(client):
    tools = {t["id"]: t for t in client.get("/api/v1/tools").json()}
    for tid in ("word2pdf", "excel2pdf", "ppt2pdf", "html2pdf"):
        assert tools[tid]["group"] == "office" and tools[tid]["available"] is True
    assert tools["excel2pdf"]["extensions"] == ["xlsx", "xls", "ods", "csv"]


# ---------- word ----------
def docx(font: str = "Arial") -> bytes:
    d = Document()
    d.add_paragraph().add_run("Hola mundo con ñ").font.name = font
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def test_word2pdf_basic_and_output_name(client):
    task, pdf = run_tool(client, "word2pdf", "Informe final.docx", docx())
    assert n_pages(pdf) == 1 and "Hola mundo" in text(pdf)
    assert [f["filename"] for f in task["files"] if f["role"] == "out"] == ["Informe final.pdf"]
    assert "font_substituted" not in codes(task)


def test_word2pdf_page_size_letter(client):
    _, pdf = run_tool(client, "word2pdf", "a.docx", docx(), page_size="letter")
    assert first_size(pdf) == (612, 792)


def test_word2pdf_warns_about_missing_fonts(client):
    task, _ = run_tool(client, "word2pdf", "a.docx", docx("NonExistentFontXYZ"))
    assert "NonExistentFontXYZ" in codes(task)["font_substituted"]["fonts"]


def test_word2pdf_blocks_external_images(client):
    task, _ = run_tool(client, "word2pdf", "a.docx", docx_with_external_image())
    assert codes(task)["external_links_blocked"] == {"count": 1}


def test_word2pdf_plain_text(client):
    _, pdf = run_tool(client, "word2pdf", "notes.txt", "línea uno\nlínea dos\n".encode())
    assert "uno" in text(pdf)


# ---------- excel ----------
def xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Wide"
    for r in range(1, 30):
        for c in range(1, 26):
            ws.cell(r, c, f"w{r}x{c}")
    wb.create_sheet("Small")["A1"] = "small sheet"
    secret = wb.create_sheet("Secret")
    secret["A1"] = "secret text"
    secret.sheet_state = "hidden"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_excel2pdf_defaults_fit_width_and_skip_hidden(client):
    task, pdf = run_tool(client, "excel2pdf", "book.xlsx", xlsx())
    assert n_pages(pdf) == 2  # wide sheet fits one page width, small sheet one page
    assert "secret text" not in text(pdf)
    assert codes(task)["hidden_skipped"] == {"count": 1}
    assert first_size(pdf)[0] > first_size(pdf)[1]  # auto orientation -> landscape for wide


def test_excel2pdf_sheet_selection(client):
    _, pdf = run_tool(client, "excel2pdf", "book.xlsx", xlsx(), sheets="Small")
    t = text(pdf)
    assert "small sheet" in t and "w1x1" not in t


def test_excel2pdf_fit_sheet_one_page_each(client):
    _, pdf = run_tool(
        client, "excel2pdf", "book.xlsx", xlsx(), fit_sheet=True, orientation="portrait"
    )
    assert n_pages(pdf) == 2
    assert first_size(pdf)[0] < first_size(pdf)[1]


def test_excel2pdf_csv(client):
    _, pdf = run_tool(client, "excel2pdf", "data.csv", b"name,value\nuno,1\ndos,2\n")
    assert "uno" in text(pdf)


def test_excel2pdf_unknown_sheet_is_an_error(client):
    r = client.post("/api/v1/tasks", json={"tool": "excel2pdf", "params": {"sheets": "Nope"}})
    tid = r.json()["id"]
    client.post(f"/api/v1/tasks/{tid}/files", files={"file": ("b.xlsx", xlsx())})
    r = client.post(f"/api/v1/tasks/{tid}/process")
    assert r.status_code == 400 and r.json()["detail"]["state"] == "out_of_range"


# ---------- powerpoint ----------
def pptx() -> bytes:
    prs = Presentation()
    for i in range(6):
        s = prs.slides.add_slide(prs.slide_layouts[5])
        s.shapes.title.text = f"Slide {i + 1}"
        s.notes_slide.notes_text_frame.text = f"speaker note {i + 1}"
    prs.slides[5]._element.set("show", "0")
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def test_ppt2pdf_skips_hidden_by_default(client):
    task, pdf = run_tool(client, "ppt2pdf", "deck.pptx", pptx())
    assert n_pages(pdf) == 5
    assert codes(task)["hidden_skipped"] == {"count": 1}


def test_ppt2pdf_include_hidden(client):
    task, pdf = run_tool(client, "ppt2pdf", "deck.pptx", pptx(), include_hidden=True)
    assert n_pages(pdf) == 6 and "hidden_skipped" not in codes(task)


def test_ppt2pdf_handouts(client):
    _, pdf = run_tool(client, "ppt2pdf", "deck.pptx", pptx(), handout="h4")
    assert n_pages(pdf) == 2  # 5 visible slides, 4 per page
    assert first_size(pdf) == (595, 842)


def test_ppt2pdf_notes(client):
    _, pdf = run_tool(client, "ppt2pdf", "deck.pptx", pptx(), include_notes=True)
    assert n_pages(pdf) == 5 and "speaker note 1" in text(pdf)


# ---------- html ----------
HTML = b"""<html><head><title>t</title><script>document.write('INJECTED')</script></head>
<body><h1>Factura</h1><img src="http://example.invalid/x.png"><p>Total 42</p></body></html>"""


def test_html2pdf_sanitized_and_sized(client):
    task, pdf = run_tool(
        client, "html2pdf", "page.html", HTML, page_size="letter", orientation="landscape"
    )
    t = text(pdf)
    assert "Factura" in t and "INJECTED" not in t
    assert first_size(pdf) == (792, 612)
    assert codes(task)["external_links_blocked"]["count"] >= 2


def test_html2pdf_rejects_other_types(client):
    r = client.post("/api/v1/tasks", json={"tool": "html2pdf", "params": {}})
    tid = r.json()["id"]
    r = client.post(f"/api/v1/tasks/{tid}/files", files={"file": ("x.docx", docx())})
    assert r.status_code == 422 and r.json()["detail"]["state"] == "unsupported"
