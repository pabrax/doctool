"""Importing this package registers every built-in tool."""

from doctool.tools.base import Tool, ToolError, ToolInput, ToolOutput, registry

__all__ = ["Tool", "ToolError", "ToolInput", "ToolOutput", "registry"]
