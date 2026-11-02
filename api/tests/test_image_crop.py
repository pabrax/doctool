import io

import pytest
from PIL import Image, features

from tests.helpers import outputs, run_tool


def img_bytes(img: Image.Image, fmt: str, **kw) -> bytes:
    buf = io.BytesIO()
    img.save(buf, fmt, **kw)
    return buf.getvalue()


def crop(client, files, expect=200, **params):
    return run_tool(client, "imagecrop", params, files, expect=expect)


def decode(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.load()
    return img


def exif_with(orientation: int | None = None) -> Image.Exif:
    exif = Image.Exif()
    exif[0x010F] = "TestMaker"
    if orientation:
        exif[0x0112] = orientation
    exif.get_ifd(0x8825)[1] = "N"
    return exif


# ratio mode ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("ratio", "size", "expected"),
    [
        ("1-1", (400, 300), (300, 300)),
        ("4-3", (400, 400), (400, 300)),
        ("3-2", (400, 300), (400, 266)),
        ("16-9", (320, 320), (320, 180)),
        ("16-9", (300, 160), (284, 160)),
    ],
)
def test_ratio_sizes_every_enum(client, ratio, size, expected):
    data = img_bytes(Image.new("RGB", size, "red"), "PNG")
    out = crop(client, [("a.png", data, "image/png")], ratio=ratio)
    assert decode(out.content).size == expected


def test_default_is_centered_square(client):
    img = Image.new("RGB", (40, 20), "black")
    img.paste((255, 0, 0), (10, 0, 30, 20))  # centre 20x20 is red
    out = crop(client, [("a.png", img_bytes(img, "PNG"), "image/png")])
    res = decode(out.content)
    assert res.size == (20, 20)
    assert res.getpixel((0, 0)) == (255, 0, 0) and res.getpixel((19, 19)) == (255, 0, 0)


def test_portrait_uses_portrait_ratio(client):
    data = img_bytes(Image.new("RGB", (300, 400), "red"), "PNG")
    out = crop(client, [("a.png", data, "image/png")], ratio="4-3")
    assert decode(out.content).size == (300, 400)
    data = img_bytes(Image.new("RGB", (300, 600), "red"), "PNG")
    out = crop(client, [("a.png", data, "image/png")], ratio="4-3")
    assert decode(out.content).size == (300, 400)


# box mode --------------------------------------------------------------------------------
def test_box_exact_pixels(client):
    img = Image.new("RGB", (50, 40), "black")
    img.paste((0, 255, 0), (10, 5, 30, 25))
    out = crop(
        client, [("a.png", img_bytes(img, "PNG"), "image/png")],
        mode="box", x=10, y=5, width=20, height=20,
    )
    res = decode(out.content)
    assert res.size == (20, 20)
    assert res.getpixel((0, 0)) == (0, 255, 0) and res.getpixel((19, 19)) == (0, 255, 0)


def test_box_outside_is_out_of_range_with_size(client):
    data = img_bytes(Image.new("RGB", (50, 40)), "PNG")
    r = crop(
        client, [("a.png", data, "image/png")], expect=400,
        mode="box", x=40, y=0, width=20, height=10,
    )
    detail = r.json()["detail"]
    assert detail["state"] == "out_of_range"
    assert "50" in detail["message"] and "40" in detail["message"]


def test_box_missing_size_rejected(client):
    # now rejected when the task is created (pydantic validator), not at process time
    body = {"tool": "imagecrop", "params": {"mode": "box", "width": 10}}
    r = client.post("/api/v1/tasks", json=body)
    assert r.status_code == 422


def test_box_uses_oriented_image(client):
    # stored 30x10 with orientation 6 -> 10x30 after rotation
    src = img_bytes(Image.new("RGB", (30, 10), "white"), "JPEG", exif=exif_with(6))
    out = crop(client, [("o.jpg", src, "image/jpeg")], mode="box", x=0, y=0, width=10, height=30)
    assert decode(out.content).size == (10, 30)
    r = crop(
        client, [("o.jpg", src, "image/jpeg")], expect=400,
        mode="box", x=0, y=0, width=30, height=10,
    )
    assert r.json()["detail"]["state"] == "out_of_range"


# formats ---------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("fmt", "out_fmt"),
    [("PNG", "PNG"), ("JPEG", "JPEG"), ("WEBP", "WEBP"), ("GIF", "PNG"), ("BMP", "PNG"),
     ("TIFF", "PNG")],
)
def test_output_format_follows_input(client, fmt, out_fmt):
    data = img_bytes(Image.new("RGB", (40, 30), "red"), fmt)
    out = crop(client, [("a." + fmt.lower(), data, "image/x")])
    res = decode(out.content)
    assert res.format == out_fmt and res.size == (30, 30)


def test_jpeg_is_progressive(client):
    data = img_bytes(Image.new("RGB", (40, 30), "red"), "JPEG")
    res = decode(crop(client, [("a.jpg", data, "image/jpeg")]).content)
    assert res.info.get("progressive") or res.info.get("progression")


def test_avif_input_when_supported(client):
    if not features.check("avif"):
        pytest.skip("AVIF not available")
    data = img_bytes(Image.new("RGB", (40, 30), "red"), "AVIF")
    assert decode(crop(client, [("a.avif", data, "image/avif")]).content).format == "AVIF"


def test_transparency_kept(client):
    data = img_bytes(Image.new("RGBA", (20, 20), (0, 0, 0, 0)), "PNG")
    res = decode(crop(client, [("t.png", data, "image/png")], ratio="4-3").content)
    assert res.convert("RGBA").getpixel((5, 5))[3] == 0


def test_metadata_stripped_orientation_applied_icc_kept(client):
    from PIL import ImageCms

    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    src = img_bytes(Image.new("RGB", (40, 20), "white"), "JPEG", exif=exif_with(6), icc_profile=icc)
    res = decode(crop(client, [("o.jpg", src, "image/jpeg")]).content)
    assert res.size == (20, 20)
    assert not len(res.getexif())
    assert res.info.get("icc_profile") == icc


# rejects ---------------------------------------------------------------------------------
def test_animated_gif_rejected(client):
    frames = [Image.new("RGB", (10, 10), "red"), Image.new("RGB", (10, 10), "blue")]
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=100)
    r = crop(client, [("a.gif", buf.getvalue(), "image/gif")], expect=400)
    assert r.json()["detail"]["state"] == "unsupported"


def test_corrupt_rejected_at_upload(client):
    t = client.post("/api/v1/tasks", json={"tool": "imagecrop", "params": {}})
    r = client.post(
        f"/api/v1/tasks/{t.json()['id']}/files", files={"file": ("x.png", b"nope", "image/png")}
    )
    assert r.status_code == 422


def test_duplicate_output_names_unique(client):
    a = img_bytes(Image.new("RGB", (8, 8), "red"), "PNG")
    b = img_bytes(Image.new("RGB", (8, 8), "blue"), "PNG")
    out = crop(client, [("x.png", a, "image/png"), ("x.png", b, "image/png")])
    names = [n for n, _ in outputs(out)]
    assert len(names) == len(set(names)) == 2


# registry and params ---------------------------------------------------------------------
def test_tool_listed_with_schema(client):
    t = {t["id"]: t for t in client.get("/api/v1/tools").json()}["imagecrop"]
    assert t["group"] == "images"
    props = t["params_schema"]["properties"]
    assert set(props) == {"mode", "ratio", "x", "y", "width", "height"}
    assert props["mode"]["enum"] == ["ratio", "box"]
    assert props["ratio"]["enum"] == ["1-1", "4-3", "3-2", "16-9"]
    assert props["mode"]["default"] == "ratio" and props["ratio"]["default"] == "1-1"


@pytest.mark.parametrize(
    "params",
    [{"mode": "free"}, {"ratio": "5-4"}, {"x": -1}, {"y": -1}, {"width": 0}, {"height": 0}],
)
def test_params_validation(client, params):
    r = client.post("/api/v1/tasks", json={"tool": "imagecrop", "params": params})
    assert r.status_code == 422
