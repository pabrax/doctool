import io

import pytest
from PIL import Image, features

from doctool.tools import imagecore
from tests.helpers import outputs, run_tool


def img_bytes(img: Image.Image, fmt: str, **kw) -> bytes:
    buf = io.BytesIO()
    img.save(buf, fmt, **kw)
    return buf.getvalue()


def convert(client, files, **params):
    return run_tool(client, "imageconvert", params, files)


def decode(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.load()
    return img


def exif_with_gps(orientation: int | None = None) -> Image.Exif:
    exif = Image.Exif()
    exif[0x010F] = "TestMaker"
    if orientation:
        exif[0x0112] = orientation
    exif.get_ifd(0x8825)[1] = "N"  # GPSLatitudeRef
    return exif


def has_gps(data: bytes) -> bool:
    return bool(Image.open(io.BytesIO(data)).getexif().get_ifd(0x8825))


# (a) round trips -------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("src", "target", "mime"),
    [
        ("PNG", "jpg", "JPEG"),
        ("JPEG", "png", "PNG"),
        ("PNG", "webp", "WEBP"),
        ("WEBP", "png", "PNG"),
        ("JPEG", "webp", "WEBP"),
        ("WEBP", "jpg", "JPEG"),
    ],
)
def test_convert_between_formats(client, src, target, mime):
    data = img_bytes(Image.new("RGB", (40, 30), (10, 200, 30)), src)
    out = convert(client, [("a." + src.lower(), data, "image/x")], format=target)
    img = decode(out.content)
    assert img.format == mime and img.size == (40, 30)


def test_output_name_uses_new_extension(client):
    data = img_bytes(Image.new("RGB", (8, 8)), "PNG")
    out = convert(client, [("photo.png", data, "image/png")], format="jpg")
    assert "photo.jpg" in out.headers["content-disposition"]


# (b) transparency ------------------------------------------------------------------------
def test_transparent_png_flattened_on_background_for_jpeg(client):
    data = img_bytes(Image.new("RGBA", (20, 20), (0, 0, 0, 0)), "PNG")
    out = convert(client, [("t.png", data, "image/png")], format="jpg", background="#ff0000")
    r, g, b = decode(out.content).convert("RGB").getpixel((10, 10))
    assert r > 240 and g < 15 and b < 15


def test_transparency_kept_for_png_and_webp(client):
    data = img_bytes(Image.new("RGBA", (20, 20), (0, 0, 0, 0)), "PNG")
    for target in ("png", "webp"):
        out = convert(client, [("t.png", data, "image/png")], format=target)
        assert decode(out.content).convert("RGBA").getpixel((5, 5))[3] == 0


def test_palette_with_transparency_flattened(client):
    p = Image.new("P", (10, 10), 0)
    p.putpalette([0, 0, 255] * 256)
    data = img_bytes(p, "PNG", transparency=0)
    out = convert(client, [("p.png", data, "image/png")], format="jpg", background="#00ff00")
    r, g, b = decode(out.content).getpixel((5, 5))
    assert g > 240 and r < 15 and b < 15


# (c) odd modes ---------------------------------------------------------------------------
def test_cmyk_jpeg_converts(client):
    data = img_bytes(Image.new("CMYK", (16, 16), (0, 255, 255, 0)), "JPEG")
    for target in ("png", "jpg", "webp"):
        out = convert(client, [("c.jpg", data, "image/jpeg")], format=target)
        assert decode(out.content).size == (16, 16)


def test_16bit_png_converts(client):
    data = img_bytes(Image.new("I;16", (16, 16), 40000), "PNG")
    for target in ("png", "jpg", "webp"):
        out = convert(client, [("g.png", data, "image/png")], format=target)
        assert decode(out.content).size == (16, 16)


# (d) metadata and orientation ------------------------------------------------------------
def test_exif_gps_dropped_by_default_and_kept_on_request(client):
    src = img_bytes(Image.new("RGB", (16, 16), "gray"), "JPEG", exif=exif_with_gps())
    assert has_gps(src)
    dropped = convert(client, [("e.jpg", src, "image/jpeg")], format="jpg")
    assert not has_gps(dropped.content)
    assert not Image.open(io.BytesIO(dropped.content)).getexif().get(0x010F)
    kept = convert(client, [("e.jpg", src, "image/jpeg")], format="jpg", keep_metadata=True)
    assert has_gps(kept.content)


def test_orientation_applied_to_pixels(client):
    img = Image.new("RGB", (30, 10), "white")
    src = img_bytes(img, "JPEG", exif=exif_with_gps(orientation=6))  # rotate 90 cw
    for keep in (False, True):
        out = convert(client, [("o.jpg", src, "image/jpeg")], format="png", keep_metadata=keep)
        res = decode(out.content)
        assert res.size == (10, 30)
        assert res.getexif().get(0x0112) in (None, 1)


def test_icc_profile_kept(client):
    from PIL import ImageCms

    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    src = img_bytes(Image.new("RGB", (8, 8)), "PNG", icc_profile=icc)
    out = convert(client, [("i.png", src, "image/png")], format="jpg")
    assert Image.open(io.BytesIO(out.content)).info.get("icc_profile") == icc


# (e) animated ----------------------------------------------------------------------------
def test_animated_gif_rejected(client):
    frames = [Image.new("RGB", (10, 10), "red"), Image.new("RGB", (10, 10), "blue")]
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=100)
    assert Image.open(io.BytesIO(buf.getvalue())).n_frames == 2
    r = run_tool(
        client, "imageconvert", {"format": "png"}, [("a.gif", buf.getvalue(), "image/gif")],
        expect=400,
    )
    assert r.json()["detail"]["state"] == "unsupported"


def test_single_frame_gif_ok(client):
    data = img_bytes(Image.new("P", (10, 10), 1), "GIF")
    out = convert(client, [("a.gif", data, "image/gif")], format="png")
    assert decode(out.content).format == "PNG"


# (f) limits and damage -------------------------------------------------------------------
def test_image_over_max_pixels_rejected(client, monkeypatch):
    data = img_bytes(Image.new("RGB", (50, 50)), "PNG")
    monkeypatch.setattr("doctool.tools.imageutil.IMAGE_MAX_PIXELS", 100)
    t = client.post("/api/v1/tasks", json={"tool": "imageconvert", "params": {"format": "png"}})
    r = client.post(
        f"/api/v1/tasks/{t.json()['id']}/files", files={"file": ("b.png", data, "image/png")}
    )
    assert r.status_code == 422


def test_load_image_rejects_too_large_and_truncated(monkeypatch):
    from doctool.tools.base import ToolError

    data = img_bytes(Image.new("RGB", (50, 50)), "PNG")
    monkeypatch.setattr("doctool.tools.imageutil.IMAGE_MAX_PIXELS", 100)
    with pytest.raises(ToolError) as too_big:
        imagecore.load_image(data, "big.png")
    assert too_big.value.state == "too_large"
    monkeypatch.undo()
    noisy = img_bytes(Image.effect_noise((200, 200), 80).convert("RGB"), "PNG")
    with pytest.raises(ToolError) as exc:
        imagecore.load_image(noisy[: len(noisy) // 2], "cut.png")
    assert exc.value.state == "damaged"


def test_truncated_file_via_api_rejected_at_upload(client):
    noisy = img_bytes(Image.effect_noise((200, 200), 80).convert("RGB"), "PNG")
    t = client.post("/api/v1/tasks", json={"tool": "imageconvert", "params": {"format": "png"}})
    r = client.post(
        f"/api/v1/tasks/{t.json()['id']}/files",
        files={"file": ("cut.png", noisy[: len(noisy) // 2], "image/png")},
    )
    assert r.status_code == 422


# (g) AVIF --------------------------------------------------------------------------------
def test_available_formats_matches_install():
    fmts = imagecore.available_formats()
    assert {"png", "jpeg", "webp"} <= set(fmts)
    assert ("avif" in fmts) == bool(features.check("avif"))


def test_avif_hidden_when_unsupported(monkeypatch):
    import importlib

    from doctool.tools import imageconvert

    real = features.check
    monkeypatch.setattr(features, "check", lambda f: False if f == "avif" else real(f))
    assert "avif" not in imagecore.available_formats()
    try:
        importlib.reload(imageconvert)  # the enum is built at import time
        enum = imageconvert.ImageConvertParams.model_json_schema()["properties"]["format"]["enum"]
        assert "avif" not in enum
        assert {"jpg", "png", "webp"} <= set(enum)
    finally:
        monkeypatch.undo()
        importlib.reload(imageconvert)  # restore the real registration


def test_avif_roundtrip_when_supported(client):
    if not features.check("avif"):
        pytest.skip("AVIF not available")
    data = img_bytes(Image.new("RGB", (16, 16), "red"), "PNG")
    out = convert(client, [("a.png", data, "image/png")], format="avif")
    assert decode(out.content).format == "AVIF"


# (h) duplicates --------------------------------------------------------------------------
def test_duplicate_output_names_get_suffix(client):
    a = img_bytes(Image.new("RGB", (8, 8), "red"), "PNG")
    b = img_bytes(Image.new("RGB", (8, 8), "blue"), "JPEG")
    out = convert(
        client, [("x.png", a, "image/png"), ("x.jpg", b, "image/jpeg")], format="webp"
    )
    names = [n for n, _ in outputs(out)]
    assert len(names) == len(set(names)) == 2


def test_output_name_sanitized():
    name = imagecore.output_name("..\\..//evil/na me.png", "jpeg")
    assert "/" not in name and "\\" not in name and name.endswith(".jpg")


# (i) registry ----------------------------------------------------------------------------
def test_tool_listed_with_target_enum(client):
    tools = {t["id"]: t for t in client.get("/api/v1/tools").json()}
    t = tools["imageconvert"]
    assert t["group"] == "images"
    assert t["params_schema"]["properties"]["format"]["enum"] == [
        "jpg" if f == "jpeg" else f for f in imagecore.available_formats()
    ]


def test_params_validation(client):
    for params in ({"format": "bmp"}, {"format": "png", "quality": 0},
                   {"format": "png", "background": "red"}):
        assert client.post("/api/v1/tasks", json={"tool": "imageconvert", "params": params}
                           ).status_code == 422
