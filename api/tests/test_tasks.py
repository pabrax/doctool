import io
import zipfile
from typing import Literal

import pytest
from pydantic import BaseModel, Field

from doctool.tools.base import Tool, ToolError, ToolOutput, registry
from tests.pdfs import make_pdf


class EchoParams(BaseModel):
    copies: int = Field(1, ge=1, le=3)
    mode: Literal["ok", "damaged", "password"] = "ok"
    secret: str | None = Field(None, json_schema_extra={"secret": True})


class EchoTool(Tool):
    id = "echo"
    title = "Echo"
    group = "test"
    Params = EchoParams
    min_files = 1
    max_files = 2

    def run(self, inputs, params):
        if params.mode == "damaged":
            raise ToolError("damaged", "file is damaged")
        if params.mode == "password" and not inputs[0].password:
            raise ToolError("wrong_password", "password required", retryable=True)
        return [ToolOutput(f"out{i}.pdf", inputs[0].data) for i in range(params.copies)]


@pytest.fixture(autouse=True)
def echo_tool():
    registry.register(EchoTool())
    yield
    registry.unregister("echo")


def mk_task(client, **params):
    r = client.post("/api/v1/tasks", json={"tool": "echo", "params": params})
    assert r.status_code == 201, r.text
    return r.json()


def add_file(client, task_id, data=None, name="in.pdf"):
    return client.post(
        f"/api/v1/tasks/{task_id}/files",
        files={"file": (name, data or make_pdf(2), "application/pdf")},
    )


def test_tools_listing_has_schema(client):
    tools = {t["id"]: t for t in client.get("/api/v1/tools").json()}
    assert tools["echo"]["params_schema"]["properties"]["copies"]["maximum"] == 3
    assert tools["echo"]["min_files"] == 1


def test_create_unknown_tool_404(client):
    assert client.post("/api/v1/tasks", json={"tool": "nope", "params": {}}).status_code == 404


def test_create_invalid_params_422_with_field_path(client):
    r = client.post("/api/v1/tasks", json={"tool": "echo", "params": {"copies": 9}})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["copies"]


def test_add_files_and_unknown_version(client):
    t = mk_task(client)
    assert add_file(client, t["id"]).status_code == 201
    r = client.post(f"/api/v1/tasks/{t['id']}/files", data={"version_id": "nope"})
    assert r.status_code == 404
    assert client.post(f"/api/v1/tasks/{t['id']}/files").status_code == 422


def test_process_requires_min_and_max_files(client):
    t = mk_task(client)
    assert client.post(f"/api/v1/tasks/{t['id']}/process").status_code == 422
    for _ in range(3):
        add_file(client, t["id"])
    assert client.post(f"/api/v1/tasks/{t['id']}/process").status_code == 422


def test_process_success_saves_to_library_and_downloads(client):
    t = mk_task(client)
    add_file(client, t["id"])
    r = client.post(f"/api/v1/tasks/{t['id']}/process")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "success"
    out = [f for f in body["files"] if f["role"] == "out"]
    assert len(out) == 1 and out[0]["version_id"]
    assert len(client.get("/api/v1/documents").json()) == 1
    d = client.get(f"/api/v1/tasks/{t['id']}/download")
    assert d.status_code == 200 and d.content.startswith(b"%PDF")


def test_multiple_outputs_download_as_zip(client):
    t = mk_task(client, copies=2)
    add_file(client, t["id"])
    assert client.post(f"/api/v1/tasks/{t['id']}/process").status_code == 200
    d = client.get(f"/api/v1/tasks/{t['id']}/download")
    assert d.headers["content-type"] == "application/zip"
    assert sorted(zipfile.ZipFile(io.BytesIO(d.content)).namelist()) == ["out0.pdf", "out1.pdf"]


def test_library_input_creates_child_version_of_same_document(client):
    doc = client.post(
        "/api/v1/documents", files={"file": ("a.pdf", make_pdf(2), "application/pdf")}
    ).json()
    v1 = doc["latest_version"]["id"]
    t = mk_task(client)
    client.post(f"/api/v1/tasks/{t['id']}/files", data={"version_id": v1})
    assert client.post(f"/api/v1/tasks/{t['id']}/process").status_code == 200
    versions = client.get(f"/api/v1/documents/{doc['id']}/versions").json()
    assert [v["seq"] for v in versions] == [1, 2]
    assert versions[1]["parent_version_id"] == v1 and versions[1]["tool"] == "echo"
    assert len(client.get("/api/v1/documents").json()) == 1


def test_save_to_library_false_keeps_library_empty(client):
    t = mk_task(client)
    add_file(client, t["id"])
    r = client.post(f"/api/v1/tasks/{t['id']}/process", json={"save_to_library": False})
    assert r.status_code == 200
    assert client.get("/api/v1/documents").json() == []
    assert client.get(f"/api/v1/tasks/{t['id']}/download").status_code == 200


def test_damaged_sets_error_state(client):
    t = mk_task(client, mode="damaged")
    add_file(client, t["id"])
    r = client.post(f"/api/v1/tasks/{t['id']}/process")
    assert r.status_code == 400 and r.json()["detail"]["state"] == "damaged"
    assert client.get(f"/api/v1/tasks/{t['id']}").json()["state"] == "error"


def test_wrong_password_keeps_task_waiting_then_retry_succeeds(client):
    t = mk_task(client, mode="password")
    fid = add_file(client, t["id"]).json()["files"][0]["id"]
    r = client.post(f"/api/v1/tasks/{t['id']}/process")
    assert r.status_code == 400 and r.json()["detail"]["state"] == "wrong_password"
    assert client.get(f"/api/v1/tasks/{t['id']}").json()["state"] == "waiting"
    r = client.post(f"/api/v1/tasks/{t['id']}/process", json={"passwords": {fid: "pw"}})
    assert r.status_code == 200 and r.json()["state"] == "success"


def test_secret_params_are_redacted_in_history(client):
    t = mk_task(client, secret="hunter2")
    add_file(client, t["id"])
    client.post(f"/api/v1/tasks/{t['id']}/process")
    assert "hunter2" not in str(client.get(f"/api/v1/tasks/{t['id']}").json())
    doc = client.get("/api/v1/documents").json()[0]
    assert doc["latest_version"]["params"]["secret"] == "***"


def test_debug_echoes_without_processing(client):
    t = mk_task(client, copies=2)
    add_file(client, t["id"])
    r = client.post(f"/api/v1/tasks/{t['id']}/process?debug=true")
    assert r.status_code == 200 and r.json()["params"]["copies"] == 2
    assert client.get("/api/v1/documents").json() == []


def test_delete_task(client):
    t = mk_task(client)
    assert client.delete(f"/api/v1/tasks/{t['id']}").status_code == 204
    assert client.get(f"/api/v1/tasks/{t['id']}").status_code == 404
