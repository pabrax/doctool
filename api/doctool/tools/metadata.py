from pikepdf import Name
from pydantic import BaseModel, Field

from doctool.tools.base import Tool, ToolInput, ToolOutput, open_pdf, registry, save_pdf

FIELDS = ("title", "author", "subject", "keywords", "creator", "producer")


class MetadataParams(BaseModel):
    title: str | None = Field(None, description="omit = keep, empty string = remove")
    author: str | None = None
    subject: str | None = None
    keywords: str | None = None
    creator: str | None = None
    producer: str | None = None
    clear_all: bool = Field(False, description="strip every metadata field (and XMP)")


class MetadataTool(Tool):
    id = "metadata"
    title = "Edit metadata"
    group = "edit"
    description = "Set, change or remove document properties; or strip them all."
    Params = MetadataParams

    def run(self, inputs: list[ToolInput], params: MetadataParams) -> list[ToolOutput]:
        item = inputs[0]
        with open_pdf(item.data, item.password) as pdf:
            if params.clear_all:
                for key in list(pdf.docinfo.keys()):
                    del pdf.docinfo[key]
                if Name.Metadata in pdf.Root:
                    del pdf.Root.Metadata
            else:
                for field in FIELDS:
                    value = getattr(params, field)
                    if value is None:
                        continue
                    key = "/" + field.capitalize()
                    if value == "":
                        if key in pdf.docinfo:
                            del pdf.docinfo[key]
                    else:
                        pdf.docinfo[key] = value
                if Name.Metadata in pdf.Root:  # keep XMP consistent with the info dictionary
                    with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
                        meta.load_from_docinfo(pdf.docinfo, delete_missing=True)
            return [ToolOutput(item.name, save_pdf(pdf))]


registry.register(MetadataTool())
