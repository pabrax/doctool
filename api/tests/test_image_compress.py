import io

import pytest
from PIL import Image, features

from tests.helpers import outputs, run_tool


def img_bytes(img: Image.Image, fmt: str, **kw) -> bytes:
    buf = io.BytesIO()
    img.save(buf, fmt, **kw)
    return buf.getvalue()


def compress(client, files, **params):
    return run_tool(client, "imagecompress", params, files)


def decode(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.load()
    return img


def noisy(size: tuple[int, int]) -> Image.Image:
    return Image.effect_noise(size, 60).convert("RGB")


def exif_with_gps(orientation: int | None = None) -> Image.Exif:
    exif = Image.Exif()
    exif[0x010F] = "TestMaker"
    if orientation:
        exif[0x0112] = orientation
    exif.get_ifd(0x8825)[1] = "N"
    return exif


def has_gps(data: bytes) -> bool:
    return bool(Image.open(io.BytesIO(data)).getexif().get_ifd(0x8825))


@pytest.mark.parametrize(("preset", "cap"), [("web", 2560), ("email", 1600), ("max", 1280)])
def test_presets_cap_longest_side_and_shrink(client, preset, cap):
    src = img_bytes(noisy((3000, 1500)), "JPEG", quality=98)
    out = compress(client, [("p.jpg", src, "image/jpeg")], preset=preset)
    img = decode(out.content)
    assert img.format == "JPEG"
    assert img.size == (cap, cap // 2)
    assert len(out.content) < len(src)


def test_default_preset_is_web(client):
    src = img_bytes(noisy((3000, 1000)), "JPEG", quality=98)
    out = compress(client, [("p.jpg", src, "image/jpeg")])
    assert decode(out.content).size == (2560, 853)


def test_quality_orders_presets(client):
    src = img_bytes(noisy((1200, 1200)), "JPEG", quality=98)
    sizes = {
        p: len(compress(client, [("p.jpg", src, "image/jpeg")], preset=p).content)
        for p in ("web", "email", "max")
    }
    assert sizes["web"] > sizes["email"] > sizes["max"]


def test_never_enlarged(client):
    src = img_bytes(noisy((400, 300)), "JPEG", quality=98)
    out = compress(client, [("p.jpg", src, "image/jpeg")], preset="max")
    assert decode(out.content).size == (400, 300)


def test_jpeg_is_progressive(client):
    src = img_bytes(noisy((300, 300)), "JPEG", quality=98)
    out = compress(client, [("p.jpg", src, "image/jpeg")])
    assert decode(out.content).info.get("progressive") or decode(out.content).info.get(
        "progression"
    )


def test_png_stays_png_and_lossless(client):
    img = noisy((200, 200))
    src = img_bytes(img, "PNG", compress_level=0)
    out = compress(client, [("p.png", src, "image/png")], preset="max")
    res = decode(out.content)
    assert res.format == "PNG" and len(out.content) < len(src)
    assert res.convert("RGB").tobytes() == img.tobytes()


def test_webp_stays_webp(client):
    src = img_bytes(noisy((300, 300)), "WEBP", quality=100)
    out = compress(client, [("p.webp", src, "image/webp")], preset="email")
    assert decode(out.content).format == "WEBP" and len(out.content) < len(src)


def test_avif_stays_avif_when_supported(client):
    if not features.check("avif"):
        pytest.skip("AVIF not available")
    src = img_bytes(noisy((300, 300)), "AVIF", quality=100)
    out = compress(client, [("p.avif", src, "image/avif")], preset="email")
    assert decode(out.content).format == "AVIF"


@pytest.mark.parametrize("fmt", ["GIF", "BMP", "TIFF"])
def test_other_formats_become_png(client, fmt):
    img = noisy((600, 600))
    src = img_bytes(img.quantize(64) if fmt == "GIF" else img, fmt)
    out = compress(client, [("p." + fmt.lower(), src, "image/x")])
    if out.content == src:  # never-grow fallback keeps the original file and name
        assert "p." + fmt.lower() in out.headers["content-disposition"]
    else:
        assert decode(out.content).format == "PNG"
        assert "p.png" in out.headers["content-disposition"]


def test_never_grow_returns_original_bytes_and_name(client):
    src = img_bytes(Image.new("RGB", (8, 8), "red"), "PNG", optimize=True)
    out = compress(client, [("Tiny One.png", src, "image/png")])
    assert out.content == src
    assert "Tiny One.png" in out.headers["content-disposition"]


def test_gif_is_never_returned_as_is(client):
    # GIF is converted to PNG, so the original bytes are never handed back (they may hold XMP)
    src = img_bytes(Image.new("P", (4, 4), 1), "GIF")
    out = compress(client, [("tiny.gif", src, "image/gif")])
    assert out.content != src and out.content[:4] == b"PNG"
    assert "tiny.png" in out.headers["content-disposition"]


def test_transparent_png_stays_transparent(client):
    img = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    img.paste(noisy((100, 100)), (100, 100))
    src = img_bytes(img, "PNG", compress_level=0)
    out = compress(client, [("t.png", src, "image/png")])
    res = decode(out.content)
    assert res.mode == "RGBA" and res.getpixel((5, 5))[3] == 0


def test_exif_gps_stripped_and_orientation_applied(client):
    src = img_bytes(
        noisy((600, 200)), "JPEG", quality=98, exif=exif_with_gps(orientation=6)
    )
    assert has_gps(src)
    out = compress(client, [("e.jpg", src, "image/jpeg")])
    assert not has_gps(out.content)
    res = decode(out.content)
    assert res.size == (200, 600)
    assert res.getexif().get(0x0112) in (None, 1)


def test_icc_profile_kept(client):
    from PIL import ImageCms

    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    src = img_bytes(noisy((300, 300)), "JPEG", quality=98, icc_profile=icc)
    out = compress(client, [("i.jpg", src, "image/jpeg")])
    assert decode(out.content).info.get("icc_profile") == icc


def test_animated_gif_rejected(client):
    frames = [Image.new("RGB", (10, 10), "red"), Image.new("RGB", (10, 10), "blue")]
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=100)
    r = run_tool(
        client, "imagecompress", {}, [("a.gif", buf.getvalue(), "image/gif")], expect=400
    )
    assert r.json()["detail"]["state"] == "unsupported"


def test_corrupt_rejected_at_upload(client):
    t = client.post("/api/v1/tasks", json={"tool": "imagecompress", "params": {}})
    r = client.post(
        f"/api/v1/tasks/{t.json()['id']}/files",
        files={"file": ("bad.png", b"not an image", "image/png")},
    )
    assert r.status_code == 422


def test_duplicate_output_names_get_suffix(client):
    a = img_bytes(noisy((300, 300)), "PNG", compress_level=0)
    b = img_bytes(noisy((300, 300)), "PNG", compress_level=0)
    out = compress(client, [("x.png", a, "image/png"), ("x.png", b, "image/png")])
    names = [n for n, _ in outputs(out)]
    assert len(names) == len(set(names)) == 2


def test_tool_listed_with_preset_schema(client):
    tools = {t["id"]: t for t in client.get("/api/v1/tools").json()}
    t = tools["imagecompress"]
    assert t["group"] == "images"
    assert t["description"] == "Make photos lighter to share or upload."
    prop = t["params_schema"]["properties"]["preset"]
    assert prop["enum"] == ["web", "email", "max"] and prop["default"] == "web"
    assert prop["description"] == "We never return a file bigger than the original."


def test_params_validation(client):
    for params in ({"preset": "tiny"}, {"preset": 3}):
        assert client.post(
            "/api/v1/tasks", json={"tool": "imagecompress", "params": params}
        ).status_code == 422
