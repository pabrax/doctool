import io
import threading
import time

import pytest
from PIL import Image

from doctool.config import Settings
from tests.test_qa3_api import IMAGE_TOOLS, new_task, png, upload


def _slow_setup(client, monkeypatch, wait=0.3):
    from doctool.routers import tasks
    from doctool.tools.base import ToolOutput, registry

    monkeypatch.setattr(tasks, "_IMAGE_SLOTS", threading.BoundedSemaphore(1))
    client.app.state.settings.image_slot_wait_seconds = wait
    started, release = threading.Event(), threading.Event()

    def slow_run(inputs, params):
        started.set()
        release.wait(10)
        return [ToolOutput("o.png", inputs[0].data)]

    monkeypatch.setattr(registry.get("imageclean"), "run", slow_run)
    return started, release


def _task(client):
    tid = new_task(client, "imageclean")
    assert upload(client, tid, "a.png", png()).status_code == 201
    return tid


def test_busy_returns_503_and_other_endpoints_answer(client, monkeypatch):
    started, release = _slow_setup(client, monkeypatch)
    first, second = _task(client), _task(client)
    res = {}
    t = threading.Thread(
        target=lambda: res.update(r=client.post(f"/api/v1/tasks/{first}/process", json={}))
    )
    t.start()
    assert started.wait(5)
    t0 = time.monotonic()
    box = {}
    t2 = threading.Thread(
        target=lambda: box.update(r=client.post(f"/api/v1/tasks/{second}/process", json={}))
    )
    t2.start()
    time.sleep(0.1)
    assert client.get("/api/v1/tools").status_code == 200  # not stalled while it waits
    t2.join(5)
    assert time.monotonic() - t0 < 1.3
    r = box["r"]
    assert r.status_code == 503, r.text
    assert r.json()["detail"] == {
        "state": "busy",
        "message": "The server is busy. Try again in a moment.",
        "retryable": True,
    }
    assert client.get(f"/api/v1/tasks/{second}").json()["state"] == "waiting"
    release.set()
    t.join(5)
    assert res["r"].status_code == 200
    assert client.post(f"/api/v1/tasks/{second}/process", json={}).status_code == 200


def test_slot_released_when_tool_raises(client, monkeypatch):
    from doctool.routers import tasks
    from doctool.tools.base import registry

    monkeypatch.setattr(tasks, "_IMAGE_SLOTS", threading.BoundedSemaphore(1))

    def boom(inputs, params):
        raise RuntimeError("x")

    monkeypatch.setattr(registry.get("imageclean"), "run", boom)
    tid = _task(client)
    assert client.post(f"/api/v1/tasks/{tid}/process", json={}).status_code == 500
    assert tasks._IMAGE_SLOTS.acquire(blocking=False)


# Q2 -------------------------------------------------------------------------------------
@pytest.mark.parametrize("bad", ["0", "-3", "abc", "1.5"])
@pytest.mark.parametrize(
    "key", ["image_concurrency", "image_max_files", "image_max_pixels", "image_task_max_pixels"]
)
def test_invalid_env_caps_fall_back(monkeypatch, caplog, key, bad):
    monkeypatch.setenv(f"DOCTOOL_{key.upper()}", bad)
    s = Settings.from_env()
    assert getattr(s, key) == Settings.model_fields[key].default
    assert key.upper() in caplog.text


@pytest.mark.parametrize("bad", ["0", "-1", "abc"])
def test_invalid_slot_wait_falls_back(monkeypatch, bad):
    monkeypatch.setenv("DOCTOOL_IMAGE_SLOT_WAIT_SECONDS", bad)
    assert Settings.from_env().image_slot_wait_seconds == 0.5


def test_valid_env_caps_applied(monkeypatch):
    monkeypatch.setenv("DOCTOOL_IMAGE_SLOT_WAIT_SECONDS", "0.5")
    monkeypatch.setenv("DOCTOOL_IMAGE_MAX_FILES", "4")
    s = Settings.from_env()
    assert (s.image_slot_wait_seconds, s.image_max_files) == (0.5, 4)


# Q4 -------------------------------------------------------------------------------------
@pytest.mark.parametrize("tool", list(IMAGE_TOOLS))
def test_eleventh_upload_rejected(client, tool):
    tid = new_task(client, tool, IMAGE_TOOLS[tool])
    for i in range(10):
        assert upload(client, tid, f"{i}.png", png()).status_code == 201
    r = upload(client, tid, "x.png", png())
    assert r.status_code == 422
    d = r.json()["detail"]
    assert d["state"] == "too_many_files" and "at most 10 images at once" in d["message"]


def test_imagepdf_has_no_upload_cap(client):
    tid = new_task(client, "imagepdf")
    for i in range(11):
        assert upload(client, tid, f"{i}.png", png()).status_code == 201


def test_process_too_many_uses_same_state(client, monkeypatch):
    from doctool.tools.base import registry

    tid = new_task(client, "imageclean")
    for i in range(3):
        assert upload(client, tid, f"{i}.png", png()).status_code == 201
    monkeypatch.setattr(registry.get("imageclean"), "max_files", 10)
    client.app.state.settings.image_max_files = 2
    r = client.post(f"/api/v1/tasks/{tid}/process", json={})
    assert r.status_code == 422
    assert r.json()["detail"]["state"] == "too_many_files"


# Q5 -------------------------------------------------------------------------------------
# Q3 -------------------------------------------------------------------------------------
def _noise(mode="RGB", size=(64, 64)):
    return Image.effect_noise(size, 60).convert(mode)


def _save(img, fmt, **kw):
    buf = io.BytesIO()
    img.save(buf, fmt, **kw)
    return buf.getvalue()


def _jpeg_with_segment(marker: int, payload: bytes) -> bytes:
    src = _save(_noise(), "JPEG", quality=20)
    seg = b"\xff" + bytes([marker]) + (len(payload) + 2).to_bytes(2, "big") + payload
    return src[:2] + seg + src[2:]


def _gif_with_xmp() -> bytes:
    src = _save(_noise("L"), "GIF")
    pos = 13 + (3 * 2 ** ((src[10] & 7) + 1) if src[10] & 0x80 else 0)
    ext = b"\x21\xff\x0bXMP DataXMP" + bytes([len(b"secret-xmp")]) + b"secret-xmp" + b"\x00"
    return src[:pos] + ext + src[pos:]


def _png(**kw):
    return _save(_noise(), "PNG", optimize=True, compress_level=9, **kw)


def _png_itxt():
    from PIL.PngImagePlugin import PngInfo, iTXt

    info = PngInfo()
    info.add_text("Comment", iTXt("secret-itxt", "en", "Comment"))
    return _png(pnginfo=info)


def _png_text():
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    info.add_text("Comment", "secret-text")
    return _png(pnginfo=info)


def _png_exif():
    exif = Image.Exif()
    exif[0x010F] = "secret-maker"
    return _png(exif=exif.tobytes())


def _webp(**kw):
    return _save(_noise(), "WEBP", quality=20, **kw)


PRIVATE_CASES = {
    "jpeg-extxmp": (
        lambda: _jpeg_with_segment(0xE1, b"http://ns.adobe.com/xmp/extension/\0secret-xmp"),
        b"secret-xmp", "image/jpeg", "p.jpg"),
    "jpeg-app13": (
        lambda: _jpeg_with_segment(0xED, b"Photoshop 3.0\0secret-xmp"),
        b"secret-xmp", "image/jpeg", "p.jpg"),
    "png-itxt": (_png_itxt, b"secret-itxt", "image/png", "p.png"),
    "png-text": (_png_text, b"secret-text", "image/png", "p.png"),
    "png-exif": (_png_exif, b"secret-maker", "image/png", "p.png"),
    "gif-xmp": (_gif_with_xmp, b"secret-xmp", "image/gif", "p.gif"),
    "webp-xmp": (lambda: _webp(xmp=b"<x>secret-xmp</x>"), b"secret-xmp", "image/webp", "p.webp"),
}


@pytest.mark.parametrize("case", list(PRIVATE_CASES))
def test_never_grow_fallback_scans_original_bytes(client, case):
    make, marker, mime, name = PRIVATE_CASES[case]
    src = make()
    assert marker in src
    out = run_compress(client, name, src, mime)
    assert marker not in out
    assert out != src


@pytest.mark.parametrize(
    ("clean", "mime", "name"),
    [
        (lambda: _save(_noise(), "JPEG", quality=20), "image/jpeg", "p.jpg"),
        (_png, "image/png", "p.png"),
        (_webp, "image/webp", "p.webp"),
    ],
    ids=["jpeg", "png", "webp"],
)
def test_clean_never_grow_returns_identical_bytes(client, clean, mime, name):
    src = clean()
    assert run_compress(client, name, src, mime) == src


def test_gif_never_returns_original(client):
    src = _save(_noise("L"), "GIF")
    out = run_compress(client, "p.gif", src, "image/gif")
    assert out[:8] == b"\x89PNG\r\n\x1a\n"


def run_compress(client, name, data, mime):
    from tests.helpers import run_tool

    return run_tool(client, "imagecompress", {"preset": "max"}, [(name, data, mime)]).content
