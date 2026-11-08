"""Importing this package registers every built-in tool."""

# Side-effect imports: each module registers its tool.
from doctool.tools import (  # noqa: F401,I001
    compress,
    excel2pdf,
    html2pdf,
    imageclean,
    imagecompress,
    imageconvert,
    imagecrop,
    imagepdf,
    imageresize,
    merge,
    metadata,
    organize,
    pagenumber,
    pdf2excel,
    pdf2ppt,
    pdf2word,
    pdfimage,
    ppt2pdf,
    rotate,
    secure,
    split,
    watermark,
    word2pdf,
)
from doctool.tools.base import Tool, ToolError, ToolInput, ToolOutput, registry

__all__ = ["Tool", "ToolError", "ToolInput", "ToolOutput", "registry"]
