import os
from pathlib import Path

from pydantic import BaseModel, Field

LOCAL_HOSTS = {"127.0.0.1", "localhost"}


class Settings(BaseModel):
    data_dir: Path = Field(default=Path("data"))
    web_dir: Path | None = Field(default=None, description="built frontend (web/dist) to serve")
    max_upload_bytes: int = 200 * 1024 * 1024
    max_pages: int = 5000
    task_ttl_hours: int = 24
    host: str = "127.0.0.1"
    port: int = 8000
    # Host headers accepted (anti DNS-rebinding). Ports are ignored.
    allowed_hosts: list[str] = ["127.0.0.1", "localhost"]
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    @property
    def blob_dir(self) -> Path:
        return self.data_dir / "blobs"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "doctool.sqlite3"

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        values: dict = {}
        if v := env.get("DOCTOOL_DATA_DIR"):
            values["data_dir"] = Path(v)
        if v := env.get("DOCTOOL_PORT"):
            values["port"] = int(v)
        if v := env.get("DOCTOOL_ALLOWED_HOSTS"):
            values["allowed_hosts"] = [h.strip() for h in v.split(",") if h.strip()]
        host = env.get("DOCTOOL_HOST", "127.0.0.1")
        if host not in LOCAL_HOSTS and env.get("DOCTOOL_ALLOW_LAN") != "1":
            raise ValueError(
                f"refusing to bind {host}: doctool has no login. "
                "Set DOCTOOL_ALLOW_LAN=1 only on a network you trust."
            )
        values["host"] = host
        web = env.get("DOCTOOL_WEB_DIR")
        default_web = Path(__file__).resolve().parents[2] / "web" / "dist"
        if web:
            values["web_dir"] = Path(web)
        elif (default_web / "index.html").is_file():
            values["web_dir"] = default_web
        return cls(**values)
