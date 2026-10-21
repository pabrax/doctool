from contextlib import ExitStack

import pikepdf
from pydantic import BaseModel

from doctool.tools.base import Tool, ToolInput, ToolOutput, open_pdf, registry, save_pdf


class MergeParams(BaseModel):
    pass


class MergeTool(Tool):
    id = "merge"
    title = "Merge PDF"
    group = "organize"
    description = "Combine several PDFs into one, in the order they were added."
    Params = MergeParams
    min_files = 2
    max_files = None

    def run(self, inputs: list[ToolInput], params: MergeParams) -> list[ToolOutput]:
        with ExitStack() as stack, pikepdf.new() as dst:
            for item in inputs:
                src = stack.enter_context(open_pdf(item.data, item.password))
                dst.pages.extend(src.pages)
            return [ToolOutput("merged.pdf", save_pdf(dst))]


registry.register(MergeTool())
