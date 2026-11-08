"""O6: pdf2word, pdf2excel, pdf2ppt (own extractor, no LibreOffice needed by default)."""

import io

import pikepdf
import pytest
from docx import Document
from openpyxl import load_workbook
from PIL import Image
from pptx import Presentation
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

from doctool import officecore


def rich_pdf(scanned_page: bool = True, table_rows=None) -> bytes:
    """Page 1: heading, paragraph, grid table, picture. Page 2 (optional): picture only."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(72, 780, "Quarterly Report")
    c.setFont("Helvetica", 11)
    c.drawString(72, 750, "Sales grew in every region during the quarter.")
    c.drawString(72, 736, "The table below lists the totals per region.")
    rows = table_rows or [["Region", "Total"], ["North", "42"], ["South", "=1+1"], ["East", "7.5"]]
    t = Table(rows, colWidths=[120, 80])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.8, colors.black)]))
    t.wrapOn(c, 400, 200)
    t.drawOn(c, 72, 600)
    pic = Image.new("RGB", (200, 120), (200, 30, 30))
    c.drawImage(ImageReader(pic), 72, 400, width=200, height=120)
    c.showPage()
    if scanned_page:
        c.drawImage(ImageReader(Image.new("RGB", (600, 800), (240, 240, 240))), 0, 0, 595, 842)
        c.showPage()
    c.save()
    return buf.getvalue()


def image_only_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawImage(ImageReader(Image.new("RGB", (300, 400), (90, 90, 90))), 0, 0, 595, 842)
    c.showPage()
    c.save()
    return buf.getvalue()


def run(client, tool, data, name="report.pdf", password=None, expect=200, **params):
    r = client.post("/api/v1/tasks", json={"tool": tool, "params": params})
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    r = client.post(f"/api/v1/tasks/{tid}/files", files={"file": (name, data, "application/pdf")})
    assert r.status_code == 201, r.text
    fid = r.json()["files"][0]["id"]
    body = {"passwords": {fid: password}} if password else None
    r = client.post(f"/api/v1/tasks/{tid}/process", json=body)
    assert r.status_code == expect, r.text
    if expect != 200:
        return r.json(), None
    return r.json(), client.get(f"/api/v1/tasks/{tid}/download").content


def warning(task, code):
    return next((w for w in task["warnings"] if w["code"] == code), None)


def test_tools_listed_and_available_without_libreoffice(client, monkeypatch):
    monkeypatch.setattr(officecore, "find_soffice", lambda *a, **k: None)
    tools = {t["id"]: t for t in client.get("/api/v1/tools").json()}
    for tid in ("pdf2word", "pdf2excel", "pdf2ppt"):
        assert tools[tid]["group"] == "office"
        assert tools[tid]["accepts"] == "pdf"
        assert tools[tid]["available"] is True


# ---------- word ----------
def test_pdf2word_structure(client):
    task, data = run(client, "pdf2word", rich_pdf())
    doc = Document(io.BytesIO(data))
    heads = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
    assert heads == ["Quarterly Report"]
    body = " ".join(p.text for p in doc.paragraphs)
    assert "Sales grew in every region during the quarter." in body
    assert len(doc.tables) == 1
    assert doc.tables[0].cell(1, 0).text == "North" and doc.tables[0].cell(2, 1).text == "=1+1"
    assert len(doc.inline_shapes) == 2  # the picture, and the scanned page kept as a picture
    w = warning(task, "no_text_layer")
    assert w and w["params"] == {"pages": "2"}
    assert [f["filename"] for f in task["files"] if f["role"] == "out"] == ["report.docx"]


def test_pdf2word_without_images(client):
    _, data = run(client, "pdf2word", rich_pdf(scanned_page=False), include_images=False)
    assert len(Document(io.BytesIO(data)).inline_shapes) == 0


def test_pdf2word_scanned_only_is_an_error(client):
    body, _ = run(client, "pdf2word", image_only_pdf(), expect=400)
    assert body["detail"]["state"] == "no_text"


def test_pdf2word_password(client):
    src = pikepdf.open(io.BytesIO(rich_pdf(scanned_page=False)))
    buf = io.BytesIO()
    src.save(buf, encryption=pikepdf.Encryption(owner="o", user="secret"))
    body, _ = run(client, "pdf2word", buf.getvalue(), expect=400)
    assert body["detail"]["state"] == "wrong_password"


@pytest.mark.office
@pytest.mark.skipif(officecore.find_soffice() is None, reason="LibreOffice not installed")
def test_pdf2word_keep_look_uses_libreoffice(client):
    _, data = run(client, "pdf2word", rich_pdf(scanned_page=False), fidelity="keep_look")
    assert data[:2] == b"PK"
    Document(io.BytesIO(data))


def test_pdf2word_keep_look_without_engine(client, monkeypatch):
    monkeypatch.setattr(officecore, "find_soffice", lambda *a, **k: None)
    body, _ = run(
        client, "pdf2word", rich_pdf(scanned_page=False), fidelity="keep_look", expect=400
    )
    assert body["detail"]["state"] == "engine_missing"


# ---------- excel ----------
def test_pdf2excel_per_sheet_values_and_no_formula_injection(client):
    _, data = run(client, "pdf2excel", rich_pdf())
    wb = load_workbook(io.BytesIO(data))
    assert len(wb.worksheets) == 1
    ws = wb.worksheets[0]
    assert ws["A2"].value == "North" and ws["B2"].value == 42
    assert ws["B4"].value == 7.5
    assert ws["B3"].value == "=1+1" and ws["B3"].data_type == "s"  # text, never a formula


def test_pdf2excel_one_sheet_stacks_tables(client):
    two = io.BytesIO()
    w = pikepdf.new()
    for _ in range(2):
        w.pages.extend(pikepdf.open(io.BytesIO(rich_pdf(scanned_page=False))).pages)
    w.save(two)
    _, data = run(client, "pdf2excel", two.getvalue(), table_layout="one_sheet")
    wb = load_workbook(io.BytesIO(data))
    assert len(wb.worksheets) == 1
    values = [c.value for c in wb.worksheets[0]["A"] if c.value]
    assert values.count("North") == 2
    _, data = run(client, "pdf2excel", two.getvalue(), table_layout="per_sheet")
    assert len(load_workbook(io.BytesIO(data)).worksheets) == 2
    _, data = run(client, "pdf2excel", two.getvalue(), pages="2")
    assert len(load_workbook(io.BytesIO(data)).worksheets) == 1


def test_pdf2excel_no_tables_is_an_error(client):
    body, _ = run(client, "pdf2excel", image_only_pdf(), expect=400)
    assert body["detail"]["state"] == "no_tables"


# ---------- powerpoint ----------
def test_pdf2ppt_one_picture_slide_per_page(client):
    _, data = run(client, "pdf2ppt", rich_pdf(), dpi=72)
    prs = Presentation(io.BytesIO(data))
    assert len(prs.slides) == 2
    assert prs.slide_width == round(595.276 * 12700) or abs(prs.slide_width - 595 * 12700) < 12700
    for slide in prs.slides:
        assert [s.shape_type for s in slide.shapes].count(13) == 1  # MSO_SHAPE_TYPE.PICTURE
        assert not any(s.has_text_frame and s.text_frame.text for s in slide.shapes)


def test_pdf2ppt_picture_and_text(client):
    _, data = run(client, "pdf2ppt", rich_pdf(), slide_content="picture_text", dpi=72)
    slide = Presentation(io.BytesIO(data)).slides[0]
    texts = " ".join(s.text_frame.text for s in slide.shapes if s.has_text_frame)
    assert "Quarterly Report" in texts
    assert slide.shapes[-1].shape_type == 13  # picture is on top of the text


def test_pdf2ppt_dpi_bounds(client):
    r = client.post("/api/v1/tasks", json={"tool": "pdf2ppt", "params": {"dpi": 1000}})
    assert r.status_code == 422


def test_pdf2word_reports_pictures_it_could_not_carry(client, monkeypatch):
    from doctool import pdfextract

    monkeypatch.setattr(pdfextract, "MAX_RENDER_PIXELS", 10)
    task, _ = run(client, "pdf2word", rich_pdf(scanned_page=False))
    assert warning(task, "images_skipped") == {"code": "images_skipped", "params": {"count": 1}}


def test_pdf2word_hides_keep_look_without_engine(client, monkeypatch):
    monkeypatch.setattr(officecore, "find_soffice", lambda *a, **k: None)
    tool = {t["id"]: t for t in client.get("/api/v1/tools").json()}["pdf2word"]
    assert tool["params_schema"]["properties"]["fidelity"]["enum"] == ["editable"]
    monkeypatch.setattr(officecore, "find_soffice", lambda *a, **k: __file__)
    tool = {t["id"]: t for t in client.get("/api/v1/tools").json()}["pdf2word"]
    assert tool["params_schema"]["properties"]["fidelity"]["enum"] == ["editable", "keep_look"]


def test_pdf2ppt_total_render_budget(client, monkeypatch):
    monkeypatch.setenv("DOCTOOL_OFFICE_RENDER_BUDGET_PIXELS", "1000")
    body, _ = run(client, "pdf2ppt", rich_pdf(), expect=400)
    assert body["detail"]["state"] == "too_large"


def test_pdf_to_office_tools_use_the_bounded_lanes(client):
    from doctool.routers import tasks

    taken = 0
    while tasks._IMAGE_SLOTS.acquire(blocking=False):
        taken += 1
    try:
        body, _ = run(client, "pdf2word", rich_pdf(scanned_page=False), expect=503)
        assert body["detail"]["state"] == "busy"
    finally:
        for _ in range(taken):
            tasks._IMAGE_SLOTS.release()


def test_pdf2ppt_caps_the_bytes_it_holds(client, monkeypatch):
    monkeypatch.setenv("DOCTOOL_OFFICE_MAX_OUTPUT_BYTES", "100")
    body, _ = run(client, "pdf2ppt", rich_pdf(), expect=400)
    assert body["detail"]["state"] == "too_large"


@pytest.mark.parametrize(
    "data,state", [(b"", "not_pdf"), (b"garbage", "not_pdf"), (b"%PDF-1.7\n1 0 obj", "damaged")]
)
def test_bad_pdf_uploads_get_a_state_and_no_internals(client, data, state):
    r = client.post("/api/v1/tasks", json={"tool": "pdf2word", "params": {}})
    tid = r.json()["id"]
    r = client.post(
        f"/api/v1/tasks/{tid}/files", files={"file": ("x.pdf", data, "application/pdf")}
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["state"] == state
    assert "BytesIO" not in detail["message"] and "stream" not in detail["message"]
