from typing import Literal

import pikepdf
from pydantic import BaseModel, Field, model_validator

from doctool.tools.base import Tool, ToolError, ToolInput, ToolOutput, open_pdf, registry, save_pdf
from doctool.tools.pages import parse_ranges, stem


class SplitParams(BaseModel):
    mode: Literal["ranges", "every", "extract", "remove", "size"] = "ranges"
    ranges: str = Field(
        "",
        description="e.g. 1-3,5,8-10",
        json_schema_extra={"show_when": {"mode": ["ranges", "extract", "remove"]}},
    )
    every: int = Field(
        1, ge=1, description="pages per file", json_schema_extra={"show_when": {"mode": ["every"]}}
    )
    max_kb: int = Field(
        1024,
        ge=1,
        description="max size per file in KB",
        json_schema_extra={"show_when": {"mode": ["size"]}},
    )
    merge_after: bool = Field(
        False,
        description="join all ranges into one file",
        json_schema_extra={"show_when": {"mode": ["ranges"]}},
    )

    @model_validator(mode="after")
    def _needs_ranges(self):
        if self.mode in ("ranges", "extract", "remove") and not self.ranges.strip():
            raise ValueError("ranges is required for this mode")
        return self


def _subset(src: pikepdf.Pdf, indexes: list[int]) -> bytes:
    with pikepdf.new() as dst:
        dst.pages.extend([src.pages[i] for i in indexes])
        return save_pdf(dst)


class SplitTool(Tool):
    id = "split"
    title = "Split PDF"
    group = "organize"
    description = "Split by ranges, every N pages or size; extract or remove pages."
    Params = SplitParams

    def run(self, inputs: list[ToolInput], params: SplitParams) -> list[ToolOutput]:
        item = inputs[0]
        base = stem(item.name)
        with open_pdf(item.data, item.password) as src:
            total = len(src.pages)
            if params.mode == "ranges":
                groups = parse_ranges(params.ranges, total)
                if params.merge_after:
                    flat = [i for g in groups for i in g]
                    return [ToolOutput(f"{base}_split.pdf", _subset(src, flat))]
                return [
                    ToolOutput(f"{base}_part{n}.pdf", _subset(src, g))
                    for n, g in enumerate(groups, 1)
                ]
            if params.mode == "extract":
                flat = [i for g in parse_ranges(params.ranges, total) for i in g]
                return [ToolOutput(f"{base}_extract.pdf", _subset(src, flat))]
            if params.mode == "remove":
                drop = {i for g in parse_ranges(params.ranges, total) for i in g}
                keep = [i for i in range(total) if i not in drop]
                if not keep:
                    raise ToolError("out_of_range", "cannot remove every page")
                return [ToolOutput(f"{base}_removed.pdf", _subset(src, keep))]
            if params.mode == "every":
                step = params.every
                chunks = [list(range(s, min(s + step, total))) for s in range(0, total, step)]
            else:
                chunks = self._by_size(src, total, params.max_kb * 1024)
            return [
                ToolOutput(f"{base}_part{n}.pdf", _subset(src, c)) for n, c in enumerate(chunks, 1)
            ]

    @staticmethod
    def _by_size(src: pikepdf.Pdf, total: int, limit: int) -> list[list[int]]:
        """Greedy: grow a chunk page by page, close it before it exceeds `limit` bytes."""
        chunks: list[list[int]] = []
        current: list[int] = []
        for i in range(total):
            candidate = [*current, i]
            if current and len(_subset(src, candidate)) > limit:
                chunks.append(current)
                current = [i]
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks


registry.register(SplitTool())
