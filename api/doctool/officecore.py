"""Office engine: LibreOffice discovery, hostile-document guards and a sandboxed runner.

LibreOffice is only ever started as an external process (never linked). Every input is
treated as hostile: extension allowlist, package/zip-bomb/XML-entity guards, macros refused,
a per-job temp dir with a fixed file name (the upload name never reaches argv), a macro-locked
persistent profile, one job at a time, a hard timeout that kills the whole process tree.
"""
from __future__ import annotations

import contextlib
import os
import posixpath
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import zipfile
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from doctool.config import Settings

OOXML = {"docx", "xlsx", "pptx"}
ODF = {"odt", "ods", "odp"}
ZIPPED = OOXML | ODF
FLAT = {"doc", "xls", "ppt", "rtf", "txt", "csv", "html", "htm"}
ALLOWED_EXT = ZIPPED | FLAT
# Conversion sources that are never office uploads: PDF goes in only through the PDF tools
# (already checked as a PDF) for LibreOffice's "keep the look" import.
CONVERT_ONLY_EXT = {"pdf"}
MACRO_EXT = {"docm", "xlsm", "pptm", "dotm", "xltm", "potm", "ppsm", "xlam"}

_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ENCRYPTED_PACKAGE = "EncryptedPackage".encode("utf-16-le")
_XML_SNIFF = 64 * 1024  # bytes of each XML part scanned for DTD/entity declarations


_PWD_MSG = "the file is password protected; remove the password first"
_MACRO_MSG = "the document contains macros; save a copy without macros"


class OfficeError(Exception):
    """Expected, user-facing failure; `state` follows the per-file states of the task API."""

    def __init__(self, state: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.state = state
        self.message = message
        self.retryable = retryable


@dataclass
class PackageReport:
    warnings: list[str] = field(default_factory=list)


# ---------- discovery ----------
def _default_locations() -> list[Path]:
    if sys.platform == "win32":
        roots = [os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
        return [Path(r) / "LibreOffice" / "program" / "soffice.exe" for r in roots]
    return [Path("/usr/bin/soffice"), Path("/usr/lib/libreoffice/program/soffice"),
            Path("/opt/libreoffice/program/soffice"),
            Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")]


def find_soffice(
    env: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
    defaults: list[Path] | None = None,
) -> Path | None:
    """DOCTOOL_SOFFICE, then PATH, then the usual install dirs. None when not installed."""
    env = os.environ if env is None else env
    if (v := env.get("DOCTOOL_SOFFICE")) and Path(v).is_file():
        return Path(v)
    for name in ("soffice", "libreoffice"):
        if (found := which(name)) and Path(found).is_file():
            return Path(found)
    for cand in _default_locations() if defaults is None else defaults:
        if cand.is_file():
            return cand
    return None


# ---------- input allowlist and package guards ----------
def source_ext(filename: str) -> str:
    """Lower-case extension of an upload, only if it is an allowed office source."""
    ext = posixpath.basename(filename.replace("\\", "/")).rpartition(".")[2].lower()
    if ext in MACRO_EXT:
        raise OfficeError("macro", "macro-enabled files are not accepted; save a copy without them")
    if ext not in ALLOWED_EXT or "." not in filename:
        raise OfficeError("unsupported", "unsupported office file type")
    return ext


def guard_package(
    data: bytes,
    ext: str,
    *,
    max_entries: int = 5000,
    max_uncompressed: int = 500 * 1024 * 1024,
    max_ratio: int = 200,
) -> PackageReport:
    """Reject hostile OOXML/ODF packages before LibreOffice sees them."""
    report = PackageReport()
    if ext not in ZIPPED:
        if ext in {"doc", "xls", "ppt"} and not data.startswith(_OLE_MAGIC):
            raise OfficeError("damaged", "not a valid legacy Office file")
        return report
    if data.startswith(_OLE_MAGIC):
        if _ENCRYPTED_PACKAGE in data[:1_000_000]:
            raise OfficeError("wrong_password", _PWD_MSG)
        raise OfficeError("damaged", "not a valid Office package")
    try:
        zf = zipfile.ZipFile(BytesIO(data))
        infos = zf.infolist()
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
        raise OfficeError("damaged", "the file is damaged or not an Office document") from exc
    with zf:
        if len(infos) > max_entries:
            raise OfficeError("too_large", "the document package has too many parts")
        total = sum(i.file_size for i in infos)
        packed = max(1, sum(i.compress_size for i in infos))
        if total > max_uncompressed or total / packed > max_ratio:
            raise OfficeError("too_large", "the document expands to an unsafe size")
        for info in infos:
            name = info.filename
            if name.startswith("/") or ".." in name.split("/"):
                raise OfficeError("unsafe", "the document contains an unsafe path")
            if info.flag_bits & 0x1:
                raise OfficeError("wrong_password", _PWD_MSG)
            low = name.lower()
            if low.endswith("vbaproject.bin") or low.startswith("macros/") or "/basic/" in low:
                raise OfficeError("macro", _MACRO_MSG)
            if low.endswith((".xml", ".rels")):
                head = zf.open(info).read(_XML_SNIFF)
                if b"<!ENTITY" in head or (b"<!DOCTYPE" in head and b"[" in head):
                    raise OfficeError("unsafe", "the document contains XML entity declarations")
                if low == "[content_types].xml" and b"macroenabled" in head.lower():
                    raise OfficeError("macro", _MACRO_MSG)
                if low.endswith(".rels") and re.search(rb'TargetMode="External"', head):
                    if "external_links" not in report.warnings:
                        report.warnings.append("external_links")
    return report


# ---------- profile ----------
_MACRO_LOCK = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<oor:items xmlns:oor="http://openoffice.org/2001/registry" '
    'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
    '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
    '<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>\n'
    '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
    '<prop oor:name="DisableMacrosExecution" oor:op="fuse"><value>true</value></prop></item>\n'
    '<item oor:path="/org.openoffice.Office.Common/Misc">'
    '<prop oor:name="FirstRun" oor:op="fuse"><value>false</value></prop></item>\n'
    "</oor:items>\n"
)


def prepare_profile(profile_dir: Path) -> None:
    """Create a LibreOffice profile with macros locked to the highest security level."""
    user = profile_dir / "user"
    user.mkdir(parents=True, exist_ok=True)
    (user / "registrymodifications.xcu").write_text(_MACRO_LOCK, encoding="utf-8")


# ---------- process runner ----------
def _kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        cmd = ["taskkill", "/PID", str(proc.pid), "/T", "/F"]
        subprocess.run(cmd, capture_output=True, check=False)
    else:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGKILL)
    with contextlib.suppress(Exception):
        proc.kill()


def run_process(argv: list[str], *, cwd: Path, timeout: float) -> tuple[int, str]:
    """Run argv (no shell, no stdin) and kill the whole process tree on timeout.

    Output goes to a log file in `cwd`, not to a pipe: LibreOffice helpers (e.g. xpdfimport for
    PDF import) inherit the handles and can keep a pipe open after soffice exits, which would
    make a pipe reader wait until the timeout."""
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    log = cwd / "process.log"
    with open(log, "wb") as out:
        proc = subprocess.Popen(  # noqa: S603 - argv list, fixed names, shell=False
            argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
            **kwargs,
        )
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            _kill_tree(proc)
            with contextlib.suppress(Exception):
                proc.wait(timeout=5)
            raise OfficeError("timeout", "the conversion took too long and was stopped") from exc
    return proc.returncode, log.read_bytes()[-2000:].decode("utf-8", errors="replace")


# ---------- one job at a time ----------
class OfficeSlot:
    """LibreOffice profiles do not tolerate concurrent use: one conversion at a time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    @contextlib.contextmanager
    def hold(self, wait: float = 0.5) -> Iterator[None]:
        if not self._lock.acquire(timeout=wait):
            raise OfficeError("busy", "The server is busy. Try again in a moment.", retryable=True)
        try:
            yield
        finally:
            self._lock.release()


SLOT = OfficeSlot()


# ---------- convert ----------
def convert(
    data: bytes,
    ext: str,
    target: str,
    *,
    soffice: Path | None,
    work_dir: Path,
    timeout: float | None = None,
    settings: Settings | None = None,
    infilter: str | None = None,
) -> bytes:
    """Convert `data` (extension `ext`) to `target` (e.g. "pdf", "docx:MS Word 2007 XML").

    The caller holds SLOT. Raises OfficeError; never returns an empty or non-matching file.
    """
    st = settings or Settings()
    if soffice is None:
        raise OfficeError("engine_missing", "LibreOffice is not installed")
    if ext not in ALLOWED_EXT | CONVERT_ONLY_EXT:
        raise OfficeError("unsupported", "unsupported office file type")
    guard_package(
        data, ext, max_entries=st.office_max_entries,
        max_uncompressed=st.office_max_uncompressed_bytes, max_ratio=st.office_max_ratio,
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    profile = work_dir / "profile"
    if not (profile / "user" / "registrymodifications.xcu").is_file():
        prepare_profile(profile)
    job = Path(tempfile.mkdtemp(prefix="job-", dir=work_dir))
    try:
        src = job / f"input.{ext}"
        src.write_bytes(data)
        out_dir = job / "out"
        out_dir.mkdir()
        argv = [
            str(soffice), f"-env:UserInstallation={profile.resolve().as_uri()}",
            "--headless", "--norestore", "--nolockcheck", "--nologo", "--nodefault",
        ]
        if infilter:
            argv.append(f"--infilter={infilter}")
        argv += ["--convert-to", target, "--outdir", str(out_dir), str(src)]
        rc, tail = run_process(argv, cwd=job, timeout=timeout or st.office_timeout_seconds)
        want = target.split(":", 1)[0]
        outs = [p for p in out_dir.iterdir() if p.suffix.lower() == f".{want}"]
        if rc != 0 or len(outs) != 1 or outs[0].stat().st_size == 0:
            raise OfficeError("damaged", "the document could not be converted")
        return outs[0].read_bytes()
    finally:
        shutil.rmtree(job, ignore_errors=True)
