from tests.pdfs import make_pdf


def upload(client, data=None, name="a.pdf"):
    data = data or make_pdf(2)
    return client.post("/api/v1/documents", files={"file": (name, data, "application/pdf")})


def test_upload_creates_document_and_first_version(client):
    r = upload(client)
    assert r.status_code == 201
    doc = r.json()
    assert doc["name"] == "a.pdf"
    assert doc["latest_version"]["pages"] == 2
    assert doc["latest_version"]["parent_version_id"] is None
    assert len(doc["latest_version"]["sha256"]) == 64


def test_upload_rejects_non_pdf(client):
    r = client.post("/api/v1/documents", files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 422


def test_upload_rejects_damaged_pdf(client):
    r = client.post(
        "/api/v1/documents", files={"file": ("x.pdf", b"%PDF-1.7\ngarbage", "application/pdf")}
    )
    assert r.status_code == 422


def test_same_content_is_deduplicated_on_disk(client, tmp_path):
    data = make_pdf(1)
    a = upload(client, data, "a.pdf").json()
    b = upload(client, data, "b.pdf").json()
    assert a["id"] != b["id"]
    assert a["latest_version"]["sha256"] == b["latest_version"]["sha256"]
    blobs = [p for p in (tmp_path / "data" / "blobs").rglob("*") if p.is_file()]
    assert len(blobs) == 1


def test_list_get_and_download(client):
    doc = upload(client).json()
    assert [d["id"] for d in client.get("/api/v1/documents").json()] == [doc["id"]]
    assert client.get(f"/api/v1/documents/{doc['id']}").json()["name"] == "a.pdf"
    vid = doc["latest_version"]["id"]
    r = client.get(f"/api/v1/versions/{vid}/download")
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")
    assert "a.pdf" in r.headers["content-disposition"]


def test_versions_history_and_rename_tags(client):
    doc = upload(client).json()
    r = client.patch(f"/api/v1/documents/{doc['id']}", json={"name": "b.pdf", "tags": ["x", "y"]})
    assert r.json()["name"] == "b.pdf" and r.json()["tags"] == ["x", "y"]
    versions = client.get(f"/api/v1/documents/{doc['id']}/versions").json()
    assert len(versions) == 1


def test_delete_document(client):
    doc = upload(client).json()
    assert client.delete(f"/api/v1/documents/{doc['id']}").status_code == 204
    assert client.get(f"/api/v1/documents/{doc['id']}").status_code == 404
    assert client.get("/api/v1/documents").json() == []


def test_unknown_ids_404(client):
    assert client.get("/api/v1/documents/nope").status_code == 404
    assert client.get("/api/v1/versions/nope/download").status_code == 404
