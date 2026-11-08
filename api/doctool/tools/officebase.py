"""Base class and shared steps for tools that take an office document (Word/Excel/PPT/HTML)."""

import contextlib
import json
import posixpath
from collections.abc import Callable, Iterator
from typing import ClassVar

from doctool import officecore, ooxml, pdflayout
from doctool.config import Settings
from doctool.officecore import OfficeError
from doctool.tools.base import Tool, ToolError
from doctool.tools.imageutil import InputError

Converter = Callable[..., bytes]
_MAX_FONTS_LISTED = 5


def pdf_filter(name: str, **options: bool | str | int) -> str:
    """`--convert-to` target with PDF export options, e.g. pdf_filter("impress_pdf_Export",
    ExportHiddenSlides=True) (JSON filter options, LibreOffice >= 7.4)."""
    if not options:
        return "pdf"
    spec = {}
    for key, value in options.items():
        kind = (
            "boolean" if isinstance(value, bool) else "long" if isinstance(value, int) else "string"
        )
        spec[key] = {
            "type": kind,
            "value": str(value).lower() if isinstance(value, bool) else str(value),
        }
    return f"pdf:{name}:{json.dumps(spec, separators=(',', ':'))}"


def output_name(filename: str, ext: str) -> str:
    stem = posixpath.splitext(posixpath.basename(filename.replace("\\", "/")))[0] or "document"
    return f"{stem}.{ext}"


def count_warning(code: str, count: int) -> list[dict]:
    return [{"code": code, "params": {"count": count}}] if count else []


def font_warning(original: bytes, ext: str, pdf: bytes) -> list[dict]:
    if ext not in ooxml.OOXML_EXT:
        return []
    missing = pdflayout.substituted_fonts(
        ooxml.document_fonts(original, ext), pdflayout.pdf_fonts(pdf)
    )
    if not missing:
        return []
    return [
        {"code": "font_substituted", "params": {"fonts": ", ".join(missing[:_MAX_FONTS_LISTED])}}
    ]


def prepare_package(data: bytes, ext: str) -> tuple[bytes, list[dict]]:
    """Neutralise fetchable external references (OOXML) and note legacy macros (never run)."""
    warnings: list[dict] = []
    if ext in ooxml.OOXML_EXT:
        data, blocked = ooxml.neutralize_external(data)
        warnings += count_warning("external_links_blocked", blocked)
    elif ext in ("doc", "xls", "ppt") and ooxml.ole_has_macros(data):
        warnings.append({"code": "macros_removed"})
    return data, warnings


class LibreOfficeMixin:
    """Gives a tool `lo_session()`: the single LibreOffice lane, held for the whole task."""

    @contextlib.contextmanager
    def lo_session(self) -> Iterator[Converter]:
        """Hold the single LibreOffice lane for the whole task (multi-step conversions included)
        and yield `convert(data, ext, target, **kw) -> bytes`. OfficeError becomes ToolError."""
        st = Settings.from_env()
        try:
            soffice = officecore.find_soffice()
            if soffice is None:
                raise OfficeError("engine_missing", "LibreOffice is not installed")
            with officecore.SLOT.hold(wait=officecore.slot_wait(st.office_slot_wait_seconds)):

                def convert(data: bytes, ext: str, target: str, **kw) -> bytes:
                    return officecore.convert(
                        data,
                        ext,
                        target,
                        soffice=soffice,
                        work_dir=st.data_dir / "office",
                        settings=st,
                        **kw,
                    )

                yield convert
        except OfficeError as exc:
            raise ToolError(exc.state, exc.message, retryable=exc.retryable) from exc


class OfficeTool(LibreOfficeMixin, Tool):
    """A tool whose input is an office document (validated by extension and package guards)."""

    accepts = "office"
    requires: ClassVar[tuple[str, ...]] = ("libreoffice",)
    extensions: ClassVar[tuple[str, ...]] = ()  # lower-case, no dot

    def check_input(self, data: bytes) -> None:
        """Office inputs are validated by check_upload (they need the file name)."""

    def check_upload(self, filename: str, data: bytes) -> None:
        st = Settings.from_env()
        try:
            ext = officecore.source_ext(filename)
            if ext not in self.extensions:
                raise OfficeError("unsupported", "this tool does not accept that file type")
            officecore.guard_package(
                data,
                ext,
                max_entries=st.office_max_entries,
                max_uncompressed=st.office_max_uncompressed_bytes,
                max_ratio=st.office_max_ratio,
            )
        except OfficeError as exc:
            raise InputError(exc.state, exc.message) from exc

    def source_ext(self, filename: str) -> str:
        try:
            return officecore.source_ext(filename)
        except OfficeError as exc:
            raise ToolError(exc.state, exc.message) from exc

    def lo_convert(self, data: bytes, filename: str, target: str, **kw) -> bytes:
        """One-step conversion under the LibreOffice lane."""
        ext = self.source_ext(filename)
        with self.lo_session() as convert:
            return convert(data, ext, target, **kw)
