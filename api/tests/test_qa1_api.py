import io

from PIL import Image

from tests.helpers import run_tool


def png(size=(20, 10)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, "red").save(buf, "PNG")
    return buf.getvalue()


def props(client, tool_id):
    tool = next(t for t in client.get("/api/v1/tools").json() if t["id"] == tool_id)
    return tool["params_schema"]["properties"]


def new_task(client, tool, params):
    return client.post("/api/v1/tasks", json={"tool": tool, "params": params})


def upload(client, tid, name, data, mime="image/png"):
    return client.post(f"/api/v1/tasks/{tid}/files", files={"file": (name, data, mime)})


# AC1 ----------------------------------------------------------------------------------------
def test_convert_defaults_to_jpg(client):
    out = run_tool(client, "imageconvert", {}, [("a.png", png(), "image/png")])
    assert Image.open(io.BytesIO(out.content)).format == "JPEG"


# AC2 ----------------------------------------------------------------------------------------
def test_convert_show_when(client):
    p = props(client, "imageconvert")
    allowed = set(p["format"]["enum"])
    want = [f for f in ("jpg", "webp", "avif") if f in allowed]
    assert p["quality"]["show_when"] == {"format": want}
    assert p["background"]["show_when"] == {"format": ["jpg"]}


def test_resize_show_when(client):
    p = props(client, "imageresize")
    assert p["width"]["show_when"] == {"mode": ["fit_box", "exact"]}
    assert p["height"]["show_when"] == {"mode": ["fit_box", "exact"]}
    assert p["percent"]["show_when"] == {"mode": ["percent"]}


def test_crop_show_when(client):
    p = props(client, "imagecrop")
    assert p["ratio"]["show_when"] == {"mode": ["ratio"]}
    for name in ("x", "y", "width", "height"):
        assert p[name]["show_when"] == {"mode": ["box"]}


# AC3 ----------------------------------------------------------------------------------------
def test_crop_box_without_size_is_422(client):
    for extra in ({}, {"width": 5}, {"height": 5}):
        r = new_task(client, "imagecrop", {"mode": "box", **extra})
        assert r.status_code == 422, r.text
        assert "width and height are required in box mode" in r.text


def test_crop_box_out_of_range_still_400(client):
    r = run_tool(
        client, "imagecrop", {"mode": "box", "width": 99, "height": 99},
        [("a.png", png(), "image/png")], expect=400,
    )
    assert r.json()["detail"]["state"] == "out_of_range"


# AC4 ----------------------------------------------------------------------------------------
def post_bad(client, data, name="a.png"):
    tid = new_task(client, "imageconvert", {}).json()["id"]
    return upload(client, tid, name, data)


def test_input_error_not_image(client):
    for data in (b"hello world", b""):
        r = post_bad(client, data)
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["state"] == "not_image"
        assert r.json()["detail"]["message"]


def test_input_error_damaged(client):
    r = post_bad(client, png((200, 200))[:-30])
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["state"] == "damaged"
    bad = bytearray(png((200, 200)))
    bad[40:60] = b"\x00" * 20  # corrupt the IHDR/IDAT area
    r = post_bad(client, bytes(bad))
    assert r.status_code == 422
    assert r.json()["detail"]["state"] in ("damaged", "not_image")


def test_input_error_too_large(client):
    r = post_bad(client, png((10001, 10001)))
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["state"] == "too_large"


def test_input_error_is_value_error_with_state():
    from doctool.tools.imageutil import InputError, verify_image

    assert issubclass(InputError, ValueError)
    try:
        verify_image(b"nope")
    except InputError as exc:
        assert exc.state == "not_image"
    else:
        raise AssertionError("no error")


def test_pdf_errors_unchanged(client):
    tid = new_task(client, "split", {"mode": "every"}).json()["id"]
    r = upload(client, tid, "a.pdf", b"not a pdf", "application/pdf")
    assert r.status_code == 422
    # Since office QA1 (O5): a state and a plain message, never the library's text (it leaked
    # object reprs such as "<_io.BytesIO object at 0x...>").
    assert r.json()["detail"] == {"state": "not_pdf", "message": "This file is not a PDF."}


def test_upload_limit_413_has_state(tmp_path, db_template):
    import shutil

    from fastapi.testclient import TestClient

    from doctool.config import Settings
    from doctool.main import create_app

    settings = Settings(
        data_dir=tmp_path / "data", allowed_hosts=["testserver"], max_upload_bytes=100
    )
    settings.data_dir.mkdir()
    shutil.copy(db_template, settings.db_path)
    with TestClient(create_app(settings)) as c:
        r = post_bad(c, b"x" * 500)
    assert r.status_code == 413
    assert r.json()["detail"]["state"] == "too_large"
    assert r.json()["detail"]["message"]


# AC5 ----------------------------------------------------------------------------------------
def test_task_files_carry_size(client):
    src = png((64, 64))
    tid = new_task(client, "imagecompress", {}).json()["id"]
    r = upload(client, tid, "a.png", src)
    assert r.json()["files"][0]["size"] == len(src)
    p = client.post(f"/api/v1/tasks/{tid}/process", json={})
    assert p.status_code == 200, p.text
    got = client.get(f"/api/v1/tasks/{tid}").json()["files"]
    dl = client.get(f"/api/v1/tasks/{tid}/download")
    out = next(f for f in p.json()["files"] if f["role"] == "out")
    assert out["size"] == len(dl.content)
    assert {f["role"]: f["size"] for f in got}["out"] == len(dl.content)
    assert {f["role"]: f["size"] for f in got}["in"] == len(src)
