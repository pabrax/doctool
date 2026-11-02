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
