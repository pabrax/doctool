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
