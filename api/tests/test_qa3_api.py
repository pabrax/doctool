import io
import struct

import pytest
from PIL import Image

IMAGE_TOOLS = {
    "imageclean": {},
    "imagecompress": {},
    "imageconvert": {"format": "png"},
    "imagecrop": {},
    "imageresize": {},
}
EPS = (
    b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\n%%EndComments\n"
    b"newpath 0 0 moveto 10 10 lineto stroke\nshowpage\n"
)
PSD = (
    b"8BPS" + struct.pack(">H", 1) + b"\x00" * 6
    + struct.pack(">HIIHH", 3, 10, 10, 8, 3) + b"\x00" * 40
)


def png(size=(8, 8), color="red") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


ICO = (  # one 8x8 entry holding a PNG
    b"\x00\x00\x01\x00\x01\x00" + bytes([8, 8, 0, 0])
    + struct.pack("<HHII", 1, 32, len(png()), 22) + png()
)


def new_task(client, tool, params=None):
    r = client.post("/api/v1/tasks", json={"tool": tool, "params": params or {}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def upload(client, tid, name, data, mime="image/png"):
    return client.post(f"/api/v1/tasks/{tid}/files", files={"file": (name, data, mime)})


# S1 -------------------------------------------------------------------------------------
@pytest.mark.parametrize("payload", [EPS, PSD, ICO], ids=["eps", "psd", "ico"])
@pytest.mark.parametrize("tool", [*IMAGE_TOOLS, "imagepdf", "watermark"])
def test_non_allowed_formats_rejected_at_upload(client, tool, payload):
    params = {**IMAGE_TOOLS, "watermark": {"text": "x"}}.get(tool, {})
    tid = new_task(client, tool, params)
    r = upload(client, tid, "x.png", payload)
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    if isinstance(detail, dict):
        assert detail["state"] == "not_image"


@pytest.mark.parametrize("payload", [EPS, PSD, ICO], ids=["eps", "psd", "ico"])
def test_unrestricted_pillow_would_open_payloads(payload):
    # guards the test above: these payloads really are recognised by plain Image.open
    assert Image.open(io.BytesIO(payload)).format in ("EPS", "PSD", "ICO")


def test_open_image_and_global_pixel_cap():
    from doctool.tools import imageutil

    assert imageutil.ALLOWED_FORMATS == (
        "JPEG", "MPO", "PNG", "WEBP", "AVIF", "GIF", "BMP", "TIFF"
    )
    assert Image.MAX_IMAGE_PIXELS == imageutil.MAX_PIXELS
    assert imageutil.open_image(png()).format == "PNG"


# S4 -------------------------------------------------------------------------------------
def gif_animated() -> bytes:
    buf = io.BytesIO()
    frames = [Image.new("RGB", (8, 8), c) for c in ("red", "blue")]
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=50)
    return buf.getvalue()


def process(client, tool, params, files, expect):
    tid = new_task(client, tool, params)
    for name, data in files:
        assert upload(client, tid, name, data).status_code == 201
    r = client.post(f"/api/v1/tasks/{tid}/process", json={})
    assert r.status_code == expect, r.text
    return r


@pytest.mark.parametrize("tool", list(IMAGE_TOOLS))
def test_processing_error_names_the_failing_file(client, tool):
    r = process(client, tool, IMAGE_TOOLS[tool],
                [("first.png", png()), ("second.gif", gif_animated())], 400)
    detail = r.json()["detail"]
    assert detail["state"] == "unsupported"
    assert detail["file"] == "second.gif"


def test_crop_out_of_range_names_file(client):
    params = {"mode": "box", "x": 0, "y": 0, "width": 50, "height": 50}
    r = process(client, "imagecrop", params, [("a.png", png()), ("small.png", png())], 400)
    detail = r.json()["detail"]
    assert detail["state"] == "out_of_range"
    assert detail["file"] == "a.png"


def test_error_without_file_has_no_file_key(client):
    from doctool.tools.base import ToolError

    assert ToolError("damaged", "x").file is None
    with pytest.raises(TypeError):
        ToolError("damaged", "x", False, "f.png")  # file is keyword-only
    assert ToolError("damaged", "x", file="f.png").file == "f.png"


# S2 -------------------------------------------------------------------------------------
def test_settings_defaults_and_env(monkeypatch):
    from doctool.config import Settings

    s = Settings()
    assert (s.image_max_pixels, s.image_task_max_pixels) == (50_000_000, 100_000_000)
    assert (s.image_max_files, s.image_concurrency) == (10, 2)
    monkeypatch.setenv("DOCTOOL_IMAGE_MAX_FILES", "3")
    monkeypatch.setenv("DOCTOOL_IMAGE_CONCURRENCY", "1")
    s = Settings.from_env()
    assert (s.image_max_files, s.image_concurrency) == (3, 1)


def test_image_tools_take_max_files_from_settings():
    from doctool.config import Settings
    from doctool.tools.base import registry

    for tool in IMAGE_TOOLS:
        assert registry.get(tool).max_files == Settings().image_max_files
    assert registry.get("imagepdf").max_files is None


def test_51_megapixel_image_rejected_at_upload(client):
    big = io.BytesIO()
    Image.new("1", (8000, 6400)).save(big, "PNG")  # 51.2 MP, tiny file
    for tool, params in IMAGE_TOOLS.items():
        r = upload(client, new_task(client, tool, params), "big.png", big.getvalue())
        assert r.status_code == 422, (tool, r.text)
        assert r.json()["detail"]["state"] == "too_large"


def test_imagepdf_keeps_the_hard_cap(client):
    big = io.BytesIO()
    Image.new("1", (8000, 6400)).save(big, "PNG")
    r = upload(client, new_task(client, "imagepdf"), "big.png", big.getvalue())
    assert r.status_code == 201


def test_eleven_files_rejected(client):
    tid = new_task(client, "imageclean")
    codes = [upload(client, tid, f"{i}.png", png()).status_code for i in range(11)]
    assert codes == [201] * 10 + [422]


@pytest.mark.parametrize("tool", list(IMAGE_TOOLS))
def test_task_total_pixels_rejected_before_decoding(client, monkeypatch, tool):
    from doctool.tools import imagecore, imageutil

    monkeypatch.setattr(imageutil, "IMAGE_TASK_MAX_PIXELS", 150)

    def no_decode(*a, **k):
        raise AssertionError("decoded before the preflight")

    monkeypatch.setattr(imagecore, "load_image", no_decode)
    monkeypatch.setattr(f"doctool.tools.{tool}.load_image", no_decode)
    files = [(f"{i}.png", png()) for i in range(3)]  # 64 px each, 192 in total
    r = process(client, tool, IMAGE_TOOLS[tool], files, 400)
    detail = r.json()["detail"]
    assert detail["state"] == "too_large"
    assert detail["file"] == "2.png"


def test_preflight_per_image_cap_names_file(monkeypatch):
    from doctool.tools import imagecore, imageutil
    from doctool.tools.base import ToolError, ToolInput

    monkeypatch.setattr(imageutil, "IMAGE_MAX_PIXELS", 50)
    with pytest.raises(ToolError) as exc:
        imagecore.preflight([ToolInput("fat.png", png())])
    assert (exc.value.state, exc.value.file) == ("too_large", "fat.png")


def test_image_concurrency_is_bounded(client, monkeypatch):
    import threading
    import time

    from doctool.routers import tasks
    from doctool.tools.base import registry

    monkeypatch.setattr(tasks, "_IMAGE_SLOTS", threading.BoundedSemaphore(2))
    client.app.state.settings.image_slot_wait_seconds = 5  # this test is about the bound, not 503
    lock = threading.Lock()
    state = {"now": 0, "max": 0}

    def slow_run(inputs, params):
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
        time.sleep(0.6)
        with lock:
            state["now"] -= 1
        return [ToolOutput("o.png", inputs[0].data)]

    from doctool.tools.base import ToolOutput

    monkeypatch.setattr(registry.get("imageclean"), "run", slow_run)
    tids = []
    for _ in range(5):
        tid = new_task(client, "imageclean")
        assert upload(client, tid, "a.png", png()).status_code == 201
        tids.append(tid)
    codes = []

    def go(tid):
        codes.append(client.post(f"/api/v1/tasks/{tid}/process", json={}).status_code)

    threads = [threading.Thread(target=go, args=(t,)) for t in tids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert codes == [200] * 5
    assert state["max"] == 2


# S3 / S5 --------------------------------------------------------------------------------
def noisy_jpeg(quality=20, **kw) -> bytes:
    buf = io.BytesIO()
    Image.effect_noise((64, 64), 60).convert("RGB").save(buf, "JPEG", quality=quality, **kw)
    return buf.getvalue()


def gps_exif() -> Image.Exif:
    exif = Image.Exif()
    exif[0x010F] = "TestMaker"
    exif.get_ifd(0x8825)[1] = "N"
    return exif


def run_one(client, tool, params, name, data, mime="image/jpeg"):
    from tests.helpers import run_tool

    return run_tool(client, tool, params, [(name, data, mime)]).content


def test_compress_never_grow_fallback_strips_private_metadata(client):
    src = noisy_jpeg(20, exif=gps_exif().tobytes(), comment=b"secret-comment")
    out = run_one(client, "imagecompress", {"preset": "max"}, "p.jpg", src)
    assert b"Exif" not in out and b"TestMaker" not in out and b"secret-comment" not in out
    assert not Image.open(io.BytesIO(out)).getexif()


def test_compress_never_grow_keeps_original_without_metadata(client):
    src = noisy_jpeg(20)
    assert run_one(client, "imagecompress", {"preset": "max"}, "p.jpg", src) == src


def test_compress_png_text_chunks_count_as_private(client):
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    info.add_text("Comment", "secret-text")
    buf = io.BytesIO()
    Image.effect_noise((64, 64), 60).convert("RGB").save(
        buf, "PNG", pnginfo=info, optimize=True, compress_level=9
    )
    assert b"secret-text" in buf.getvalue()
    out = run_one(client, "imagecompress", {}, "p.png", buf.getvalue(), "image/png")
    assert b"secret-text" not in out and out != buf.getvalue()


@pytest.mark.parametrize(
    ("tool", "params"),
    [
        ("imageconvert", {"format": "jpg"}),
        ("imagecrop", {}),
        ("imageresize", {"width": 32}),
        ("imagecompress", {"preset": "max"}),
    ],
)
def test_jpeg_comment_does_not_survive(client, tool, params):
    src = noisy_jpeg(95, comment=b"secret-comment")
    out = run_one(client, tool, params, "p.jpg", src)
    assert b"secret-comment" not in out


def test_cmyk_icc_profile_dropped_on_rgb_conversion(client):
    from PIL import ImageCms

    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    buf = io.BytesIO()
    Image.new("CMYK", (16, 16), (10, 20, 30, 40)).save(buf, "JPEG", icc_profile=icc)
    assert Image.open(io.BytesIO(buf.getvalue())).info.get("icc_profile")
    out = run_one(client, "imageconvert", {"format": "png"}, "c.jpg", buf.getvalue())
    img = Image.open(io.BytesIO(out))
    assert img.mode == "RGB" and "icc_profile" not in img.info
