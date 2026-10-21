"""Importing this package registers every built-in tool."""

# Side-effect imports: each module registers its tool.
from doctool.tools import merge, organize, rotate, split  # noqa: E402,F401,I001
from doctool.tools.base import Tool, ToolError, ToolInput, ToolOutput, registry

__all__ = ["Tool", "ToolError", "ToolInput", "ToolOutput", "registry"]
