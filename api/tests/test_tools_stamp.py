import io

import pikepdf
import pytest
from PIL import Image

from tests.helpers import run_tool
from tests.pdfs import make_pdf, page_count, page_text


def png_bytes(color=(255, 0, 0, 255), size=(40, 20)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, "PNG")
    return buf.getvalue()


def image_count(data: bytes, page: int) -> int:
    with pikepdf.open(io.BytesIO(data)) as pdf:
        return len(pdf.pages[page].get_images())


# ---- watermark ---------------------------------------------------------------------------
def test_text_watermark_added_and_original_text_survives(client):
    out = run_tool(
        client, "watermark", {"text": "CONFIDENTIAL"}, [("a.pdf", make_pdf(2, "Body"))]
    ).content
    texts = page_text(out)
    assert page_count(out) == 2
    for i, t in enumerate(texts, 1):
        assert f"Body {i}" in t and "CONFIDENTIAL" in t


def test_watermark_only_selected_pages(client):
    out = run_tool(
        client, "watermark", {"text": "DRAFT", "pages": "2"}, [("a.pdf", make_pdf(3, "Body"))]
    ).content
    texts = page_text(out)
    assert "DRAFT" not in texts[0] and "DRAFT" in texts[1] and "DRAFT" not in texts[2]


def test_watermark_layer_below_still_works(client):
    out = run_tool(
        client, "watermark", {"text": "UNDER", "layer": "below"}, [("a.pdf", make_pdf(1, "Body"))]
    ).content
    assert "UNDER" in page_text(out)[0] and "Body 1" in page_text(out)[0]


def test_watermark_mosaic_repeats_text(client):
    out = run_tool(
        client, "watermark", {"text": "TILE", "mosaic": True}, [("a.pdf", make_pdf(1))]
    ).content
    assert page_text(out)[0].count("TILE") > 1


def test_watermark_accented_spanish_text(client):
    out = run_tool(
        client, "watermark", {"text": "CONFIDENCIAL ñ"}, [("a.pdf", make_pdf(1))]
    ).content
    assert "CONFIDENCIAL" in page_text(out)[0]


def test_watermark_image_mode_adds_image(client):
    out = run_tool(
        client,
        "watermark",
        {"mode": "image", "opacity": 0.5},
        [("a.pdf", make_pdf(2)), ("logo.png", png_bytes(), "image/png")],
    ).content
    assert image_count(out, 0) == 1 and image_count(out, 1) == 1


def test_watermark_image_mode_without_image_is_rejected(client):
    r = run_tool(client, "watermark", {"mode": "image"}, [("a.pdf", make_pdf(1))], expect=400)
    assert r.json()["detail"]["state"] == "no_images"


def test_watermark_rejects_invalid_params(client):
    bad = [
        {"text": ""},
        {"mode": "text"},
        {"text": "x", "color": "red"},
        {"text": "x", "opacity": 2},
        {"text": "日本語"},
    ]
    for params in bad:
        assert (
            client.post("/api/v1/tasks", json={"tool": "watermark", "params": params}).status_code
            == 422
        )


def test_watermark_rejects_non_pdf_non_image_upload(client):
    t = client.post("/api/v1/tasks", json={"tool": "watermark", "params": {"text": "x"}}).json()
    r = client.post(
        f"/api/v1/tasks/{t['id']}/files", files={"file": ("x.bin", b"garbage", "text/plain")}
    )
    assert r.status_code == 422


# ---- page numbers ------------------------------------------------------------------------
def test_page_numbers_default_format(client):
    out = run_tool(client, "pagenumber", {"format": "Num {n} of {total}"}, [("a.pdf", make_pdf(3))])
    texts = page_text(out.content)
    assert [f"Num {i} of 3" in t for i, t in enumerate(texts, 1)] == [True, True, True]


def test_page_numbers_start_and_skip_first(client):
    out = run_tool(
        client,
        "pagenumber",
        {"format": "#{n}", "start": 10, "skip_first": True},
        [("a.pdf", make_pdf(3))],
    )
    texts = page_text(out.content)
    assert "#" not in texts[0]
    assert "#10" in texts[1] and "#11" in texts[2]


def test_page_numbers_selected_pages_count_from_start(client):
    out = run_tool(
        client,
        "pagenumber",
        {"format": "#{n}", "pages": "2-3"},
        [("a.pdf", make_pdf(4))],
    )
    texts = page_text(out.content)
    assert "#" not in texts[0] and "#1" in texts[1] and "#2" in texts[2] and "#" not in texts[3]


@pytest.mark.parametrize(
    "position", ["top-left", "top-center", "top-right", "bottom-left", "bottom-right"]
)
def test_page_numbers_all_positions_render(client, position):
    out = run_tool(
        client, "pagenumber", {"format": "#{n}", "position": position}, [("a.pdf", make_pdf(1))]
    )
    assert "#1" in page_text(out.content)[0]


def test_page_numbers_format_must_contain_n(client):
    r = client.post("/api/v1/tasks", json={"tool": "pagenumber", "params": {"format": "page"}})
    assert r.status_code == 422


def test_stamp_tools_listed(client):
    ids = {t["id"] for t in client.get("/api/v1/tools").json()}
    assert {"watermark", "pagenumber"} <= ids


def dark_pixels_in_band(data: bytes, band: str) -> int:
    """Render page 1 with PDFium and count dark pixels in the bottom/top 8% central band."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    try:
        img = pdf[0].render(scale=1).to_pil().convert("L")
    finally:
        pdf.close()
    w, h = img.size
    box = (int(w * 0.35), int(h * 0.92), int(w * 0.65), h) if band == "bottom" else (
        int(w * 0.35), 0, int(w * 0.65), int(h * 0.08))  # fmt: skip
    return sum(1 for px in img.crop(box).tobytes() if px < 128)


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_page_number_lands_at_visual_bottom_even_on_rotated_pages(client, angle):
    src = make_pdf(1, "Body")
    if angle:
        src = run_tool(client, "rotate", {"angle": angle}, [("a.pdf", src)]).content
    out = run_tool(
        client, "pagenumber", {"format": "NUMBER {n}", "font_size": 14}, [("a.pdf", src)]
    ).content
    assert dark_pixels_in_band(out, "bottom") > 20
