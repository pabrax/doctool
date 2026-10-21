import io
import zipfile


def run_tool(client, tool, params, files, expect=200, passwords=None):
    t = client.post("/api/v1/tasks", json={"tool": tool, "params": params})
    assert t.status_code == 201, t.text
    tid = t.json()["id"]
    for name, data in files:
        r = client.post(
            f"/api/v1/tasks/{tid}/files", files={"file": (name, data, "application/pdf")}
        )
        assert r.status_code == 201, r.text
    r = client.post(f"/api/v1/tasks/{tid}/process", json={"passwords": passwords or {}})
    assert r.status_code == expect, r.text
    if expect != 200:
        return r
    d = client.get(f"/api/v1/tasks/{tid}/download")
    return d


def outputs(resp):
    """Return list[(name, bytes)] for a pdf or zip download."""
    if resp.headers["content-type"] == "application/zip":
        z = zipfile.ZipFile(io.BytesIO(resp.content))
        return [(n, z.read(n)) for n in sorted(z.namelist())]
    return [("single", resp.content)]
