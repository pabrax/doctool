from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


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


class TaskCreate(BaseModel):
    tool: str
    params: dict = {}


class ProcessBody(BaseModel):
    passwords: dict[str, str] = {}  # task_file id -> password; transient, never persisted
    save_to_library: bool = True


class TaskFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role: str
    position: int
    version_id: str | None
    filename: str
    sha256: str | None
    state: str
    size: int | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tool: str
    params: dict
    state: str
    error: str | None
    warnings: list[dict] = []
    created_at: datetime
    finished_at: datetime | None
    files: list[TaskFileOut]

    @field_validator("warnings", mode="before")
    @classmethod
    def _no_null_warnings(cls, value):
        return value or []


class ToolOut(BaseModel):
    id: str
    title: str
    group: str
    description: str
    accepts: str
    min_files: int
    max_files: int | None
    params_schema: dict
    available: bool = True  # False when a required external engine is missing
    requires: list[str] = []
    extensions: list[str] = []
