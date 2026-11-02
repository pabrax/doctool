import io

import pytest
from PIL import Image, features

from doctool.tools.base import ToolError
from tests.helpers import outputs, run_tool


def img_bytes(img: Image.Image, fmt: str, **kw) -> bytes:
    buf = io.BytesIO()
    img.save(buf, fmt, **kw)
    return buf.getvalue()


def resize(client, files, **params):
    return run_tool(client, "imageresize", params, files)


def decode(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.load()
    return img


def png(size=(400, 200), color="red") -> bytes:
    return img_bytes(Image.new("RGB", size, color), "PNG")


def one(client, data, name="a.png", **params):
    return resize(client, [(name, data, "image/x")], **params)


def exif_with_gps(orientation: int | None = None) -> Image.Exif:
    exif = Image.Exif()
    exif[0x010F] = "TestMaker"
    if orientation:
        exif[0x0112] = orientation
    exif.get_ifd(0x8825)[1] = "N"
    return exif


def has_gps(data: bytes) -> bool:
    return bool(Image.open(io.BytesIO(data)).getexif().get_ifd(0x8825))


# modes -----------------------------------------------------------------------------------
def test_fit_box_width_only_keeps_aspect(client):
    out = one(client, png(), mode="fit_box", width=100)
    assert decode(out.content).size == (100, 50)


def test_fit_box_both_sides_fits_inside(client):
    out = one(client, png(), mode="fit_box", width=300, height=50)
    assert decode(out.content).size == (100, 50)


def test_default_is_fit_box_1920_never_enlarges(client):
    out = one(client, png((400, 200)))
    assert decode(out.content).size == (400, 200)
    big = img_bytes(Image.new("RGB", (4000, 2000), "blue"), "PNG")
    assert decode(one(client, big).content).size == (1920, 960)


def test_exact_changes_proportions(client):
    out = one(client, png(), mode="exact", width=100, height=100)
    assert decode(out.content).size == (100, 100)


def test_exact_requires_height(client):
    t = client.post(
        "/api/v1/tasks", json={"tool": "imageresize", "params": {"mode": "exact", "width": 10}}
    )
    assert t.status_code == 422


def test_exact_never_enlarges_each_dimension(client):
    out = one(client, png((400, 200)), mode="exact", width=1000, height=100)
    assert decode(out.content).size == (400, 100)


def test_percent(client):
    out = one(client, png(), mode="percent", percent=25)
    assert decode(out.content).size == (100, 50)
    out = one(client, png(), mode="percent", percent=100)
    assert decode(out.content).size == (400, 200)


def test_percent_tiny_image_keeps_at_least_one_pixel(client):
    out = one(client, png((3, 3)), mode="percent", percent=1)
    assert decode(out.content).size == (1, 1)


# formats ---------------------------------------------------------------------------------
@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_format_kept(client, fmt):
    data = img_bytes(Image.new("RGB", (200, 100), "green"), fmt)
    out = one(client, data, "p." + fmt.lower(), width=100)
    img = decode(out.content)
    assert img.format == fmt and img.size == (100, 50)


def test_avif_kept_when_supported(client):
    if not features.check("avif"):
        pytest.skip("AVIF not available")
    data = img_bytes(Image.new("RGB", (200, 100), "green"), "AVIF")
    out = one(client, data, "p.avif", width=100)
    assert decode(out.content).format == "AVIF"


@pytest.mark.parametrize("fmt", ["GIF", "BMP", "TIFF"])
def test_other_formats_become_png(client, fmt):
    data = img_bytes(Image.new("RGB", (200, 100), "green").quantize(8), fmt)
    out = one(client, data, "p." + fmt.lower(), width=100)
    assert decode(out.content).format == "PNG"
    assert "p.png" in out.headers["content-disposition"]


def test_jpeg_quality_90(client):
    noise = Image.effect_noise((300, 300), 60).convert("RGB")
    data = img_bytes(noise, "JPEG", quality=100)
    out = one(client, data, "n.jpg", mode="percent", percent=100)
    ref = img_bytes(decode(data), "JPEG", quality=90, optimize=True, progressive=True)
    assert len(out.content) == len(ref)


def test_transparency_kept(client):
    data = img_bytes(Image.new("RGBA", (100, 100), (0, 0, 0, 0)), "PNG")
    out = one(client, data, "t.png", width=50)
    res = decode(out.content)
    assert res.mode == "RGBA" and res.getpixel((5, 5))[3] == 0


# metadata --------------------------------------------------------------------------------
def test_exif_stripped_and_orientation_applied(client):
    src = img_bytes(
        Image.new("RGB", (300, 100), "white"), "JPEG", exif=exif_with_gps(orientation=6)
    )
    assert has_gps(src)
    out = one(client, src, "e.jpg", mode="percent", percent=50)
    assert not has_gps(out.content)
    res = decode(out.content)
    assert res.size == (50, 150)
    assert res.getexif().get(0x0112) in (None, 1)


def test_icc_profile_kept(client):
    from PIL import ImageCms

    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    src = img_bytes(Image.new("RGB", (100, 100)), "PNG", icc_profile=icc)
    out = one(client, src, "i.png", width=50)
    assert decode(out.content).info.get("icc_profile") == icc


# rejection -------------------------------------------------------------------------------
def test_animated_gif_rejected(client):
    frames = [Image.new("RGB", (10, 10), "red"), Image.new("RGB", (10, 10), "blue")]
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=100)
    r = run_tool(
        client, "imageresize", {}, [("a.gif", buf.getvalue(), "image/gif")], expect=400
    )
    assert r.json()["detail"]["state"] == "unsupported"


def test_corrupt_rejected_at_upload(client):
    t = client.post("/api/v1/tasks", json={"tool": "imageresize", "params": {}})
    r = client.post(
        f"/api/v1/tasks/{t.json()['id']}/files",
        files={"file": ("bad.png", b"not an image", "image/png")},
    )
    assert r.status_code == 422


def test_output_pixels_hard_cap(monkeypatch):
    from doctool.tools import imageresize, imageutil
    from doctool.tools.base import ToolInput

    monkeypatch.setattr(imageutil, "IMAGE_MAX_PIXELS", 100)
    monkeypatch.setattr(imageresize, "preflight", lambda inputs: None)
    tool = imageresize.ImageResizeTool()
    with pytest.raises(ToolError):
        tool.run([ToolInput("a.png", png((50, 50)))], imageresize.ImageResizeParams())


def test_duplicate_output_names_get_suffix(client):
    out = resize(client, [("x.png", png(), "image/png"), ("x.png", png(), "image/png")])
    names = [n for n, _ in outputs(out)]
    assert len(names) == len(set(names)) == 2


# registry and params ---------------------------------------------------------------------
def test_tool_listed_with_schema(client):
    tools = {t["id"]: t for t in client.get("/api/v1/tools").json()}
    t = tools["imageresize"]
    assert t["group"] == "images"
    props = t["params_schema"]["properties"]
    assert set(props) == {"mode", "width", "height", "percent"}
    assert props["mode"]["enum"] == ["fit_box", "exact", "percent"]
    assert props["mode"]["default"] == "fit_box"
    assert props["width"]["default"] == 1920 and props["width"]["minimum"] == 1
    assert props["percent"]["default"] == 50
    assert props["percent"]["minimum"] == 1 and props["percent"]["maximum"] == 100
    assert "never enlarged" in props["width"]["description"]
    assert "proportions" in props["height"]["description"]


def test_params_validation(client):
    for params in (
        {"mode": "fit"},
        {"width": 0},
        {"height": 0},
        {"percent": 0},
        {"percent": 101},
        {"width": "abc"},
    ):
        assert client.post(
            "/api/v1/tasks", json={"tool": "imageresize", "params": params}
        ).status_code == 422
