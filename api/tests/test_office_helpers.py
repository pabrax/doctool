"""O5 helpers: OOXML package patching, PDF page layout, HTML sanitising (no LibreOffice needed)."""

import io
import zipfile

import pikepdf
import pytest
from docx import Document
from openpyxl import Workbook, load_workbook
from pptx import Presentation

from doctool import htmlsafe, ooxml, pdflayout
from doctool.tools.base import ToolError
from tests.pdfs import make_pdf


def xlsx_bytes(hidden: bool = True) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Wide"
    for c in range(1, 16):
        ws.cell(1, c, c)
    wb.create_sheet("Small")["A1"] = "s"
    if hidden:
        wb.create_sheet("Secret").sheet_state = "hidden"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def parts(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist()}


# ---------- external relationships ----------
def docx_with_external_image() -> bytes:
    d = Document()
    d.add_paragraph("x")
    buf = io.BytesIO()
    d.save(buf)
    p = parts(buf.getvalue())
    rels = p["word/_rels/document.xml.rels"].replace(
        b"</Relationships>",
        b'<Relationship Id="rIdX" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        b'relationships/image" Target="http://evil.example/a.png" TargetMode="External"/>'
        b'<Relationship Id="rIdH" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        b'relationships/hyperlink" Target="https://ok.example/" TargetMode="External"/>'
        b"</Relationships>",
    )
    p["word/_rels/document.xml.rels"] = rels
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in p.items():
            z.writestr(n, b)
    return out.getvalue()


def test_neutralize_external_blocks_fetchable_targets_but_keeps_hyperlinks():
    data, blocked = ooxml.neutralize_external(docx_with_external_image())
    assert blocked == 1
    rels = parts(data)["word/_rels/document.xml.rels"]
    assert b"evil.example" not in rels
    assert b"https://ok.example/" in rels
    Document(io.BytesIO(data))  # still a valid package


def test_neutralize_external_noop_without_links():
    d = Document()
    buf = io.BytesIO()
    d.save(buf)
    _, blocked = ooxml.neutralize_external(buf.getvalue())
    assert blocked == 0


# ---------- xlsx page setup ----------
def test_xlsx_setup_fit_width_and_orientation():
    data, info = ooxml.xlsx_page_setup(
        xlsx_bytes(), sheets=None, orientation="landscape", fit_width=True, fit_sheet=False
    )
    wb = load_workbook(io.BytesIO(data))
    ws = wb["Wide"]
    assert ws.page_setup.orientation == "landscape"
    assert ws.page_setup.fitToWidth == 1 and ws.page_setup.fitToHeight == 0
    assert ws.sheet_properties.pageSetUpPr.fitToPage is True
    assert info.visible == 2 and info.hidden_skipped == 1


def test_xlsx_setup_fit_sheet_is_one_by_one():
    data, _ = ooxml.xlsx_page_setup(
        xlsx_bytes(), sheets=None, orientation="portrait", fit_width=False, fit_sheet=True
    )
    ws = load_workbook(io.BytesIO(data))["Small"]
    assert ws.page_setup.fitToWidth == 1 and ws.page_setup.fitToHeight == 1


def test_xlsx_setup_auto_orientation_picks_landscape_for_wide_sheets():
    data, _ = ooxml.xlsx_page_setup(
        xlsx_bytes(), sheets=None, orientation="auto", fit_width=False, fit_sheet=False
    )
    wb = load_workbook(io.BytesIO(data))
    assert wb["Wide"].page_setup.orientation == "landscape"
    assert wb["Small"].page_setup.orientation == "portrait"


@pytest.mark.parametrize("sel", [["Small"], ["2"], ["small"]])
def test_xlsx_setup_sheet_selection_hides_the_rest(sel):
    data, info = ooxml.xlsx_page_setup(
        xlsx_bytes(), sheets=sel, orientation="auto", fit_width=False, fit_sheet=False
    )
    wb = load_workbook(io.BytesIO(data))
    assert wb["Small"].sheet_state == "visible"
    assert wb["Wide"].sheet_state == "hidden"
    assert info.visible == 1


def test_xlsx_setup_selection_matching_nothing_is_an_error():
    with pytest.raises(ToolError) as e:
        ooxml.xlsx_page_setup(
            xlsx_bytes(), sheets=["Nope"], orientation="auto", fit_width=False, fit_sheet=False
        )
    assert e.value.state == "out_of_range"


def test_xlsx_setup_cannot_select_a_hidden_sheet():
    with pytest.raises(ToolError):
        ooxml.xlsx_page_setup(
            xlsx_bytes(), sheets=["Secret"], orientation="auto", fit_width=False, fit_sheet=False
        )


# ---------- pptx / fonts / legacy macros ----------
def test_pptx_hidden_slide_count():
    prs = Presentation()
    for _ in range(3):
        prs.slides.add_slide(prs.slide_layouts[5])
    prs.slides[1]._element.set("show", "0")
    buf = io.BytesIO()
    prs.save(buf)
    assert ooxml.pptx_hidden_slides(buf.getvalue()) == 1


def test_document_fonts_docx():
    d = Document()
    d.add_paragraph().add_run("a").font.name = "NonExistentFontXYZ"
    buf = io.BytesIO()
    d.save(buf)
    assert "NonExistentFontXYZ" in ooxml.document_fonts(buf.getvalue(), "docx")


def test_ole_macro_detection():
    ole = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    assert ooxml.ole_has_macros(ole + "_VBA_PROJECT".encode("utf-16-le") + b"\0" * 32)
    assert not ooxml.ole_has_macros(ole + b"\0" * 64)


# ---------- pdf layout ----------
def test_substituted_fonts_ignores_subset_prefix_and_style_suffixes():
    used = {"Arial", "Calibri Light", "NonExistentFontXYZ"}
    in_pdf = {"ABCDEF+ArialMT", "BAAAAA+Calibri-Light", "CAAAAA+LiberationSerif"}
    assert pdflayout.substituted_fonts(used, in_pdf) == ["NonExistentFontXYZ"]


def test_fit_to_size_letter_keeps_page_count_and_orientation():
    src = make_pdf(2)
    out = pikepdf.open(io.BytesIO(pdflayout.fit_to_size(src, "letter")))
    assert len(out.pages) == 2
    w, h = (float(x) for x in out.pages[0].mediabox[2:])
    assert (round(w), round(h)) == (612, 792)


def test_nup_handouts():
    src = make_pdf(5)
    out = pikepdf.open(io.BytesIO(pdflayout.nup(src, 4)))
    assert len(out.pages) == 2  # 5 slides, 4 per page
    w, h = (float(x) for x in out.pages[0].mediabox[2:])
    assert (round(w), round(h)) == (595, 842)


# ---------- html ----------
def test_html_sanitize_removes_active_and_remote_content():
    html = (
        b"<html><head><script>alert(1)</script><link rel=stylesheet href='http://x/a.css'>"
        b"<style>@import url(http://x/b.css); body{background:url(file:///etc/passwd)}</style>"
        b"</head><body onload='x()'><img src='http://x/p.png'><img src='file:///C:/secret.png'>"
        b"<img src='data:image/png;base64,iVBORw0KGgo='><iframe src='http://x'></iframe>"
        b"<a href='https://ok.example/'>link</a></body></html>"
    )
    out, blocked = htmlsafe.sanitize(html, page_size="a4", orientation="auto", backgrounds=True)
    low = out.lower()
    for bad in (b"<script", b"onload", b"http://x", b"file:", b"<iframe", b"@import"):
        assert bad not in low, bad
    assert b"data:image/png" in low and b"https://ok.example/" in low
    assert blocked >= 5
    assert b"@page { size: 210mm 297mm" in low


def test_html_sanitize_landscape_and_no_backgrounds():
    out, _ = htmlsafe.sanitize(
        b"<p>x</p>", page_size="letter", orientation="landscape", backgrounds=False
    )
    low = out.lower()
    assert b"size: 279.4mm 215.9mm" in low
    assert b"background: none" in low


def test_xlsx_sheet_numbers_count_only_visible_tabs():
    wb = Workbook()
    wb.active.title = "First"
    wb.create_sheet("Hidden").sheet_state = "hidden"
    wb.create_sheet("Third")["A1"] = "x"
    buf = io.BytesIO()
    wb.save(buf)
    data, info = ooxml.xlsx_page_setup(
        buf.getvalue(), sheets=["2"], orientation="auto", fit_width=False, fit_sheet=False
    )
    out = load_workbook(io.BytesIO(data))
    assert out["Third"].sheet_state == "visible" and out["First"].sheet_state == "hidden"
    assert info.visible == 1


def test_html_auto_orientation_lets_the_page_decide():
    page = b"<html><head><style>@page { size: A4 landscape }</style></head><body>x</body></html>"
    out, _ = htmlsafe.sanitize(page, page_size="a4", orientation="auto", backgrounds=True)
    low = out.lower()
    # ours first, so theirs wins
    assert low.index(b"size: 210mm 297mm") < low.index(b"size: a4 landscape")
    out, _ = htmlsafe.sanitize(page, page_size="a4", orientation="portrait", backgrounds=True)
    low = out.lower()
    assert low.index(b"size: 210mm 297mm") > low.index(b"size: a4 landscape")  # explicit: ours wins


def test_neutralize_external_handles_single_quotes():
    d = Document()
    buf = io.BytesIO()
    d.save(buf)
    p = parts(buf.getvalue())
    p["word/_rels/document.xml.rels"] = p["word/_rels/document.xml.rels"].replace(
        b"</Relationships>",
        b"<Relationship Id='rIdQ' Type='http://schemas.openxmlformats.org/officeDocument/2006/"
        b"relationships/image' Target='http://evil.example/q.png' TargetMode='External'/>"
        b"</Relationships>",
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for n, b in p.items():
            z.writestr(n, b)
    data, blocked = ooxml.neutralize_external(out.getvalue())
    assert blocked == 1 and b"evil.example" not in parts(data)["word/_rels/document.xml.rels"]


def test_html_srcset_is_always_dropped():
    out, _ = htmlsafe.sanitize(
        b"<img src='data:image/png;base64,AA==' "
        b"srcset='data:image/png;base64,AA== 1x, http://x/y.png 2x'>",
        page_size="a4", orientation="auto", backgrounds=True,
    )
    assert b"srcset" not in out.lower() and b"http://x" not in out
