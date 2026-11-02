import threading
import time

import pytest

from tests.test_qa3_api import new_task, png, upload
from tests.test_qa4_api import (
    _jpeg_with_segment,
    _noise,
    _png,
    _save,
    _webp,
    run_compress,
)


def test_imagepdf_has_no_task_wide_pixel_cap(client, monkeypatch):
    from doctool.routers import tasks
    from doctool.tools import imageutil

    assert "imagepdf" in tasks._SLOTTED_TOOL_IDS  # still bounded by the semaphore
    monkeypatch.setattr(imageutil, "IMAGE_TASK_MAX_PIXELS", 150)  # 3 x 64 px = 192 in total
    tid = new_task(client, "imagepdf")
    for i in range(3):
        assert upload(client, tid, f"{i}.png", png()).status_code == 201
    assert client.post(f"/api/v1/tasks/{tid}/process", json={}).status_code == 200


def test_imagepdf_still_has_per_image_cap(client, monkeypatch):
    from doctool.tools import imagepdf

    tid = new_task(client, "imagepdf")
    assert upload(client, tid, "a.png", png()).status_code == 201  # 64 px
    monkeypatch.setattr(imagepdf, "MAX_PIXELS", 50)
    r = client.post(f"/api/v1/tasks/{tid}/process", json={})
    assert r.status_code == 400 and r.json()["detail"]["state"] == "too_large"


def test_default_slot_wait_is_half_a_second(monkeypatch):
    from doctool.config import Settings

    monkeypatch.delenv("DOCTOOL_IMAGE_SLOT_WAIT_SECONDS", raising=False)
    assert Settings.from_env().image_slot_wait_seconds == 0.5


def test_parallel_process_same_task_runs_once(client, monkeypatch):
    from doctool.routers import tasks
    from doctool.tools.base import ToolOutput, registry

    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(tasks, "_IMAGE_SLOTS", slots)
    client.app.state.settings.image_slot_wait_seconds = 5
    runs = []

    def slow_run(inputs, params):
        runs.append(1)
        time.sleep(0.3)
        return [ToolOutput("o.png", inputs[0].data)]

    monkeypatch.setattr(registry.get("imageclean"), "run", slow_run)
    tid = new_task(client, "imageclean")
    assert upload(client, tid, "a.png", png()).status_code == 201
    slots.acquire()  # both requests pass the state check, then queue for the slot
    codes = []
    threads = [
        threading.Thread(
            target=lambda: codes.append(
                client.post(f"/api/v1/tasks/{tid}/process", json={}).status_code
            )
        )
        for _ in range(2)
    ]
    for t in threads:
        t.start()
    time.sleep(0.5)
    slots.release()
    for t in threads:
        t.join(10)
    assert sorted(codes) in ([200, 409], [200, 503])
    assert len(runs) == 1
    files = client.get(f"/api/v1/tasks/{tid}").json()["files"]
    assert len([f for f in files if f["role"] == "out"]) == 1
    assert tasks._IMAGE_SLOTS.acquire(blocking=False)


def _exif() -> bytes:
    from PIL import Image

    exif = Image.Exif()
    exif[0x010F] = "secret-maker"
    return exif.tobytes()


def _png_with_chunk(kind: bytes, payload: bytes) -> bytes:
    import zlib

    src = _png()
    chunk = (
        len(payload).to_bytes(4, "big") + kind + payload
        + zlib.crc32(kind + payload).to_bytes(4, "big")
    )
    pos = src.rindex(b"IEND") - 4
    return src[:pos] + chunk + src[pos:]


PRIVATE = {
    "jpeg-app12-ducky": (
        lambda: _jpeg_with_segment(0xEC, b"Ducky\0\x01secret-duck"),
        b"secret-duck", "image/jpeg", "p.jpg"),
    "jpeg-trailing": (
        lambda: _save(_noise(), "JPEG", quality=20) + b"secret-trail",
        b"secret-trail", "image/jpeg", "p.jpg"),
    "png-caBX": (lambda: _png_with_chunk(b"caBX", b"secret-c2pa"), b"secret-c2pa",
                 "image/png", "p.png"),
    "png-unknown": (lambda: _png_with_chunk(b"prVt", b"secret-priv"), b"secret-priv",
                    "image/png", "p.png"),
    "webp-exif": (lambda: _webp(exif=_exif()), b"secret-maker",
                  "image/webp", "p.webp"),
}


@pytest.mark.parametrize("case", list(PRIVATE))
def test_allowlist_flags_private_data(client, case):
    make, marker, mime, name = PRIVATE[case]
    src = make()
    assert marker in src
    out = run_compress(client, name, src, mime)
    assert marker not in out
    assert out != src


@pytest.mark.parametrize("case", list(PRIVATE))
def test_allowlist_detects_private_directly(case):
    from doctool.tools.imagecore import has_private_metadata

    assert has_private_metadata(PRIVATE[case][0]())


@pytest.mark.parametrize(
    "clean",
    [lambda: _save(_noise(), "JPEG", quality=20), _png, _webp],
    ids=["jpeg", "png", "webp"],
)
def test_allowlist_clean_files_not_private(clean):
    from doctool.tools.imagecore import has_private_metadata

    assert not has_private_metadata(clean())
