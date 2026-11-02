import io

import pytest
from PIL import Image, ImageCms, PngImagePlugin, features

from tests.helpers import outputs, run_tool


def img_bytes(img: Image.Image, fmt: str, **kw) -> bytes:
    buf = io.BytesIO()
    img.save(buf, fmt, **kw)
    return buf.getvalue()


def clean(client, files, expect=200):
    return run_tool(client, "imageclean", {}, files, expect=expect)


def decode(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.load()
    return img


def dirty_exif(orientation: int | None = 6) -> Image.Exif:
    exif = Image.Exif()
    exif[0x010F] = "SecretMaker"
    exif[0x0110] = "SecretCamera"
    exif[0x0132] = "2020:01:02 03:04:05"
    if orientation:
        exif[0x0112] = orientation
    gps = exif.get_ifd(0x8825)
    gps[1] = "N"
    gps[2] = (40.0, 26.0, 46.0)
    return exif


def asym(size=(30, 10)) -> Image.Image:
    img = Image.new("RGB", size, (0, 0, 255))
    img.paste((255, 0, 0), (0, 0, size[0] // 2, size[1]))  # left half red
    return img


ICC = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def test_jpeg_exif_gps_removed_rotated_icc_kept(client):
    src = img_bytes(
        asym(), "JPEG", exif=dirty_exif(6), icc_profile=ICC, comment=b"SecretComment",
        xmp=b"<x:xmpmeta>SecretXmp</x:xmpmeta>",
    )
    assert len(decode(src).getexif()) > 0
    out = clean(client, [("p.jpg", src, "image/jpeg")]).content
    res = decode(out)
    assert res.format == "JPEG"
    assert len(res.getexif()) == 0
    assert b"Exif" not in out
    for secret in (b"SecretMaker", b"SecretCamera", b"SecretComment", b"SecretXmp", b"GPS"):
        assert secret not in out
    # orientation 6 = rotate 90 cw: 30x10 -> 10x30, left (red) half becomes the top
    assert res.size == (10, 30)
    r_top, _, b_top = res.getpixel((5, 3))
    r_bot, _, b_bot = res.getpixel((5, 26))
    assert r_top > 200 and b_top < 60 and r_bot < 60 and b_bot > 200
    assert res.info.get("icc_profile") == ICC


def test_jpeg_without_orientation_keeps_quantization(client):
    src = img_bytes(Image.effect_noise((64, 64), 60).convert("RGB"), "JPEG", quality=60,
                    exif=dirty_exif(None))
    res = decode(clean(client, [("p.jpg", src, "image/jpeg")]).content)
    assert res.quantization == decode(src).quantization
    assert len(res.getexif()) == 0


def test_jpeg_cleaned_is_progressive(client):
    src = img_bytes(asym(), "JPEG", exif=dirty_exif(None))
    res = decode(clean(client, [("p.jpg", src, "image/jpeg")]).content)
    assert res.info.get("progressive") or res.info.get("progression")


def test_png_text_chunks_gone_icc_kept(client):
    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "SecretAuthor")
    info.add_itxt("Description", "SecretItxt")
    info.add_text("Comment", "SecretText", zip=True)
    src = img_bytes(asym(), "PNG", pnginfo=info, icc_profile=ICC, exif=dirty_exif(None))
    assert b"SecretAuthor" in src and b"SecretItxt" in src
    out = clean(client, [("p.png", src, "image/png")]).content
    res = decode(out)
    assert res.format == "PNG" and res.size == (30, 10)
    assert b"tEXt" not in out and b"iTXt" not in out and b"zTXt" not in out
    assert b"eXIf" not in out
    assert b"Secret" not in out
    assert res.info.get("icc_profile") == ICC
    assert res.getpixel((2, 2)) == (255, 0, 0)  # lossless


def test_png_transparency_kept(client):
    src = img_bytes(Image.new("RGBA", (10, 10), (0, 0, 0, 0)), "PNG")
    res = decode(clean(client, [("t.png", src, "image/png")]).content)
    assert res.convert("RGBA").getpixel((3, 3))[3] == 0


def test_webp_cleaned(client):
    src = img_bytes(asym(), "WEBP", exif=dirty_exif(6), icc_profile=ICC)
    out = clean(client, [("p.webp", src, "image/webp")]).content
    res = decode(out)
    assert res.format == "WEBP" and res.size == (10, 30)
    assert len(res.getexif()) == 0 and b"EXIF" not in out and b"SecretMaker" not in out
    assert res.info.get("icc_profile") == ICC


def test_avif_cleaned_when_supported(client):
    if not features.check("avif"):
        pytest.skip("AVIF not available")
    src = img_bytes(asym(), "AVIF", exif=dirty_exif(6))
    res = decode(clean(client, [("p.avif", src, "image/avif")]).content)
    assert res.format == "AVIF" and res.size == (10, 30)
    assert len(res.getexif()) == 0


@pytest.mark.parametrize("fmt", ["GIF", "BMP", "TIFF"])
def test_other_static_formats_become_png(client, fmt):
    src = img_bytes(asym().convert("RGB"), fmt)
    res = decode(clean(client, [("p." + fmt.lower(), src, "image/x")]).content)
    assert res.format == "PNG" and res.size == (30, 10)


def test_tiff_metadata_removed(client):
    tiff = img_bytes(asym(), "TIFF", exif=dirty_exif(None))
    out = clean(client, [("p.tif", tiff, "image/tiff")]).content
    assert b"SecretMaker" not in out and len(decode(out).getexif()) == 0


def test_cleaned_bytes_returned_even_if_bigger(client):
    src = img_bytes(Image.new("RGB", (8, 8), "red"), "PNG")
    out = clean(client, [("p.png", src, "image/png")])
    assert out.content != src and decode(out.content).format == "PNG"


def test_animated_gif_rejected(client):
    frames = [Image.new("RGB", (10, 10), "red"), Image.new("RGB", (10, 10), "blue")]
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=100)
    r = clean(client, [("a.gif", buf.getvalue(), "image/gif")], expect=400)
    assert r.json()["detail"]["state"] == "unsupported"


def test_corrupt_rejected_at_upload(client):
    t = client.post("/api/v1/tasks", json={"tool": "imageclean", "params": {}})
    r = client.post(
        f"/api/v1/tasks/{t.json()['id']}/files", files={"file": ("x.jpg", b"nope", "image/jpeg")}
    )
    assert r.status_code == 422


def test_duplicate_output_names_unique(client):
    a = img_bytes(Image.new("RGB", (8, 8), "red"), "PNG")
    b = img_bytes(Image.new("RGB", (8, 8), "blue"), "PNG")
    names = [n for n, _ in outputs(clean(client, [("x.png", a, "image/png"),
                                                   ("x.png", b, "image/png")]))]
    assert len(names) == len(set(names)) == 2


def test_tool_listed_without_params(client):
    t = {t["id"]: t for t in client.get("/api/v1/tools").json()}["imageclean"]
    assert t["group"] == "images"
    assert not t["params_schema"].get("properties")
    assert t["description"] == "Strips hidden data such as location, camera and date."
