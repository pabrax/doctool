import io
from datetime import UTC, datetime, timedelta

from PIL import Image

from doctool.db import Task, TaskFile
from doctool.library import purge_expired_tasks
from tests.helpers import run_tool
from tests.pdfs import make_pdf


def upload(client, data=None, name="a.pdf"):
    return client.post(
        "/api/v1/documents", files={"file": (name, data or make_pdf(3), "application/pdf")}
    ).json()


def vid(doc):
    return doc["latest_version"]["id"]


def test_thumbnail_is_png_with_requested_width_and_immutable_cache(client):
    doc = upload(client)
    r = client.get(f"/api/v1/versions/{vid(doc)}/thumbnail/1?width=200")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert "immutable" in r.headers["cache-control"]
    assert Image.open(io.BytesIO(r.content)).width == 200


def test_thumbnail_page_out_of_range_404(client):
    doc = upload(client)
    assert client.get(f"/api/v1/versions/{vid(doc)}/thumbnail/9").status_code == 404
    assert client.get(f"/api/v1/versions/{vid(doc)}/thumbnail/0").status_code == 404


def test_thumbnail_width_is_bounded(client):
    doc = upload(client)
    assert client.get(f"/api/v1/versions/{vid(doc)}/thumbnail/1?width=5000").status_code == 422


def test_thumbnail_encrypted_is_409(client):
    locked = run_tool(client, "protect", {"password": "pw"}, [("a.pdf", make_pdf(1))]).content
    doc = upload(client, locked, "l.pdf")
    assert client.get(f"/api/v1/versions/{vid(doc)}/thumbnail/1").status_code == 409


def test_thumbnail_respects_page_rotation(client):
    src = run_tool(client, "rotate", {"angle": 90}, [("a.pdf", make_pdf(1))]).content
    doc = upload(client, src, "r.pdf")
    r = client.get(f"/api/v1/versions/{vid(doc)}/thumbnail/1?width=300")
    w, h = Image.open(io.BytesIO(r.content)).size
    assert w == 300 and h < w  # rotated A4 is landscape


def test_pages_info_lists_size_and_rotation(client):
    src = run_tool(client, "rotate", {"angle": 90, "pages": "2"}, [("a.pdf", make_pdf(2))]).content
    doc = upload(client, src, "r.pdf")
    pages = client.get(f"/api/v1/versions/{vid(doc)}/pages").json()
    assert [p["index"] for p in pages] == [1, 2]
    assert [p["rotate"] for p in pages] == [0, 90]
    assert round(pages[0]["width"]) == 595 and round(pages[0]["height"]) == 842


def test_inline_download_for_preview(client):
    doc = upload(client)
    r = client.get(f"/api/v1/versions/{vid(doc)}/download?inline=1")
    assert r.headers["content-disposition"].startswith("inline")


def test_non_latin_filename_does_not_break_download(client):
    doc = upload(client, name="señal – 日本語.pdf")
    r = client.get(f"/api/v1/versions/{vid(doc)}/download")
    assert r.status_code == 200
    cd = r.headers["content-disposition"]
    assert "filename*=UTF-8''" in cd and "%C3%B1" in cd  # ñ percent-encoded


def test_filename_cannot_inject_header_or_path(client):
    doc = upload(client, name='..\\..\\evil"\r\nX-Injected: 1.pdf')
    name = doc["latest_version"]["filename"]
    assert "\r" not in name and "\n" not in name and "/" not in name and "\\" not in name
    r = client.get(f"/api/v1/versions/{vid(doc)}/download")
    assert "x-injected" not in {k.lower() for k in r.headers}


def test_purge_expired_tasks_removes_old_tasks_and_orphan_blobs_only(client, tmp_path):
    app = client.app
    old = run_tool(client, "rotate", {"angle": 90}, [("a.pdf", make_pdf(1, "old"))], expect=200)
    assert old.status_code == 200
    run_tool(client, "rotate", {"angle": 90}, [("b.pdf", make_pdf(1, "new"))])
    with app.state.session_factory() as db:
        tasks = db.query(Task).order_by(Task.created_at).all()
        tasks[0].created_at = datetime.now(UTC) - timedelta(hours=48)
        db.commit()
        removed = purge_expired_tasks(db, app.state.blobs, ttl_hours=24)
        assert removed == 1
        assert db.query(Task).count() == 1
        # library versions created by the purged task must survive
        assert db.query(TaskFile).count() >= 1
    assert len(client.get("/api/v1/documents").json()) == 2
    for d in client.get("/api/v1/documents").json():
        assert (
            client.get(f"/api/v1/versions/{d['latest_version']['id']}/download").status_code == 200
        )
