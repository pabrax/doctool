from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    data_dir: Path = Field(default=Path("data"))
    max_upload_bytes: int = 200 * 1024 * 1024
    max_pages: int = 5000
    task_ttl_hours: int = 24
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    @property
    def blob_dir(self) -> Path:
        return self.data_dir / "blobs"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "doctool.sqlite3"
