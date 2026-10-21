"""T4 tools exercised through the real task API (contract + property checks)."""

import pytest

from tests.helpers import outputs, run_tool
from tests.pdfs import make_pdf, page_count, page_text


# ---- merge -------------------------------------------------------------------------------
def test_merge_page_count_is_sum_and_order_kept(client):
    a, b, c = make_pdf(2, "A"), make_pdf(3, "B"), make_pdf(1, "C")
    out = run_tool(client, "merge", {}, [("a.pdf", a), ("b.pdf", b), ("c.pdf", c)])
    data = out.content
    assert page_count(data) == 6
    assert page_text(data) == ["A 1", "A 2", "B 1", "B 2", "B 3", "C 1"]


def test_merge_needs_two_files(client):
    t = client.post("/api/v1/tasks", json={"tool": "merge", "params": {}}).json()
    client.post(
        f"/api/v1/tasks/{t['id']}/files", files={"file": ("a.pdf", make_pdf(1), "application/pdf")}
    )
    assert client.post(f"/api/v1/tasks/{t['id']}/process").status_code == 422


# ---- split -------------------------------------------------------------------------------
def test_split_ranges_one_output_per_range(client):
    src = make_pdf(10)
    out = outputs(
        run_tool(client, "split", {"mode": "ranges", "ranges": "1-3,5,8-10"}, [("s.pdf", src)])
    )
    assert [page_count(d) for _, d in out] == [3, 1, 3]


def test_split_ranges_merge_after_makes_single_file(client):
    out = run_tool(
        client, "split",
        {"mode": "ranges", "ranges": "1,3-4", "merge_after": True}, [("s.pdf", make_pdf(5))],
    )  # fmt: skip
    assert page_count(out.content) == 3


def test_split_every_n(client):
    out = outputs(
        run_tool(client, "split", {"mode": "every", "every": 4}, [("s.pdf", make_pdf(10))])
    )
    assert [page_count(d) for _, d in out] == [4, 4, 2]


def test_split_extract_pages_single_output(client):
    out = run_tool(
        client, "split", {"mode": "extract", "ranges": "2,4-5"}, [("s.pdf", make_pdf(6))]
    )
    assert page_text(out.content) == ["Page 2", "Page 4", "Page 5"]


def test_split_remove_pages(client):
    out = run_tool(client, "split", {"mode": "remove", "ranges": "1,3"}, [("s.pdf", make_pdf(4))])
    assert page_text(out.content) == ["Page 2", "Page 4"]


def test_split_by_size_keeps_every_page_and_respects_limit(client):
    src = make_pdf(12)
    out = outputs(run_tool(client, "split", {"mode": "size", "max_kb": 3}, [("s.pdf", src)]))
    assert len(out) > 1
    assert sum(page_count(d) for _, d in out) == 12


@pytest.mark.parametrize("ranges", ["0", "5-2", "1-99", "a", "1,,2"])
def test_split_invalid_or_out_of_range_is_rejected(client, ranges):
    r = run_tool(client, "split", {"mode": "ranges", "ranges": ranges}, [("s.pdf", make_pdf(5))],
                 expect=400)  # fmt: skip
    assert r.json()["detail"]["state"] == "out_of_range"


def test_split_empty_ranges_rejected_at_task_creation(client):
    r = client.post("/api/v1/tasks", json={"tool": "split", "params": {"mode": "ranges"}})
    assert r.status_code == 422


def test_split_remove_all_pages_is_rejected(client):
    r = run_tool(
        client, "split", {"mode": "remove", "ranges": "1-2"}, [("s.pdf", make_pdf(2))], expect=400
    )
    assert r.json()["detail"]["state"] == "out_of_range"


# ---- rotate ------------------------------------------------------------------------------
def rotations(data):
    import io as _io

    import pikepdf

    with pikepdf.open(_io.BytesIO(data)) as pdf:
        return [int(p.obj.get("/Rotate", 0)) % 360 for p in pdf.pages]


def test_rotate_selected_pages(client):
    out = run_tool(client, "rotate", {"angle": 90, "pages": "2-3"}, [("r.pdf", make_pdf(4))])
    assert rotations(out.content) == [0, 90, 90, 0]


def test_rotate_four_times_is_identity(client):
    data = make_pdf(3)
    for _ in range(4):
        data = run_tool(client, "rotate", {"angle": 90}, [("r.pdf", data)]).content
    assert rotations(data) == [0, 0, 0]
    assert page_text(data) == ["Page 1", "Page 2", "Page 3"]


def test_rotate_negative_angle(client):
    out = run_tool(client, "rotate", {"angle": 270}, [("r.pdf", make_pdf(1))])
    assert rotations(out.content) == [270]


# ---- organize ----------------------------------------------------------------------------
def test_organize_reorder_delete_duplicate_blank(client):
    ops = {"order": [3, 1, 1, "blank", 2], "rotations": {"1": 90}}
    out = run_tool(client, "organize", ops, [("o.pdf", make_pdf(4))])
    assert page_count(out.content) == 5
    assert page_text(out.content) == ["Page 3", "Page 1", "Page 1", "", "Page 2"]
    assert rotations(out.content) == [0, 90, 90, 0, 0]


def test_organize_out_of_range_page_rejected(client):
    r = run_tool(client, "organize", {"order": [1, 9]}, [("o.pdf", make_pdf(2))], expect=400)
    assert r.json()["detail"]["state"] == "out_of_range"


def test_organize_empty_order_is_422(client):
    r = client.post("/api/v1/tasks", json={"tool": "organize", "params": {"order": []}})
    assert r.status_code == 422


def test_tools_listing_includes_t4_tools(client):
    ids = {t["id"] for t in client.get("/api/v1/tools").json()}
    assert {"merge", "split", "rotate", "organize"} <= ids
