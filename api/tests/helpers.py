import io
import zipfile


def run_tool(client, tool, params, files, expect=200, passwords=None):
    """Drive the real task API. `files` = [(name, bytes[, mime])]; `passwords` aligned to files."""
    t = client.post("/api/v1/tasks", json={"tool": tool, "params": params})
    assert t.status_code == 201, t.text
    tid = t.json()["id"]
    file_ids = []
    for item in files:
        name, data = item[0], item[1]
        mime = item[2] if len(item) > 2 else "application/pdf"
        r = client.post(f"/api/v1/tasks/{tid}/files", files={"file": (name, data, mime)})
        assert r.status_code == 201, r.text
        file_ids.append(r.json()["files"][-1]["id"])
    pw = {fid: p for fid, p in zip(file_ids, passwords or [], strict=False) if p}
    r = client.post(f"/api/v1/tasks/{tid}/process", json={"passwords": pw})
    assert r.status_code == expect, r.text
    if expect != 200:
        return r
    return client.get(f"/api/v1/tasks/{tid}/download")


def outputs(resp):
    """Return list[(name, bytes)] for a pdf or zip download."""
    if resp.headers["content-type"] == "application/zip":
        z = zipfile.ZipFile(io.BytesIO(resp.content))
        return [(n, z.read(n)) for n in sorted(z.namelist())]
    return [("single", resp.content)]
