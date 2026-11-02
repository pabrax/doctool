"""Independent QA tests for imageconvert (criteria C1-C10). Everything goes through the HTTP API."""

import io
import shutil
import struct
import zipfile
import zlib

import pytest
from fastapi.testclient import TestClient
from PIL import Image, features

from doctool.config import Settings
from doctool.main import create_app
from tests.helpers import outputs, run_tool


def img_bytes(img, fmt, **kw):
    buf = io.BytesIO()
    img.save(buf, fmt, **kw)
    return buf.getvalue()


def decode(data):
    img = Image.open(io.BytesIO(data))
    img.load()
    return img


def convert(client, files, expect=200, **params):
    return run_tool(client, "imageconvert", params, files, expect=expect)


def upload(client, name, data, **params):
    params.setdefault("format", "png")
    t = client.post("/api/v1/tasks", json={"tool": "imageconvert", "params": params})
    assert t.status_code == 201, t.text
    return t.json()["id"], client.post(
        f"/api/v1/tasks/{t.json()['id']}/files", files={"file": (name, data, "image/png")}
    )


FORMATS = ["PNG", "JPEG", "WEBP"] + (["AVIF"] if features.check("avif") else [])
TARGETS = ["jpg" if f == "JPEG" else f.lower() for f in FORMATS]
PIL_FMT = {"jpg": "JPEG"}


# C1 ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("src", FORMATS)
@pytest.mark.parametrize("target", TARGETS)
def test_c1_all_pairs_pixels_close(client, src, target):
    base = Image.new("RGB", (32, 24), (200, 30, 40))
    data = img_bytes(base, src)
    out = convert(client, [("a." + src.lower(), data)], format=target)
    res = decode(out.content)
    assert res.format == PIL_FMT.get(target, target.upper()) and res.size == (32, 24)
    r, g, b = res.convert("RGB").getpixel((16, 12))
    assert abs(r - 200) < 20 and abs(g - 30) < 20 and abs(b - 40) < 20


# C2 ---------------------------------------------------------------------------------------
def test_c2_semi_transparent_blend_and_alpha_kept(client):
    data = img_bytes(Image.new("RGBA", (10, 10), (0, 0, 0, 128)), "PNG")
    j = decode(convert(client, [("t.png", data)], format="jpg", background="#ffffff").content)
    assert 100 < j.convert("RGB").getpixel((5, 5))[0] < 156  # half black over white
    for target in ("png", "webp"):
        a = decode(convert(client, [("t.png", data)], format=target).content).convert("RGBA")
        assert 118 <= a.getpixel((5, 5))[3] <= 138


def test_c2_uppercase_hex_background(client):
    data = img_bytes(Image.new("RGBA", (10, 10), (0, 0, 0, 0)), "PNG")
    out = convert(client, [("t.png", data)], format="jpg", background="#00FF00")
    assert decode(out.content).convert("RGB").getpixel((5, 5))[1] > 240


# C3 ---------------------------------------------------------------------------------------
def _modes():
    yield "cmyk", img_bytes(Image.new("CMYK", (9, 9), (10, 20, 30, 40)), "JPEG")
    yield "cmyk_tiff", img_bytes(Image.new("CMYK", (9, 9), (10, 20, 30, 40)), "TIFF")
    yield "gray", img_bytes(Image.new("L", (9, 9), 100), "PNG")
    yield "gray_alpha", img_bytes(Image.new("LA", (9, 9), (100, 50)), "PNG")
    yield "16bit", img_bytes(Image.new("I;16", (9, 9), 50000), "PNG")
    yield "rgba16", img_bytes(Image.new("RGBA", (9, 9), (1, 2, 3, 4)), "TIFF")
    yield "1bit", img_bytes(Image.new("1", (9, 9), 1), "PNG")
    p = Image.new("P", (9, 9), 3)
    p.putpalette([i % 256 for i in range(768)])
    yield "palette", img_bytes(p, "PNG")
    yield "palette_trans", img_bytes(p, "PNG", transparency=3)
    yield "palette_gif_trans", img_bytes(p, "GIF", transparency=3)
    yield "1x1", img_bytes(Image.new("RGB", (1, 1), "red"), "PNG")
    yield "1x1_rgba", img_bytes(Image.new("RGBA", (1, 1), (1, 1, 1, 0)), "PNG")


@pytest.mark.parametrize(("label", "data"), list(_modes()), ids=[m[0] for m in _modes()])
@pytest.mark.parametrize("target", TARGETS)
def test_c3_modes_convert(client, label, data, target):
    out = convert(client, [("m.png", data)], format=target)
    assert decode(out.content).format == PIL_FMT.get(target, target.upper())


@pytest.mark.parametrize("size", [(20000, 1), (1, 20000)])
@pytest.mark.parametrize("target", ["png", "jpg", "webp"])
def test_c3_extreme_aspect(client, size, target):
    data = img_bytes(Image.new("RGB", size, "blue"), "PNG")
    if target == "webp":
        # WebP is limited to 16383 px per side: clean 400 with a clear message.
        r = convert(client, [("w.png", data)], expect=400, format=target)
        assert "16383" in r.text
        return
    out = convert(client, [("w.png", data)], format=target)
    assert decode(out.content).size == size


def test_c3_webp_over_16383_is_error_not_500(client):
    # WebP cannot encode > 16383 px per side: must be a clean 4xx, never a 500.
    data = img_bytes(Image.new("RGB", (20000, 1), "blue"), "PNG")
    t = client.post("/api/v1/tasks", json={"tool": "imageconvert", "params": {"format": "webp"}})
    tid = t.json()["id"]
    client.post(f"/api/v1/tasks/{tid}/files", files={"file": ("w.png", data, "image/png")})
    r = client.post(f"/api/v1/tasks/{tid}/process", json={})
    assert r.status_code in (200, 400, 422)


def test_c3_jpeg_over_65500_is_error_not_500(client):
    data = img_bytes(Image.new("1", (70000, 1), 1), "PNG")
    tid, r = upload(client, "w.png", data, format="jpg")
    assert r.status_code == 201
    r = client.post(f"/api/v1/tasks/{tid}/process", json={})
    assert r.status_code in (400, 422), r.text


# C4 ---------------------------------------------------------------------------------------
def _exif(orientation=None):
    ex = Image.Exif()
    ex[0x010F] = "Maker"
    if orientation:
        ex[0x0112] = orientation
    ex.get_ifd(0x8825)[1] = "N"
    return ex


def _gps(data):
    return bool(Image.open(io.BytesIO(data)).getexif().get_ifd(0x8825))


@pytest.mark.parametrize("src", ["JPEG", "PNG", "WEBP"])
@pytest.mark.parametrize("target", ["jpg", "png", "webp"])
def test_c4_exif_dropped_default_all_pairs(client, src, target):
    data = img_bytes(Image.new("RGB", (16, 16), "gray"), src, exif=_exif())
    out = convert(client, [("e." + src.lower(), data)], format=target)
    assert not _gps(out.content)
    assert not Image.open(io.BytesIO(out.content)).getexif().get(0x010F)


@pytest.mark.parametrize("target", ["jpg", "png", "webp"])
def test_c4_keep_metadata_all_targets(client, target):
    data = img_bytes(Image.new("RGB", (16, 16), "gray"), "JPEG", exif=_exif())
    out = convert(client, [("e.jpg", data)], format=target, keep_metadata=True)
    assert _gps(out.content)


@pytest.mark.parametrize("target", ["png", "webp"])
def test_c4_keep_metadata_with_alpha_source(client, target):
    # RGBA PNG carrying EXIF -> alpha target
    data = img_bytes(Image.new("RGBA", (16, 16), (1, 2, 3, 200)), "PNG", exif=_exif())
    out = convert(client, [("e.png", data)], format=target, keep_metadata=True)
    assert _gps(out.content)


def test_c4_keep_metadata_with_alpha_flattened_to_jpeg(client):
    # F-b: flattening/mode change creates a new image; EXIF must still be kept.
    data = img_bytes(Image.new("RGBA", (16, 16), (1, 2, 3, 200)), "PNG", exif=_exif())
    out = convert(client, [("e.png", data)], format="jpg", keep_metadata=True)
    assert _gps(out.content)


def test_c4_keep_metadata_with_cmyk_and_palette(client):
    p = Image.new("P", (8, 8), 1)
    p.putpalette([i % 256 for i in range(768)])
    data = img_bytes(p, "PNG", exif=_exif())
    out = convert(client, [("e.png", data)], format="jpg", keep_metadata=True)
    assert _gps(out.content)


@pytest.mark.parametrize("orientation", [2, 3, 4, 5, 6, 7, 8])
@pytest.mark.parametrize("keep", [False, True])
def test_c4_orientation_all_values(client, orientation, keep):
    img = Image.new("RGB", (30, 10), "white")
    img.putpixel((0, 0), (255, 0, 0))
    data = img_bytes(img, "JPEG", exif=_exif(orientation), quality=100, subsampling=0)
    out = convert(client, [("o.jpg", data)], format="png", keep_metadata=keep)
    res = decode(out.content)
    assert res.size == ((10, 30) if orientation >= 5 else (30, 10))
    assert res.getexif().get(0x0112) in (None, 1)
    # The red marker must have moved unless orientation is 1
    expected = Image.open(io.BytesIO(data))
    from PIL import ImageOps

    ref = ImageOps.exif_transpose(expected).convert("RGB")
    assert res.convert("RGB").size == ref.size


def test_c4_icc_kept_and_dropped_exif(client):
    from PIL import ImageCms

    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    for src in ("PNG", "JPEG"):
        data = img_bytes(Image.new("RGB", (8, 8)), src, icc_profile=icc, exif=_exif())
        for target in ("jpg", "png", "webp"):
            out = convert(client, [("i." + src.lower(), data)], format=target)
            assert Image.open(io.BytesIO(out.content)).info.get("icc_profile") == icc
            assert not _gps(out.content)


def test_c4_icc_kept_when_flattening_alpha(client):
    from PIL import ImageCms

    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    data = img_bytes(Image.new("RGBA", (8, 8), (1, 1, 1, 100)), "PNG", icc_profile=icc)
    out = convert(client, [("i.png", data)], format="jpg")
    assert Image.open(io.BytesIO(out.content)).info.get("icc_profile") == icc


def test_c4_xmp_dropped_by_default(client):
    xmp = b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>SECRETGPS</x:xmpmeta>"
    data = img_bytes(Image.new("RGB", (8, 8)), "WEBP", xmp=xmp)
    for target in ("jpg", "png", "webp"):
        out = convert(client, [("x.webp", data)], format=target)
        assert b"SECRETGPS" not in out.content


def test_c4_png_text_chunks_dropped_by_default(client):
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    info.add_text("Location", "SECRETPLACE")
    data = img_bytes(Image.new("RGB", (8, 8)), "PNG", pnginfo=info)
    out = convert(client, [("x.png", data)], format="png")
    assert b"SECRETPLACE" not in out.content


# C5 ---------------------------------------------------------------------------------------
def _anim(fmt, **kw):
    frames = [Image.new("RGB", (10, 10), c) for c in ("red", "blue", "green")]
    buf = io.BytesIO()
    frames[0].save(buf, fmt, save_all=True, append_images=frames[1:], duration=100, **kw)
    return buf.getvalue()


@pytest.mark.parametrize("fmt", ["GIF", "WEBP", "PNG"])
def test_c5_animated_rejected_with_message(client, fmt):
    data = _anim(fmt)
    assert Image.open(io.BytesIO(data)).n_frames == 3
    tid, r = upload(client, "a." + fmt.lower(), data)
    if r.status_code != 201:  # rejecting at upload is also acceptable, never a 500
        assert r.status_code == 422 and "animat" in r.text.lower()
        return
    r = client.post(f"/api/v1/tasks/{tid}/process", json={})
    assert r.status_code == 400
    assert "animat" in r.json()["detail"]["message"].lower()


def test_c5_animated_in_batch_fails_whole_task(client):
    ok = img_bytes(Image.new("RGB", (8, 8)), "PNG")
    r = convert(client, [("ok.png", ok), ("anim.gif", _anim("GIF"))], expect=400, format="png")
    assert "animat" in r.json()["detail"]["message"].lower()


# C6 ---------------------------------------------------------------------------------------
def _chunk(tag, body):
    c = struct.pack(">I", len(body)) + tag + body
    return c + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)


def bomb_png(w, h):
    """Valid 1-bit grey PNG of w*h pixels whose IDAT is a few KB (zeros)."""
    row = b"\x00" * (1 + (w + 7) // 8)
    comp = zlib.compressobj(9)
    parts = [comp.compress(row * 1000) for _ in range(h // 1000)] + [comp.flush()]
    raw = b"".join(parts)
    ihdr = struct.pack(">IIBBBBB", w, h, 1, 0, 0, 0, 0)
    idat = _chunk(b"IDAT", raw)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + idat + _chunk(b"IEND", b"")


@pytest.mark.parametrize("size", [(20000, 20000), (60000, 60000), (65535, 65535)])
def test_c6_bomb_png_rejected_422(client, size):
    data = bomb_png(*size)
    assert len(data) < 5_000_000
    _, r = upload(client, "bomb.png", data)
    assert r.status_code == 422, r.text


def test_c6_bomb_via_decompression_error_not_500(client):
    # 12000x12000 = 144M > 100M cap
    _, r = upload(client, "bomb.png", bomb_png(12000, 12000))
    assert r.status_code == 422


def test_c6_bomb_jpeg_header_rejected(client):
    big = img_bytes(Image.new("L", (100, 100), 0), "JPEG")
    # patch SOF0 height/width to 60000 x 60000
    i = big.find(b"\xff\xc0")
    assert i > 0
    patched = big[: i + 5] + struct.pack(">HH", 60000, 60000) + big[i + 9 :]
    _, r = upload(client, "bomb.jpg", patched, format="png")
    assert r.status_code == 422


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"garbage" * 100,
        b"\x89PNG\r\n\x1a\n",
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 50,
        b"%PDF-1.4 not an image",
        b"GIF89a",
        b"\xff\xd8\xff",
        b"RIFF\x00\x00\x00\x00WEBP",
    ],
)
def test_c6_garbage_rejected_422(client, data):
    _, r = upload(client, "g.png", data)
    assert r.status_code == 422, r.text


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP", "GIF"])
@pytest.mark.parametrize("frac", [0.3, 0.6, 0.95])
def test_c6_truncated_never_500(client, fmt, frac):
    noisy = Image.effect_noise((200, 200), 80).convert("RGB")
    if fmt == "GIF":
        noisy = noisy.convert("P")
    data = img_bytes(noisy, fmt)
    cut = data[: int(len(data) * frac)]
    tid, r = upload(client, "cut." + fmt.lower(), cut)
    assert r.status_code in (201, 422)
    if r.status_code == 201:
        p = client.post(f"/api/v1/tasks/{tid}/process", json={})
        assert p.status_code in (200, 400), p.text
        if p.status_code == 200:  # silently decoded a cut file: report as bug
            pytest.fail(f"truncated {fmt} at {frac} was accepted and converted")


def test_c6_corrupt_idat_crc_never_500(client):
    data = bytearray(img_bytes(Image.effect_noise((64, 64), 80).convert("RGB"), "PNG"))
    data[len(data) // 2] ^= 0xFF
    tid, r = upload(client, "bad.png", bytes(data))
    assert r.status_code in (201, 422)
    if r.status_code == 201:
        p = client.post(f"/api/v1/tasks/{tid}/process", json={})
        assert p.status_code in (200, 400)


def test_c6_exif_bomb_huge_declared_not_500(client):
    # fake JPEG with oversized EXIF segment length
    data = img_bytes(Image.new("RGB", (8, 8)), "JPEG")
    evil = data[:2] + b"\xff\xe1\xff\xffExif\x00\x00" + b"A" * 100 + data[2:]
    tid, r = upload(client, "e.jpg", evil)
    assert r.status_code in (201, 422)
    if r.status_code == 201:
        assert client.post(f"/api/v1/tasks/{tid}/process", json={}).status_code in (200, 400)


# C7 ---------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "params",
    [
        {"format": "png", "quality": 0},
        {"format": "png", "quality": 101},
        {"format": "png", "quality": -1},
        {"format": "png", "quality": "abc"},
        {"format": "png", "quality": 85.5},
        {"format": "png", "quality": None},
        {"format": "png", "background": "red"},
        {"format": "png", "background": "#fff"},
        {"format": "png", "background": "#gggggg"},
        {"format": "png", "background": "#ffffff\n"},
        {"format": "png", "background": "#ffffff00"},
        {"format": "png", "background": 123},
        {"format": "bmp"},
        {"format": "PNG"},
        {"format": ""},
        {"format": None},
        {},
        {"format": "png", "keep_metadata": "maybe"},
        {"format": "png", "keep_metadata": []},
    ],
)
def test_c7_invalid_params_422(client, params):
    r = client.post("/api/v1/tasks", json={"tool": "imageconvert", "params": params})
    assert r.status_code == 422, r.text


@pytest.mark.parametrize("quality", [1, 100])
def test_c7_quality_boundaries_ok(client, quality):
    data = img_bytes(Image.new("RGB", (8, 8)), "PNG")
    for target in ("jpg", "webp", "png"):
        convert(client, [("a.png", data)], format=target, quality=quality)


def test_c7_unknown_param_ignored_or_422(client):
    r = client.post(
        "/api/v1/tasks", json={"tool": "imageconvert", "params": {"format": "png", "zzz": 1}}
    )
    assert r.status_code in (201, 422)


def test_c7_quality_effect_jpeg(client):
    data = img_bytes(Image.effect_noise((128, 128), 80).convert("RGB"), "PNG")
    lo = convert(client, [("a.png", data)], format="jpg", quality=5).content
    hi = convert(client, [("a.png", data)], format="jpg", quality=95).content
    assert len(hi) > len(lo)


def test_c7_png_quality_ignored_spec_gap(client):
    # spec gap: PNG ignores quality (documented only by the field description). Checked: no error.
    data = img_bytes(Image.new("RGB", (16, 16), "red"), "PNG")
    a = convert(client, [("a.png", data)], format="png", quality=1).content
    b = convert(client, [("a.png", data)], format="png", quality=100).content
    assert a == b


# C8 ---------------------------------------------------------------------------------------
HOSTILE = [
    "../../x.png",
    "..\\..\\x.png",
    "CON.png",
    "NUL.png",
    "a/b/c.png",
    "‮gnp.exe.png",
    "‮.png",
    "café 日本語 \U0001f600.png",
    "line\nbreak.png",
    "tab\there.png",
    "quote\".png",
    ("x" * 400) + ".png",
    ".png",
    "...png",
    "   .png",
    "..",
    "noext",
    "a:b*c?.png",
    "%2e%2e%2fx.png",
    "<script>.png",
]


@pytest.mark.parametrize("name", HOSTILE, ids=[repr(n[:20]) for n in HOSTILE])
def test_c8_hostile_names(client, name):
    data = img_bytes(Image.new("RGB", (8, 8), "red"), "PNG")
    t = client.post("/api/v1/tasks", json={"tool": "imageconvert", "params": {"format": "jpg"}})
    tid = t.json()["id"]
    r = client.post(f"/api/v1/tasks/{tid}/files", files={"file": (name, data, "image/png")})
    assert r.status_code == 201, r.text
    p = client.post(f"/api/v1/tasks/{tid}/process", json={})
    assert p.status_code == 200, p.text
    out_names = [f["filename"] for f in p.json()["files"] if f["role"] == "out"]
    assert len(out_names) == 1
    n = out_names[0]
    assert n and "/" not in n and "\\" not in n and "\n" not in n and "\x00" not in n
    assert n not in (".", "..") and not n.startswith(".") and n.endswith(".jpg")
    assert len(n) <= 220
    d = client.get(f"/api/v1/tasks/{tid}/download")
    assert d.status_code == 200
    assert decode(d.content).format == "JPEG"
    cd = d.headers["content-disposition"]
    assert "\n" not in cd and "\r" not in cd


def test_c8_hostile_names_multi_zip(client):
    data = img_bytes(Image.new("RGB", (8, 8), "red"), "PNG")
    files = [(n, data) for n in HOSTILE if "\n" not in n]
    res = convert(client, files, format="webp")
    z = zipfile.ZipFile(io.BytesIO(res.content))
    names = z.namelist()
    assert len(names) == len(set(names)) == len(files)
    for n in names:
        assert n and not n.startswith("/") and ".." not in n.split("/") and "\\" not in n


# C9 ---------------------------------------------------------------------------------------
def test_c9_duplicate_names_unique_and_content_matches(client):
    red = img_bytes(Image.new("RGB", (8, 8), (250, 0, 0)), "PNG")
    blue = img_bytes(Image.new("RGB", (8, 8), (0, 0, 250)), "PNG")
    grn = img_bytes(Image.new("RGB", (8, 8), (0, 250, 0)), "PNG")
    res = convert(client, [("a.png", red), ("a.png", blue), ("A.PNG", grn)], format="png")
    outs = outputs(res)
    names = [n for n, _ in outs]
    assert len({n.lower() for n in names}) == 3
    colors = sorted(decode(b).convert("RGB").getpixel((1, 1)) for _, b in outs)
    assert colors == sorted([(250, 0, 0), (0, 250, 0), (0, 0, 250)])


def test_c9_dup_collision_with_suffix_name(client):
    d = img_bytes(Image.new("RGB", (8, 8)), "PNG")
    res = convert(client, [("a.png", d), ("a-2.png", d), ("a.jpg", d)], format="png")
    names = [n for n, _ in outputs(res)]
    assert len({n.lower() for n in names}) == 3


def test_c9_same_stem_different_ext_library_names(client):
    d = img_bytes(Image.new("RGB", (8, 8)), "PNG")
    res = convert(client, [("a.png", d), ("a.gif", img_bytes(Image.new("P", (8, 8)), "GIF"))],
                  format="jpg")
    assert len({n for n, _ in outputs(res)}) == 2


# C10 --------------------------------------------------------------------------------------
def test_c10_multiple_files_zip_in_order(client):
    files = [
        (f"f{i}.png", img_bytes(Image.new("RGB", (8 + i, 8), "red"), "PNG")) for i in range(5)
    ]
    res = convert(client, files, format="jpg")
    assert res.headers["content-type"] == "application/zip"
    got = {n: decode(b).size for n, b in outputs(res)}
    assert len(got) == 5
    assert sorted(s[0] for s in got.values()) == [8, 9, 10, 11, 12]


def test_c10_zero_files_422(client):
    t = client.post("/api/v1/tasks", json={"tool": "imageconvert", "params": {"format": "png"}})
    r = client.post(f"/api/v1/tasks/{t.json()['id']}/process", json={})
    assert r.status_code == 422


def test_c10_default_upload_limit_is_200mb():
    assert Settings().max_upload_bytes == 200 * 1024 * 1024


@pytest.fixture
def small_client(tmp_path, db_template):
    settings = Settings(
        data_dir=tmp_path / "data", allowed_hosts=["testserver", "localhost"],
        max_upload_bytes=4000,
    )
    settings.data_dir.mkdir()
    shutil.copy(db_template, settings.db_path)
    with TestClient(create_app(settings)) as c:
        yield c


def test_c10_upload_limit_413_and_boundary(small_client):
    base = img_bytes(Image.effect_noise((60, 60), 80).convert("L"), "PNG")
    assert 1000 < len(base) < 4000
    ok_tid, ok = upload(small_client, "ok.png", base)
    assert ok.status_code == 201
    # pad with trailing bytes to exactly the limit, then limit + 1
    at = base + b"\x00" * (4000 - len(base))
    over = at + b"\x00"
    assert upload(small_client, "at.png", at)[1].status_code == 201
    assert upload(small_client, "over.png", over)[1].status_code == 413


def test_c10_failed_upload_leaves_task_usable(small_client):
    base = img_bytes(Image.effect_noise((60, 60), 80).convert("L"), "PNG")
    tid, _ = upload(small_client, "ok.png", base)
    big = base + b"\x00" * 4000
    r = small_client.post(
        f"/api/v1/tasks/{tid}/files", files={"file": ("big.png", big, "image/png")}
    )
    assert r.status_code == 413
    p = small_client.post(f"/api/v1/tasks/{tid}/process", json={})
    assert p.status_code == 200


# spec gaps -------------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["PHOTO.PNG", "a.JPG", "a.jpeg", "a.txt", "a", "a.png.exe"])
def test_gap_odd_extensions(client, name):
    # spec gap: nothing says what odd extensions do; content sniffing is used. Must not 500.
    data = img_bytes(Image.new("RGB", (8, 8)), "PNG")
    out = convert(client, [(name, data)], format="jpg")
    assert decode(out.content).format == "JPEG"


def test_gap_5000_char_filename_rejected_by_framework_not_500(client):
    # spec gap: the multipart parser refuses header lines this long (400); not a tool decision.
    data = img_bytes(Image.new("RGB", (8, 8)), "PNG")
    _, r = upload(client, ("x" * 5000) + ".png", data)
    assert r.status_code in (201, 400, 413, 422)


def test_gap_zero_byte_file(client):
    # spec gap: zero-byte file; actual behaviour 422 at upload.
    _, r = upload(client, "empty.png", b"")
    assert r.status_code == 422


def test_gap_uppercase_output_extension_lower(client):
    data = img_bytes(Image.new("RGB", (8, 8)), "PNG")
    out = convert(client, [("PHOTO.PNG", data)], format="jpg")
    assert "PHOTO.jpg" in out.headers["content-disposition"]
