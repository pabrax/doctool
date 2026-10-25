import pytest
from fastapi.testclient import TestClient

from doctool.config import Settings
from doctool.main import create_app
from tests.pdfs import make_pdf


@pytest.fixture
def web_dir(tmp_path):
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>doctool-shell</title>")
    (root / "assets" / "app.js").write_text("console.log('app')")
    (root / "fonts").mkdir()
    (root / "fonts" / "f.woff2").write_bytes(b"wOF2")
    (tmp_path / "secret.txt").write_text("TOP-SECRET")
    return root


@pytest.fixture
def served(tmp_path, web_dir, db_template):
    import shutil

    settings = Settings(
        data_dir=tmp_path / "data", web_dir=web_dir, allowed_hosts=["testserver", "localhost"]
    )
    settings.data_dir.mkdir()
    shutil.copy(db_template, settings.db_path)
    with TestClient(create_app(settings)) as c:
        yield c


# ---- static web ---------------------------------------------------------------------------
def test_root_and_spa_routes_serve_index(served):
    for path in ("/", "/library/abc123", "/tools/merge", "/organize/v1"):
        r = served.get(path)
        assert r.status_code == 200 and "doctool-shell" in r.text, path
        assert r.headers["content-type"].startswith("text/html")


def test_woff2_is_served_with_a_font_content_type(served):
    r = served.get("/fonts/f.woff2")
    assert r.status_code == 200
    assert r.headers["content-type"] == "font/woff2"


def test_assets_are_served_with_cache_headers(served):
    r = served.get("/assets/app.js")
    assert r.status_code == 200 and "console.log" in r.text
    assert "immutable" in r.headers["cache-control"]


def test_unknown_api_path_is_json_404_not_the_spa(served):
    r = served.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    assert "doctool-shell" not in r.text


def test_missing_asset_is_404_not_index(served):
    assert served.get("/assets/missing.js").status_code == 404


@pytest.mark.parametrize(
    "path",
    ["/..%2fsecret.txt", "/%2e%2e/secret.txt", "/assets/..%2f..%2fsecret.txt", "/....//secret.txt"],
)
def test_path_traversal_never_leaks_files(served, path):
    r = served.get(path)
    assert "TOP-SECRET" not in r.text


def test_api_still_works_next_to_static(served):
    assert served.get("/api/v1/health").json()["status"] == "ok"


def test_no_web_dir_means_api_only(client):
    assert client.get("/").status_code == 404


# ---- headers ------------------------------------------------------------------------------
def test_html_shell_has_a_strict_csp(served):
    csp = served.get("/").headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp and "unsafe-eval" not in csp
    assert "frame-ancestors 'self'" in csp
    assert "object-src 'self'" in csp  # own PDF previews


def test_all_responses_get_basic_security_headers(served):
    for path in ("/", "/api/v1/health"):
        h = served.get(path).headers
        assert h["x-content-type-options"] == "nosniff"
        assert h["referrer-policy"] == "no-referrer"
        assert h["x-frame-options"] == "SAMEORIGIN"


def test_user_content_is_served_nosniff(client):
    doc = client.post(
        "/api/v1/documents", files={"file": ("a.pdf", make_pdf(1), "application/pdf")}
    ).json()
    r = client.get(f"/api/v1/versions/{doc['latest_version']['id']}/download")
    assert r.headers["x-content-type-options"] == "nosniff"


# ---- DNS rebinding / cross-site writes ----------------------------------------------------
def test_foreign_host_header_is_rejected(served):
    r = served.get("/api/v1/health", headers={"host": "evil.example"})
    assert r.status_code == 400


def test_allowed_host_with_port_is_accepted(served):
    r = served.get("/api/v1/health", headers={"host": "localhost:8000"})
    assert r.status_code == 200


def test_cross_origin_writes_are_forbidden(served):
    files = {"file": ("a.pdf", make_pdf(1), "application/pdf")}
    r = served.post("/api/v1/documents", files=files, headers={"origin": "https://evil.example"})
    assert r.status_code == 403
    assert served.get("/api/v1/documents").json() == []


def test_same_site_dev_origin_and_no_origin_are_allowed(served):
    files = {"file": ("a.pdf", make_pdf(1), "application/pdf")}
    ok = served.post("/api/v1/documents", files=files, headers={"origin": "http://localhost:5173"})
    assert ok.status_code == 201
    files = {"file": ("b.pdf", make_pdf(1), "application/pdf")}
    assert served.post("/api/v1/documents", files=files).status_code == 201  # curl / scripts


def test_cross_origin_reads_stay_possible_only_via_cors_allowlist(served):
    r = served.get("/api/v1/health", headers={"origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


# ---- settings from the environment --------------------------------------------------------
def test_settings_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DOCTOOL_DATA_DIR", str(tmp_path / "d"))
    monkeypatch.setenv("DOCTOOL_PORT", "9123")
    monkeypatch.setenv("DOCTOOL_ALLOWED_HOSTS", "a.local, b.local")
    s = Settings.from_env()
    assert s.data_dir == tmp_path / "d" and s.port == 9123
    assert s.allowed_hosts == ["a.local", "b.local"]
    assert s.host == "127.0.0.1"


def test_binding_beyond_localhost_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("DOCTOOL_HOST", "0.0.0.0")
    with pytest.raises(ValueError, match="DOCTOOL_ALLOW_LAN"):
        Settings.from_env()
    monkeypatch.setenv("DOCTOOL_ALLOW_LAN", "1")
    assert Settings.from_env().host == "0.0.0.0"
