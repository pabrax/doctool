"""Base class for tools that take an office document (Word/Excel/PowerPoint/HTML) as input."""
from typing import ClassVar

from doctool import officecore
from doctool.config import Settings
from doctool.officecore import OfficeError
from doctool.tools.base import Tool, ToolError
from doctool.tools.imageutil import InputError


class OfficeTool(Tool):
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
                data, ext, max_entries=st.office_max_entries,
                max_uncompressed=st.office_max_uncompressed_bytes, max_ratio=st.office_max_ratio,
            )
        except OfficeError as exc:
            raise InputError(exc.state, exc.message) from exc

    def lo_convert(self, data: bytes, filename: str, target: str, **kw) -> bytes:
        """Convert with LibreOffice under the global one-job-at-a-time slot."""
        st = Settings.from_env()
        try:
            soffice = officecore.find_soffice()
            if soffice is None:
                raise OfficeError("engine_missing", "LibreOffice is not installed")
            ext = officecore.source_ext(filename)
            with officecore.SLOT.hold(wait=st.office_slot_wait_seconds):
                return officecore.convert(
                    data, ext, target, soffice=soffice, work_dir=st.data_dir / "office",
                    settings=st, **kw,
                )
        except OfficeError as exc:
            raise ToolError(exc.state, exc.message, retryable=exc.retryable) from exc
