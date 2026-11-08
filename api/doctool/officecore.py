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

from doctool.config import Settings, log

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
        roots = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ]
        return [Path(r) / "LibreOffice" / "program" / "soffice.exe" for r in roots]
    return [
        Path("/usr/bin/soffice"),
        Path("/usr/lib/libreoffice/program/soffice"),
        Path("/opt/libreoffice/program/soffice"),
        Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
    ]


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
        sniff_flat(data, ext)
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
            # Per entry too: stored padding must not hide one hugely compressed part.
            ratio = info.file_size / max(1, info.compress_size)
            if info.file_size > _BIG_ENTRY and ratio > max_ratio:
                raise OfficeError("too_large", "the document expands to an unsafe size")
            name = info.filename
            if name.startswith("/") or "\\" in name or ".." in name.split("/"):
                raise OfficeError("unsafe", "the document contains an unsafe path")
            if info.flag_bits & 0x1:
                raise OfficeError("wrong_password", _PWD_MSG)
            low = name.lower()
            if (
                low.endswith("vbaproject.bin")
                or low.startswith(_ODF_SCRIPT_DIRS)
                or "/basic/" in low
            ):
                raise OfficeError("macro", _MACRO_MSG)
            if not low.endswith(_MEDIA_EXT) and _declares_entities(zf, info):
                raise OfficeError("unsafe", "the document contains XML entity declarations")
            if low.endswith((".xml", ".rels")):
                if low == "[content_types].xml":
                    if b"macroenabled" in zf.read(info).lower():
                        raise OfficeError("macro", _MACRO_MSG)
                if low.endswith(".rels") and _has_external_rel(zf.read(info)):
                    if "external_links" not in report.warnings:
                        report.warnings.append("external_links")
    return report


_BIG_ENTRY = 10 * 1024 * 1024
# Binary media is not XML: every other part (.xml, .rels, .vml, ...) is scanned for a DTD.
_MEDIA_EXT = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".emf",
    ".wmf",
    ".svm",
    ".wdp",
    ".mp4",
    ".mp3",
    ".wav",
    ".m4a",
    ".bin",
    ".ttf",
    ".odttf",
    ".otf",
    ".pdf",
)
_ODF_SCRIPT_DIRS = ("macros/", "basic/", "scripts/")
_SCAN_CHUNK = 256 * 1024
_ENTITY_MARKERS = (b"<!ENTITY", b"<!DOCTYPE")


def _declares_entities(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> bool:
    """Scan the whole XML part in chunks (constant memory) for a DTD, in UTF-8 or UTF-16."""
    markers = list(_ENTITY_MARKERS)
    markers += [m.decode().encode("utf-16-le") for m in _ENTITY_MARKERS]
    markers += [m.decode().encode("utf-16-be") for m in _ENTITY_MARKERS]
    markers += [
        m.decode().encode(enc) for m in _ENTITY_MARKERS for enc in ("utf-32-le", "utf-32-be")
    ]
    keep = max(len(m) for m in markers)
    tail = b""
    with zf.open(info) as fh:
        while chunk := fh.read(_SCAN_CHUNK):
            window = tail + chunk
            if any(m in window for m in markers):
                return True
            tail = window[-keep:]
    return False


def _has_external_rel(content: bytes) -> bool:
    """Parse the .rels (any quoting or encoding) instead of matching bytes."""
    from lxml import etree

    try:
        root = etree.fromstring(content, etree.XMLParser(resolve_entities=False, no_network=True))
    except etree.XMLSyntaxError as exc:
        raise OfficeError("damaged", "the document has a broken part") from exc
    return any(el.get("TargetMode") == "External" for el in root.iter())


# Flat formats are read by LibreOffice from their content, so a package or binary renamed to
# .txt/.rtf/.csv/.html would skip the package guards: check what the bytes really are.
_PACKAGE_OR_BINARY = (b"PK\x03\x04", _OLE_MAGIC)


def sniff_flat(data: bytes, ext: str) -> None:
    head = data[:16].lstrip(b"\xef\xbb\xbf")
    if ext == "rtf":
        if not head.startswith(b"{\\rtf"):
            raise OfficeError("damaged", "not a valid RTF document")
    elif ext in ("txt", "csv", "html", "htm"):
        if head.startswith(_PACKAGE_OR_BINARY) or head.startswith(b"{\\rtf"):
            raise OfficeError("unsupported", "the file content does not match its extension")


# Import filter per extension: LibreOffice must not pick a different format from the content.
INFILTERS = {
    "docx": "MS Word 2007 XML",
    "doc": "MS Word 97",
    "odt": "writer8",
    "rtf": "Rich Text Format",
    "txt": "Text (encoded):UTF8",
    "html": "HTML (StarWriter)",
    "htm": "HTML (StarWriter)",
    "xlsx": "Calc MS Excel 2007 XML",
    "xls": "MS Excel 97",
    "ods": "calc8",
    "pptx": "Impress MS PowerPoint 2007 XML",
    "ppt": "MS PowerPoint 97",
    "odp": "impress8",
}


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
    # No fetching of linked content. Measured on LibreOffice 26.8 with a legacy .doc that links
    # an image over http and from file:///: with neither setting LibreOffice fetched both; each
    # setting alone stopped only one; together: 0 requests, nothing embedded (RESEARCH.md).
    '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
    '<prop oor:name="BlockUntrustedRefererLinks" oor:op="fuse"><value>true</value></prop></item>\n'
    + "".join(
        f'<item oor:path="/org.openoffice.Inet/Settings"><prop oor:name="{k}" oor:op="fuse">'
        f"<value>{v}</value></prop></item>\n"
        for k, v in (
            ("ooInetProxyType", "2"),  # manual proxy ...
            ("ooInetHTTPProxyName", "127.0.0.1"),  # ... that does not exist (discard port)
            ("ooInetHTTPProxyPort", "9"),
            ("ooInetHTTPSProxyName", "127.0.0.1"),
            ("ooInetHTTPSProxyPort", "9"),
            ("ooInetNoProxy", ""),
        )
    )
    # Never recalculate formulas on load (WEBSERVICE and friends stay as saved).
    + "".join(
        f'<item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="{k}" '
        f'oor:op="fuse"><value>1</value></prop></item>\n'
        for k in ("OOXMLRecalcMode", "ODFRecalcMode")
    )
    + "</oor:items>\n"
)
# Bump when _MACRO_LOCK changes so existing profiles are re-locked.
PROFILE_VERSION = "2"


def prepare_profile(profile_dir: Path) -> None:
    """Create (or re-lock) a LibreOffice profile: macros off, no network, no recalculation."""
    user = profile_dir / "user"
    user.mkdir(parents=True, exist_ok=True)
    (user / "registrymodifications.xcu").write_text(_MACRO_LOCK, encoding="utf-8")
    (profile_dir / "doctool-profile.version").write_text(PROFILE_VERSION, encoding="utf-8")


def profile_current(profile_dir: Path) -> bool:
    marker = profile_dir / "doctool-profile.version"
    return marker.is_file() and marker.read_text(encoding="utf-8").strip() == PROFILE_VERSION


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
            argv,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
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
        data,
        ext,
        max_entries=st.office_max_entries,
        max_uncompressed=st.office_max_uncompressed_bytes,
        max_ratio=st.office_max_ratio,
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    profile = work_dir / "profile"
    if not profile_current(profile):
        prepare_profile(profile)
    infilter = infilter or INFILTERS.get(ext)
    job = Path(tempfile.mkdtemp(prefix="job-", dir=work_dir))
    try:
        src = job / f"input.{ext}"
        src.write_bytes(data)
        out_dir = job / "out"
        out_dir.mkdir()
        argv = [
            str(soffice),
            f"-env:UserInstallation={profile.resolve().as_uri()}",
            "--headless",
            "--norestore",
            "--nolockcheck",
            "--nologo",
            "--nodefault",
        ]
        if infilter:
            argv.append(f"--infilter={infilter}")
        argv += ["--convert-to", target, "--outdir", str(out_dir), str(src)]
        limit = effective_timeout(work_dir, timeout or st.office_timeout_seconds)
        rc, tail = run_process(argv, cwd=job, timeout=limit)
        want = target.split(":", 1)[0]
        outs = [p for p in out_dir.iterdir() if p.suffix.lower() == f".{want}"]
        if rc != 0 or len(outs) != 1 or outs[0].stat().st_size == 0:
            log.info("LibreOffice failed (rc=%s): %s", rc, tail[-300:])
            raise OfficeError("damaged", "the document could not be converted")
        if outs[0].stat().st_size > st.office_max_output_bytes:
            raise OfficeError("too_large", "the converted document is too large")
        (profile / READY_MARK).write_text("ok", encoding="utf-8")
        return outs[0].read_bytes()
    finally:
        shutil.rmtree(job, ignore_errors=True)


# ---------- first run ----------
# A brand-new LibreOffice profile takes much longer the first time (it is built and the font
# cache filled). Until one conversion has succeeded the timeout is raised, and the server warms
# the profile up in the background at start so the user's first conversion is not the slow one.
READY_MARK = ".ready"
FIRST_RUN_TIMEOUT = 180.0


def profile_ready(work_dir: Path) -> bool:
    return (work_dir / "profile" / READY_MARK).is_file()


def effective_timeout(work_dir: Path, timeout: float) -> float:
    return timeout if profile_ready(work_dir) else max(timeout, FIRST_RUN_TIMEOUT)


def warm_up(soffice: Path | None, work_dir: Path, settings: Settings | None = None) -> bool:
    """Build the profile with one tiny conversion. True when it ran; never raises."""
    if soffice is None or profile_ready(work_dir):
        return False
    WARMING.set()
    try:
        with SLOT.hold(wait=0.1):
            convert(
                b"warm,up\n", "csv", "pdf", soffice=soffice, work_dir=work_dir, settings=settings
            )
        return True
    except OfficeError as exc:
        log.warning("LibreOffice warm-up skipped: %s", exc.message)
        return False
    finally:
        WARMING.clear()


# Set while the start-up warm-up holds the lane: requests then wait for it instead of a 503.
WARMING = threading.Event()


def slot_wait(default: float) -> float:
    return FIRST_RUN_TIMEOUT if WARMING.is_set() else default
