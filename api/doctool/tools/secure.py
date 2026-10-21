import pikepdf
from pydantic import BaseModel, Field

from doctool.tools.base import Tool, ToolInput, ToolOutput, open_pdf, registry, save_pdf


class ProtectParams(BaseModel):
    password: str = Field(min_length=1, json_schema_extra={"secret": True})
    owner_password: str | None = Field(
        None, json_schema_extra={"secret": True}, description="defaults to the open password"
    )
    allow_print: bool = True
    allow_copy: bool = True
    allow_modify: bool = True


class ProtectTool(Tool):
    id = "protect"
    title = "Protect PDF"
    group = "security"
    description = "Encrypt with AES-256 and an open password; optionally restrict actions."
    Params = ProtectParams

    def run(self, inputs: list[ToolInput], params: ProtectParams) -> list[ToolOutput]:
        item = inputs[0]
        perms = pikepdf.Permissions(
            print_lowres=params.allow_print,
            print_highres=params.allow_print,
            extract=params.allow_copy,
            modify_annotation=params.allow_modify,
            modify_assembly=params.allow_modify,
            modify_form=params.allow_modify,
            modify_other=params.allow_modify,
        )
        enc = pikepdf.Encryption(
            user=params.password,
            owner=params.owner_password or params.password,
            R=6,
            allow=perms,
        )
        with open_pdf(item.data, item.password) as pdf:
            return [ToolOutput(item.name, save_pdf(pdf, encryption=enc))]


class UnlockParams(BaseModel):
    pass


class UnlockTool(Tool):
    id = "unlock"
    title = "Unlock PDF"
    group = "security"
    description = "Remove the password and restrictions. Send the password with the file."
    Params = UnlockParams

    def run(self, inputs: list[ToolInput], params: UnlockParams) -> list[ToolOutput]:
        item = inputs[0]
        with open_pdf(item.data, item.password) as pdf:
            return [ToolOutput(item.name, save_pdf(pdf, encryption=False))]


registry.register(ProtectTool())
registry.register(UnlockTool())
