import io

import pikepdf
import pytest

from tests.helpers import run_tool
from tests.pdfs import make_pdf, page_count, page_text


def is_encrypted(data: bytes) -> bool:
    try:
        with pikepdf.open(io.BytesIO(data)):
            return False
    except pikepdf.PasswordError:
        return True


# ---- protect / unlock --------------------------------------------------------------------
def test_protect_encrypts_and_correct_password_opens(client):
    out = run_tool(client, "protect", {"password": "s3cret"}, [("a.pdf", make_pdf(3))]).content
    assert is_encrypted(out)
    with pikepdf.open(io.BytesIO(out), password="s3cret") as pdf:
        assert len(pdf.pages) == 3
        assert pdf.encryption.R == 6  # AES-256


def test_protect_unlock_round_trip_keeps_content(client):
    src = make_pdf(3, "Doc")
    locked = run_tool(client, "protect", {"password": "pw1"}, [("a.pdf", src)]).content
    clear = run_tool(client, "unlock", {}, [("a.pdf", locked)], passwords=["pw1"]).content
    assert not is_encrypted(clear)
    assert page_count(clear) == 3
    assert page_text(clear) == ["Doc 1", "Doc 2", "Doc 3"]


def test_unlock_without_password_reports_wrong_password_and_stays_waiting(client):
    locked = run_tool(client, "protect", {"password": "pw1"}, [("a.pdf", make_pdf(1))]).content
    r = run_tool(client, "unlock", {}, [("a.pdf", locked)], expect=400)
    assert r.json()["detail"]["state"] == "wrong_password"


def test_unlock_with_wrong_password_rejected(client):
    locked = run_tool(client, "protect", {"password": "pw1"}, [("a.pdf", make_pdf(1))]).content
    r = run_tool(client, "unlock", {}, [("a.pdf", locked)], passwords=["nope"], expect=400)
    assert r.json()["detail"]["state"] == "wrong_password"


def test_unlock_on_plain_pdf_is_a_noop_copy(client):
    out = run_tool(client, "unlock", {}, [("a.pdf", make_pdf(2))]).content
    assert page_count(out) == 2 and not is_encrypted(out)


def test_protect_requires_password(client):
    for params in ({}, {"password": ""}):
        r = client.post("/api/v1/tasks", json={"tool": "protect", "params": params})
        assert r.status_code == 422


def test_protect_restrictions_are_applied(client):
    out = run_tool(
        client,
        "protect",
        {"password": "pw", "owner_password": "own", "allow_print": False, "allow_copy": False},
        [("a.pdf", make_pdf(1))],
    ).content
    with pikepdf.open(io.BytesIO(out), password="pw") as pdf:
        assert pdf.allow.print_lowres is False
        assert pdf.allow.extract is False


def test_password_never_stored_in_history_or_task(client):
    run_tool(client, "protect", {"password": "TOPSECRET"}, [("a.pdf", make_pdf(1))])
    blob = str(client.get("/api/v1/documents").json())
    assert "TOPSECRET" not in blob
    assert (
        client.get("/api/v1/documents").json()[0]["latest_version"]["params"]["password"] == "***"
    )


def test_encrypted_upload_to_library_is_accepted_with_unknown_pages(client):
    locked = run_tool(client, "protect", {"password": "pw"}, [("a.pdf", make_pdf(2))]).content
    r = client.post("/api/v1/documents", files={"file": ("l.pdf", locked, "application/pdf")})
    assert r.status_code == 201
    v = r.json()["latest_version"]
    assert v["encrypted"] is True and v["pages"] is None


# ---- metadata ----------------------------------------------------------------------------
def info(data: bytes) -> dict:
    with pikepdf.open(io.BytesIO(data)) as pdf:
        return {str(k)[1:]: str(v) for k, v in pdf.docinfo.items()}


def test_metadata_set_update_and_remove_fields(client):
    a = run_tool(
        client,
        "metadata",
        {"title": "Report", "author": "Pablo", "keywords": "a,b"},
        [("a.pdf", make_pdf(1))],
    ).content
    assert info(a)["Title"] == "Report" and info(a)["Author"] == "Pablo"
    b = run_tool(client, "metadata", {"title": "New", "author": ""}, [("a.pdf", a)]).content
    assert info(b)["Title"] == "New"
    assert "Author" not in info(b)
    assert info(b)["Keywords"] == "a,b"  # untouched fields survive


def test_metadata_clear_all(client):
    a = run_tool(
        client, "metadata", {"title": "T", "author": "A"}, [("a.pdf", make_pdf(1))]
    ).content
    b = run_tool(client, "metadata", {"clear_all": True}, [("a.pdf", a)]).content
    assert "Title" not in info(b) and "Author" not in info(b)
    assert page_count(b) == 1


def test_metadata_read_endpoint(client):
    doc = client.post(
        "/api/v1/documents", files={"file": ("a.pdf", make_pdf(4), "application/pdf")}
    ).json()
    vid = doc["latest_version"]["id"]
    m = client.get(f"/api/v1/versions/{vid}/metadata")
    assert m.status_code == 200
    body = m.json()
    assert body["pages"] == 4 and "info" in body and body["encrypted"] is False


def test_metadata_read_endpoint_encrypted_is_409(client):
    locked = run_tool(client, "protect", {"password": "pw"}, [("a.pdf", make_pdf(1))]).content
    doc = client.post(
        "/api/v1/documents", files={"file": ("l.pdf", locked, "application/pdf")}
    ).json()
    r = client.get(f"/api/v1/versions/{doc['latest_version']['id']}/metadata")
    assert r.status_code == 409


@pytest.mark.parametrize("tool", ["protect", "unlock", "metadata"])
def test_tools_listed(client, tool):
    assert tool in {t["id"] for t in client.get("/api/v1/tools").json()}
