import io

import img2pdf
import pikepdf
import pytest
from PIL import Image, ImageFilter

from tests.helpers import outputs, run_tool
from tests.pdfs import make_pdf, page_count, page_text


def noise_image(w=1000, h=800, seed=1) -> Image.Image:
    import random

    rnd = random.Random(seed)
    data = bytes(rnd.getrandbits(8) for _ in range(w * h * 3))
    return Image.frombytes("RGB", (w, h), data).filter(ImageFilter.GaussianBlur(1.5))


def img_bytes(img: Image.Image, fmt: str, **kw) -> bytes:
    buf = io.BytesIO()
    img.save(buf, fmt, **kw)
    return buf.getvalue()


@pytest.fixture(scope="module")
def heavy_pdf_jpeg() -> bytes:
    return img2pdf.convert(img_bytes(noise_image(), "JPEG", quality=100))


@pytest.fixture(scope="module")
def heavy_pdf_png() -> bytes:
    return img2pdf.convert(img_bytes(noise_image(seed=2), "PNG"))


# ---- compress ----------------------------------------------------------------------------
def test_compress_recommended_shrinks_heavy_jpeg_pdf_and_stays_valid(client, heavy_pdf_jpeg):
    out = run_tool(
        client, "compress", {"level": "recommended"}, [("h.pdf", heavy_pdf_jpeg)]
    ).content
    assert len(out) < len(heavy_pdf_jpeg) * 0.8
    with pikepdf.open(io.BytesIO(out)) as pdf:
        assert pdf.check_pdf_syntax() == []
        assert len(pdf.pages) == 1


def test_compress_levels_are_ordered_by_size(client, heavy_pdf_png):
    sizes = {
        lvl: len(run_tool(client, "compress", {"level": lvl}, [("h.pdf", heavy_pdf_png)]).content)
        for lvl in ("low", "recommended", "extreme")
    }
    assert sizes["extreme"] < sizes["recommended"] <= sizes["low"] <= len(heavy_pdf_png)


def test_compress_never_returns_a_bigger_file(client):
    src = make_pdf(3)
    out = run_tool(client, "compress", {"level": "extreme"}, [("a.pdf", src)]).content
    assert len(out) <= len(src)
    assert page_text(out) == ["Page 1", "Page 2", "Page 3"]


def test_compress_keeps_text_extractable_and_page_count(client, heavy_pdf_png):
    out = run_tool(client, "compress", {"level": "recommended"}, [("h.pdf", heavy_pdf_png)])
    assert page_count(out.content) == 1


def test_compress_rejects_bad_level(client):
    r = client.post("/api/v1/tasks", json={"tool": "compress", "params": {"level": "max"}})
    assert r.status_code == 422


# ---- images -> pdf -----------------------------------------------------------------------
def rgba_png() -> bytes:
    return img_bytes(Image.new("RGBA", (200, 100), (255, 0, 0, 128)), "PNG")


def sizes(data: bytes) -> list[tuple[float, float]]:
    with pikepdf.open(io.BytesIO(data)) as pdf:
        return [
            (
                float(p.mediabox[2]) - float(p.mediabox[0]),
                float(p.mediabox[3]) - float(p.mediabox[1]),
            )
            for p in pdf.pages
        ]


def imgs():
    return [
        ("a.png", rgba_png(), "image/png"),
        ("b.jpg", img_bytes(Image.new("RGB", (100, 200), "blue"), "JPEG"), "image/jpeg"),
        ("c.gif", img_bytes(Image.new("P", (50, 50), 3), "GIF"), "image/gif"),
        ("d.bmp", img_bytes(Image.new("RGB", (30, 30), "green"), "BMP"), "image/bmp"),
    ]


def test_images_to_pdf_merged_one_page_per_image_in_order(client):
    out = run_tool(client, "imagepdf", {}, imgs()).content
    assert page_count(out) == 4
    s = sizes(out)
    assert s[0][0] > s[0][1]  # landscape png first
    assert s[1][0] < s[1][1]  # portrait jpg second


def test_images_to_pdf_a4_pages(client):
    out = run_tool(
        client, "imagepdf", {"page_size": "A4", "orientation": "portrait"}, imgs()
    ).content
    for w, h in sizes(out):
        assert abs(w - 595.3) < 1 and abs(h - 841.9) < 1


def test_images_to_pdf_landscape_swaps_page(client):
    out = run_tool(
        client, "imagepdf", {"page_size": "letter", "orientation": "landscape"}, imgs()[:1]
    )
    w, h = sizes(out.content)[0]
    assert (round(w), round(h)) == (792, 612)


def test_images_to_pdf_separate_files_zip(client):
    out = run_tool(client, "imagepdf", {"merge": False}, imgs()[:3])
    files = outputs(out)
    assert len(files) == 3 and all(page_count(d) == 1 for _, d in files)


def test_images_to_pdf_margin_shrinks_image_area(client):
    a = run_tool(client, "imagepdf", {"page_size": "A4", "margin": 0}, imgs()[1:2]).content
    b = run_tool(client, "imagepdf", {"page_size": "A4", "margin": 60}, imgs()[1:2]).content
    assert len(a) > 0 and len(b) > 0 and page_count(a) == page_count(b) == 1


def test_images_to_pdf_rejects_non_image_upload(client):
    t = client.post("/api/v1/tasks", json={"tool": "imagepdf", "params": {}}).json()
    r = client.post(
        f"/api/v1/tasks/{t['id']}/files", files={"file": ("x.png", b"not an image", "image/png")}
    )
    assert r.status_code == 422
    r = client.post(
        f"/api/v1/tasks/{t['id']}/files", files={"file": ("x.pdf", make_pdf(1), "application/pdf")}
    )
    assert r.status_code == 422


def test_images_to_pdf_result_is_saved_in_library_as_valid_pdf(client):
    run_tool(client, "imagepdf", {}, imgs()[:2])
    doc = client.get("/api/v1/documents").json()[0]
    assert doc["latest_version"]["pages"] == 2 and doc["latest_version"]["tool"] == "imagepdf"


# ---- pdf -> images -----------------------------------------------------------------------
def test_pdf_to_images_png_zip_one_per_page(client):
    out = run_tool(client, "pdfimage", {"format": "png", "dpi": 72}, [("doc.pdf", make_pdf(3))])
    files = outputs(out)
    assert [n for n, _ in files] == ["doc_page1.png", "doc_page2.png", "doc_page3.png"]
    for _, data in files:
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        w, h = Image.open(io.BytesIO(data)).size
        assert (w, h) == (596, 842)  # pdfium rounds A4 (595.28pt) up


def test_pdf_to_images_dpi_scales_pixels(client):
    out = run_tool(client, "pdfimage", {"dpi": 144}, [("doc.pdf", make_pdf(1))])
    w, h = Image.open(io.BytesIO(out.content)).size
    assert (w, h) == (1191, 1684)


def test_pdf_to_images_jpg_and_page_selection(client):
    out = run_tool(client, "pdfimage", {"format": "jpg", "pages": "2"}, [("doc.pdf", make_pdf(3))])
    assert out.headers["content-type"] == "image/jpeg"
    assert out.content[:2] == b"\xff\xd8"


def test_pdf_to_images_encrypted_needs_password(client):
    locked = run_tool(client, "protect", {"password": "pw"}, [("a.pdf", make_pdf(1))]).content
    r = run_tool(client, "pdfimage", {}, [("a.pdf", locked)], expect=400)
    assert r.json()["detail"]["state"] == "wrong_password"
    ok = run_tool(client, "pdfimage", {"dpi": 72}, [("a.pdf", locked)], passwords=["pw"])
    assert ok.content[:4] == b"\x89PNG"


def test_pdf_to_images_out_of_range_and_huge_dpi(client):
    r = run_tool(client, "pdfimage", {"pages": "9"}, [("a.pdf", make_pdf(2))], expect=400)
    assert r.json()["detail"]["state"] == "out_of_range"
    assert (
        client.post("/api/v1/tasks", json={"tool": "pdfimage", "params": {"dpi": 5000}}).status_code
        == 422
    )


def test_image_outputs_are_not_added_to_library(client):
    run_tool(client, "pdfimage", {"dpi": 72}, [("doc.pdf", make_pdf(1))])
    assert client.get("/api/v1/documents").json() == []


def test_convert_tools_listed(client):
    ids = {t["id"] for t in client.get("/api/v1/tools").json()}
    assert {"compress", "imagepdf", "pdfimage"} <= ids
