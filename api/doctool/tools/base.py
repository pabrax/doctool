import io
from dataclasses import dataclass
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


class ToolError(Exception):
    """Expected, user-facing failure. `state` is one of the documented per-file states."""

    def __init__(self, state: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.state = state
        self.message = message
        self.retryable = retryable


class Tool:
    """One tool = id + Pydantic Params + run(). The registry derives API, schema and UI form."""

    id: ClassVar[str]
    title: ClassVar[str]
    group: ClassVar[str]
    description: ClassVar[str] = ""
    Params: ClassVar[type[BaseModel]]
    min_files: ClassVar[int] = 1
    max_files: ClassVar[int | None] = 1
    accepts: ClassVar[str] = "pdf"  # pdf | image

    def check_input(self, data: bytes) -> None:
        """Raise ValueError when `data` is not acceptable input for this tool."""
        from doctool.pdfio import inspect_pdf

        inspect_pdf(data)

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
