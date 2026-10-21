from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str
    seq: int
    parent_version_id: str | None
    filename: str
    sha256: str
    size: int
    pages: int | None
    encrypted: bool
    tool: str | None
    params: dict | None
    created_at: datetime


class DocumentOut(BaseModel):
    id: str
    name: str
    tags: list[str]
    created_at: datetime
    latest_version: VersionOut


class DocumentPatch(BaseModel):
    name: str | None = None
    tags: list[str] | None = None
