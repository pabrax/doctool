"""O3: LibreOffice discovery, hostile-document guards and the sandboxed runner."""
import io
import os
import subprocess
import sys
import time
import zipfile

import pikepdf
import pytest

from doctool import officecore as oc
from doctool.config import Settings


def make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


CT = b'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>'
DOCX = {"[Content_Types].xml": CT, "word/document.xml": b"<w:document/>"}


# ---------- discovery ----------
def test_find_soffice_env_wins(tmp_path):
    exe = tmp_path / "mysoffice.exe"
    exe.write_bytes(b"x")
    assert oc.find_soffice({"DOCTOOL_SOFFICE": str(exe)}, which=lambda n: None) == exe


def test_find_soffice_bad_env_falls_back_to_path(tmp_path):
    exe = tmp_path / "soffice"
    exe.write_bytes(b"x")
    found = oc.find_soffice(
        {"DOCTOOL_SOFFICE": str(tmp_path / "nope")},
        which=lambda n: str(exe) if n == "soffice" else None,
    )
    assert found == exe


def test_find_soffice_none_when_absent(tmp_path):
    assert oc.find_soffice({}, which=lambda n: None, defaults=[tmp_path / "missing"]) is None


# ---------- kind / allowlist ----------
@pytest.mark.parametrize(
    "name,ext",
    [("Report.DOCX", "docx"), ("a.b.xlsx", "xlsx"), ("s.pptx", "pptx"), ("t.csv", "csv")],
)
def test_source_ext_allowed(name, ext):
    assert oc.source_ext(name) == ext


@pytest.mark.parametrize("name", ["evil.docm", "evil.xlsm", "evil.pptm", "x.dotm"])
def test_macro_enabled_extensions_rejected(name):
    with pytest.raises(oc.OfficeError) as e:
        oc.source_ext(name)
    assert e.value.state == "macro"


@pytest.mark.parametrize("name", ["a.exe", "noext", "a.pdf", "../../etc/passwd"])
def test_other_extensions_unsupported(name):
    with pytest.raises(oc.OfficeError) as e:
        oc.source_ext(name)
    assert e.value.state == "unsupported"


# ---------- package guards ----------
def test_guard_accepts_plain_docx():
    rep = oc.guard_package(make_zip(DOCX), "docx")
    assert rep.warnings == []


def test_guard_rejects_non_zip_ooxml():
    with pytest.raises(oc.OfficeError) as e:
        oc.guard_package(b"definitely not a zip", "docx")
    assert e.value.state == "damaged"


def test_guard_rejects_vba_project():
    data = make_zip({**DOCX, "word/vbaProject.bin": b"\xd0\xcf"})
    with pytest.raises(oc.OfficeError) as e:
        oc.guard_package(data, "docx")
    assert e.value.state == "macro"


def test_guard_rejects_macro_content_type():
    macro = b"application/vnd.ms-word.document.macroEnabled.main+xml"
    ov = b'><Override PartName="/word/document.xml" ContentType="' + macro + b'"/></Types>'
    ct = CT.replace(b"/>", ov, 1)
    data = make_zip({"[Content_Types].xml": ct, "word/document.xml": b"<a/>"})
    with pytest.raises(oc.OfficeError) as e:
        oc.guard_package(data, "docx")
    assert e.value.state == "macro"


def test_guard_too_many_entries():
    data = make_zip({f"f{i}.xml": b"<a/>" for i in range(50)})
    with pytest.raises(oc.OfficeError) as e:
        oc.guard_package(data, "docx", max_entries=10)
    assert e.value.state == "too_large"


def test_guard_uncompressed_size_and_ratio():
    bomb = make_zip({**DOCX, "word/big.xml": b"\0" * 3_000_000})
    with pytest.raises(oc.OfficeError) as e:
        oc.guard_package(bomb, "docx", max_uncompressed=1_000_000)
    assert e.value.state == "too_large"
    with pytest.raises(oc.OfficeError) as e2:
        oc.guard_package(bomb, "docx", max_uncompressed=10**9, max_ratio=50)
    assert e2.value.state == "too_large"


def test_guard_rejects_xml_entities():
    evil = b'<?xml version="1.0"?><!DOCTYPE a [<!ENTITY x "boom">]><a>&x;</a>'
    with pytest.raises(oc.OfficeError) as e:
        oc.guard_package(make_zip({**DOCX, "word/document.xml": evil}), "docx")
    assert e.value.state == "unsafe"


def test_guard_warns_external_links():
    rels = (
        b'<Relationships><Relationship Id="1" Type="x" Target="http://e.com/a.png"'
        b' TargetMode="External"/></Relationships>'
    )
    rep = oc.guard_package(make_zip({**DOCX, "word/_rels/document.xml.rels": rels}), "docx")
    assert "external_links" in rep.warnings


def test_guard_password_protected_ooxml():
    # encrypted OOXML is an OLE/CFB container holding an EncryptedPackage stream
    ole = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    data = ole + "EncryptedPackage".encode("utf-16-le") + b"\0" * 64
    with pytest.raises(oc.OfficeError) as e:
        oc.guard_package(data, "xlsx")
    assert e.value.state == "wrong_password"


def test_guard_ignores_flat_formats():
    assert oc.guard_package(b"a,b\n1,2\n", "csv").warnings == []


# ---------- profile ----------
def test_prepare_profile_disables_macros(tmp_path):
    oc.prepare_profile(tmp_path / "prof")
    xcu = (tmp_path / "prof" / "user" / "registrymodifications.xcu").read_text(encoding="utf-8")
    assert "MacroSecurityLevel" in xcu and ">3<" in xcu.replace(" ", "")


# ---------- process runner ----------
def _alive(pid: int) -> bool:
    if os.name == "nt":
        res = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True)
        return str(pid) in res.stdout.decode("cp437", errors="replace")
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def test_run_process_ok(tmp_path):
    rc, _ = oc.run_process([sys.executable, "-c", "print('hi')"], cwd=tmp_path, timeout=20)
    assert rc == 0


def test_run_process_timeout_kills_whole_tree(tmp_path):
    pidfile = tmp_path / "child.pid"
    code = (
        "import subprocess,sys,time;"
        f"c=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
        f"open(r'{pidfile}','w').write(str(c.pid));time.sleep(60)"
    )
    with pytest.raises(oc.OfficeError) as e:
        oc.run_process([sys.executable, "-c", code], cwd=tmp_path, timeout=2.5)
    assert e.value.state == "timeout" and e.value.retryable is False
    pid = int(pidfile.read_text())
    deadline = time.time() + 5
    while _alive(pid) and time.time() < deadline:
        time.sleep(0.2)
    assert not _alive(pid)


# ---------- slot ----------
def test_slot_is_exclusive_and_reports_busy():
    slot = oc.OfficeSlot()
    with slot.hold(wait=0.1):
        with pytest.raises(oc.OfficeError) as e:
            with slot.hold(wait=0.05):
                pass
        assert e.value.state == "busy" and e.value.retryable is True
    with slot.hold(wait=0.1):  # released afterwards
        pass


# ---------- config ----------
def test_office_settings_from_env(monkeypatch):
    monkeypatch.setenv("DOCTOOL_OFFICE_TIMEOUT_SECONDS", "90")
    monkeypatch.setenv("DOCTOOL_OFFICE_MAX_ENTRIES", "bad")
    s = Settings.from_env()
    assert s.office_timeout_seconds == 90
    assert s.office_max_entries == Settings().office_max_entries


# ---------- convert (real LibreOffice, skipped when absent) ----------
SOFFICE = oc.find_soffice()
needs_lo = pytest.mark.skipif(SOFFICE is None, reason="LibreOffice not installed")


def test_convert_without_engine_reports_engine_missing(tmp_path):
    with pytest.raises(oc.OfficeError) as e:
        oc.convert(b"a,b\n", "csv", "pdf", soffice=None, work_dir=tmp_path)
    assert e.value.state == "engine_missing"


@needs_lo
@pytest.mark.office
def test_convert_csv_to_pdf_and_cleans_up(tmp_path):
    csv = b"name,value\none,1\ntwo,2\n"
    pdf = oc.convert(csv, "csv", "pdf", soffice=SOFFICE, work_dir=tmp_path, timeout=120)
    assert pdf.startswith(b"%PDF")
    assert len(pikepdf.open(io.BytesIO(pdf)).pages) == 1
    assert [p.name for p in tmp_path.iterdir() if p.name != "profile"] == []  # job dirs removed


@needs_lo
@pytest.mark.office
def test_convert_garbage_docx_is_rejected_before_libreoffice(tmp_path):
    with pytest.raises(oc.OfficeError) as e:
        oc.convert(b"garbage", "docx", "pdf", soffice=SOFFICE, work_dir=tmp_path)
    assert e.value.state == "damaged"


# ---------- first run: profile warm-up ----------
def test_warm_up_without_engine_is_a_noop(tmp_path):
    assert oc.warm_up(None, tmp_path) is False
    assert not (tmp_path / "profile").exists()


def test_first_run_gets_a_longer_timeout(tmp_path):
    assert oc.effective_timeout(tmp_path, 60) == oc.FIRST_RUN_TIMEOUT
    (tmp_path / "profile").mkdir()
    (tmp_path / "profile" / oc.READY_MARK).write_text("ok")
    assert oc.effective_timeout(tmp_path, 60) == 60


@needs_lo
@pytest.mark.office
def test_warm_up_prepares_the_profile_once(tmp_path):
    assert oc.warm_up(SOFFICE, tmp_path) is True
    assert oc.profile_ready(tmp_path)
    assert oc.warm_up(SOFFICE, tmp_path) is False  # already warm: nothing to do


def test_requests_wait_for_the_warm_up_instead_of_busy():
    assert oc.slot_wait(0.5) == 0.5
    oc.WARMING.set()
    try:
        assert oc.slot_wait(0.5) == oc.FIRST_RUN_TIMEOUT
    finally:
        oc.WARMING.clear()


def test_warm_up_can_be_switched_off_from_the_environment(monkeypatch):
    assert Settings.from_env().office_warmup is True
    monkeypatch.setenv("DOCTOOL_OFFICE_WARMUP", "0")
    assert Settings.from_env().office_warmup is False
