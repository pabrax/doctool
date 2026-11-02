def new_task(client, tool, params):
    return client.post("/api/v1/tasks", json={"tool": tool, "params": params})


def last_loc(r):
    return r.json()["detail"][0]["loc"][-1:]


def test_crop_box_missing_width_names_field(client):
    r = new_task(client, "imagecrop", {"mode": "box", "height": 5})
    assert r.status_code == 422
    assert last_loc(r) == ["width"]
    assert "width and height are required in box mode" in r.text


def test_crop_box_missing_height_names_field(client):
    r = new_task(client, "imagecrop", {"mode": "box", "width": 5})
    assert r.status_code == 422
    assert last_loc(r) == ["height"]
    assert "width and height are required in box mode" in r.text


def test_crop_box_missing_both_names_a_field(client):
    r = new_task(client, "imagecrop", {"mode": "box"})
    assert r.status_code == 422
    assert {d["loc"][-1] for d in r.json()["detail"]} == {"width", "height"}


def test_crop_ratio_mode_needs_no_size(client):
    assert new_task(client, "imagecrop", {"mode": "ratio"}).status_code in (200, 201)


def test_resize_exact_without_height_names_field(client):
    r = new_task(client, "imageresize", {"mode": "exact", "width": 10})
    assert r.status_code == 422
    assert last_loc(r) == ["height"]
    assert "height is required for an exact size" in r.text
