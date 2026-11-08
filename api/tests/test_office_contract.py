"""O4: generic office contract (accepts=office, availability, allowlist, warnings, busy)."""
import io
import sqlite3
import zipfile

import pytest
from pydantic import BaseModel

from doctool import officecore
from doctool.db import make_session_factory
from doctool.tools.base import ToolError, ToolOutput, registry
from doctool.tools.officebase import OfficeTool
from tests.pdfs import make_pdf

CT = b'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>'


def docx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", CT)
        z.writestr("word/document.xml", b"<w:document/>")
    return buf.getvalue()


class NoParams(BaseModel):
    pass


class FakeWord(OfficeTool):
    id = "fakeword"
    title = "Fake Word"
    group = "office"
    Params = NoParams
    extensions = ("docx", "odt")
    mode = "ok"

    def run(self, inputs, params):
        if self.mode == "busy":
            raise ToolError("busy", "The server is busy. Try again in a moment.", retryable=True)
        pdf = self.lo_convert(inputs[0].data, inputs[0].name, "pdf")
        warns = [{"code": "font_substituted", "params": {"fonts": "Calibri"}}]
        return [ToolOutput("out.pdf", pdf, warnings=warns)]


@pytest.fixture
def fake_word():
    tool = FakeWord()
    registry.register(tool)
    yield tool
    registry.unregister("fakeword")


@pytest.fixture
def lo_present(monkeypatch, tmp_path):
    exe = tmp_path / "soffice.exe"
    exe.write_bytes(b"x")
    monkeypatch.setattr(officecore, "find_soffice", lambda *a, **k: exe)
    monkeypatch.setattr(officecore, "convert", lambda *a, **k: make_pdf(1))
    return exe


def make_task(client):
    r = client.post("/api/v1/tasks", json={"tool": "fakeword", "params": {}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def upload(client, tid, name, data):
    return client.post(f"/api/v1/tasks/{tid}/files", files={"file": (name, data)})


# ---------- listing ----------
def test_tools_listing_reports_availability_and_extensions(client, fake_word, lo_present):
    tool = {t["id"]: t for t in client.get("/api/v1/tools").json()}["fakeword"]
    assert tool["accepts"] == "office"
    assert tool["available"] is True
    assert tool["requires"] == ["libreoffice"]
    assert tool["extensions"] == ["docx", "odt"]


def test_tools_listing_marks_missing_engine(client, fake_word, monkeypatch):
    monkeypatch.setattr(officecore, "find_soffice", lambda *a, **k: None)
    tools = {t["id"]: t for t in client.get("/api/v1/tools").json()}
    assert tools["fakeword"]["available"] is False


def test_pdf_tools_are_available_without_requirements(client):
    merge = {t["id"]: t for t in client.get("/api/v1/tools").json()}["merge"]
    assert merge["available"] is True and merge["requires"] == [] and merge["extensions"] == []


# ---------- upload allowlist ----------
def test_upload_accepts_listed_extension(client, fake_word, lo_present):
    tid = make_task(client)
    assert upload(client, tid, "Report.DOCX", docx_bytes()).status_code == 201


@pytest.mark.parametrize("name,state", [("evil.docm", "macro"), ("sheet.xlsx", "unsupported"),
                                         ("notes.pdf", "unsupported"), ("noext", "unsupported")])
def test_upload_rejects_other_extensions(client, fake_word, lo_present, name, state):
    tid = make_task(client)
    r = upload(client, tid, name, docx_bytes())
    assert r.status_code == 422
    assert r.json()["detail"]["state"] == state


def test_upload_rejects_hostile_package(client, fake_word, lo_present):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", CT)
        z.writestr("word/vbaProject.bin", b"x")
    tid = make_task(client)
    r = upload(client, tid, "a.docx", buf.getvalue())
    assert r.status_code == 422 and r.json()["detail"]["state"] == "macro"


# ---------- process: warnings, busy, engine missing ----------
def test_warnings_are_returned_and_persisted(client, fake_word, lo_present):
    tid = make_task(client)
    upload(client, tid, "a.docx", docx_bytes())
    r = client.post(f"/api/v1/tasks/{tid}/process")
    assert r.status_code == 200, r.text
    expected = [{"code": "font_substituted", "params": {"fonts": "Calibri"}}]
    assert r.json()["warnings"] == expected
    assert client.get(f"/api/v1/tasks/{tid}").json()["warnings"] == expected


def test_task_without_warnings_has_empty_list(client, fake_word, lo_present):
    tid = make_task(client)
    assert client.get(f"/api/v1/tasks/{tid}").json()["warnings"] == []


def test_busy_maps_to_503_and_keeps_task_waiting(client, fake_word, lo_present):
    tid = make_task(client)
    upload(client, tid, "a.docx", docx_bytes())
    fake_word.mode = "busy"
    try:
        r = client.post(f"/api/v1/tasks/{tid}/process")
    finally:
        fake_word.mode = "ok"
    assert r.status_code == 503
    assert r.json()["detail"] == {
        "state": "busy", "message": "The server is busy. Try again in a moment.", "retryable": True,
    }
    assert client.get(f"/api/v1/tasks/{tid}").json()["state"] == "waiting"
    assert client.post(f"/api/v1/tasks/{tid}/process").status_code == 200  # retry works


def test_engine_missing_at_run_time(client, fake_word, lo_present, monkeypatch):
    tid = make_task(client)
    upload(client, tid, "a.docx", docx_bytes())
    monkeypatch.setattr(officecore, "find_soffice", lambda *a, **k: None)
    r = client.post(f"/api/v1/tasks/{tid}/process")
    assert r.status_code == 400
    assert r.json()["detail"]["state"] == "engine_missing"


# ---------- schema migration ----------
def test_existing_database_gains_warnings_column(tmp_path):
    path = tmp_path / "old.sqlite3"
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE task (id VARCHAR(32) PRIMARY KEY, tool VARCHAR(64), params JSON, "
        "state VARCHAR(32), error VARCHAR(1000), created_at DATETIME, finished_at DATETIME)"
    )
    con.commit()
    con.close()
    factory = make_session_factory(path)
    cols = [r[1] for r in factory.kw["bind"].connect().exec_driver_sql("PRAGMA table_info(task)")]
    assert "warnings" in cols
    factory.kw["bind"].dispose()
