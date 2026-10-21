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


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tool: str
    params: dict
    state: str
    error: str | None
    created_at: datetime
    finished_at: datetime | None
    files: list[TaskFileOut]


class ToolOut(BaseModel):
    id: str
    title: str
    group: str
    description: str
    accepts: str
    min_files: int
    max_files: int | None
    params_schema: dict
