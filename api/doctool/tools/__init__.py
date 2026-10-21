"""Importing this package registers every built-in tool."""

# Side-effect imports: each module registers its tool.
from doctool.tools import (  # noqa: F401,I001
    merge,
    metadata,
    organize,
    pagenumber,
    rotate,
    secure,
    split,
    watermark,
)
from doctool.tools.base import Tool, ToolError, ToolInput, ToolOutput, registry

__all__ = ["Tool", "ToolError", "ToolInput", "ToolOutput", "registry"]
