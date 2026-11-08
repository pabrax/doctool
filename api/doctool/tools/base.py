import io
from dataclasses import dataclass, field
from typing import Any, ClassVar

import pikepdf
from pydantic import BaseModel

SECRET_MASK = "***"


@dataclass
class ToolInput:
    name: str
    data: bytes
    password: str | None = None


@dataclass
class ToolOutput:
    name: str
    data: bytes
    # Non-fatal notes for the user: {"code": str, "params"?: dict, "file"?: str, "action"?: {...}}
    warnings: list[dict] = field(default_factory=list)


class ToolError(Exception):
    """Expected, user-facing failure. `state` is one of the documented per-file states."""

    def __init__(
        self, state: str, message: str, retryable: bool = False, *, file: str | None = None
    ):
        super().__init__(message)
        self.state = state
        self.message = message
        self.retryable = retryable
        self.file = file  # name of the input file that caused the error, when known


class Tool:
    """One tool = id + Pydantic Params + run(). The registry derives API, schema and UI form."""

    id: ClassVar[str]
    title: ClassVar[str]
    group: ClassVar[str]
    description: ClassVar[str] = ""
    Params: ClassVar[type[BaseModel]]
    min_files: ClassVar[int] = 1
    max_files: ClassVar[int | None] = 1
    accepts: ClassVar[str] = "pdf"  # pdf | image | pdf+image | office
    requires: ClassVar[tuple[str, ...]] = ()  # external engines, see engines.py
    extensions: ClassVar[tuple[str, ...]] = ()  # accepted file extensions (office tools)

    def check_input(self, data: bytes) -> None:
        """Raise ValueError when `data` is not acceptable input for this tool."""
        from doctool.pdfio import inspect_pdf

        inspect_pdf(data)

    def check_upload(self, filename: str, data: bytes) -> None:
        """Validate an uploaded file; defaults to check_input (the name matters for office)."""
        self.check_input(data)

    def available(self) -> bool:
        from doctool.engines import engine_available

        return all(engine_available(name) for name in self.requires)

    def params_schema(self) -> dict:
        """JSON schema of Params for the UI form; a tool may hide options it cannot run now."""
        return self.Params.model_json_schema()

    def run(self, inputs: list[ToolInput], params: Any) -> list[ToolOutput]:
        raise NotImplementedError


class Registry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        self._tools[tool.id] = tool
        return tool

    def unregister(self, tool_id: str) -> None:
        self._tools.pop(tool_id, None)

    def get(self, tool_id: str) -> Tool | None:
        return self._tools.get(tool_id)

    def all(self) -> list[Tool]:
        return list(self._tools.values())


registry = Registry()


def secret_fields(params_cls: type[BaseModel]) -> set[str]:
    return {
        name
        for name, f in params_cls.model_fields.items()
        if isinstance(f.json_schema_extra, dict) and f.json_schema_extra.get("secret")
    }


def redact(params: BaseModel) -> dict:
    data = params.model_dump(mode="json")
    for name in secret_fields(type(params)):
        if data.get(name) is not None:
            data[name] = SECRET_MASK
    return data


def open_pdf(data: bytes, password: str | None = None) -> pikepdf.Pdf:
    try:
        return pikepdf.open(io.BytesIO(data), password=password or "")
    except pikepdf.PasswordError as exc:
        raise ToolError("wrong_password", "password required or incorrect", retryable=True) from exc
    except (pikepdf.PdfError, ValueError) as exc:
        raise ToolError("damaged", f"damaged PDF: {exc}") from exc


def save_pdf(pdf: pikepdf.Pdf, **kwargs: Any) -> bytes:
    buf = io.BytesIO()
    pdf.save(buf, **kwargs)
    return buf.getvalue()
