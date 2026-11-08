import logging
import os
from pathlib import Path

from pydantic import BaseModel, Field

log = logging.getLogger("doctool")
LOCAL_HOSTS = {"127.0.0.1", "localhost"}


class Settings(BaseModel):
    data_dir: Path = Field(default=Path("data"))
    web_dir: Path | None = Field(default=None, description="built frontend (web/dist) to serve")
    max_upload_bytes: int = 200 * 1024 * 1024
    task_ttl_hours: int = 24
    host: str = "127.0.0.1"
    port: int = 8000
    # Host headers accepted (anti DNS-rebinding). Ports are ignored.
    # Image tools: caps against memory/CPU exhaustion (see tools/imagecore.preflight).
    image_max_pixels: int = 50_000_000  # per image (covers 48-50 MP phone photos)
    image_task_max_pixels: int = 100_000_000  # sum over the files of one task
    image_max_files: int = 10
    image_concurrency: int = 2  # image tasks decoding at the same time
    image_slot_wait_seconds: float = 0.5  # how long a request waits for a free image slot
    # Office tools (LibreOffice runs as one external process at a time; see officecore.py).
    office_timeout_seconds: float = 60.0
    office_max_entries: int = 5000  # zip entries in an OOXML/ODF package
    office_max_uncompressed_bytes: int = 500 * 1024 * 1024
    office_max_ratio: int = 200  # uncompressed/compressed size of a package
    office_slot_wait_seconds: float = 0.5
    office_max_pdf_pages: int = 300  # PDF -> Word/Excel/PowerPoint
    office_max_output_bytes: int = 500 * 1024 * 1024
    office_render_budget_pixels: int = 1_500_000_000  # pdf2ppt: all pages together
    office_warmup: bool = True  # build the LibreOffice profile in the background at start
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
        for key in ("image_max_pixels", "image_task_max_pixels", "image_max_files",
                    "image_concurrency"):
            _positive(values, env, key, int)
        _positive(values, env, "image_slot_wait_seconds", float)
        for key in ("office_max_entries", "office_max_uncompressed_bytes", "office_max_ratio",
                    "office_max_pdf_pages", "office_max_output_bytes",
                    "office_render_budget_pixels"):
            _positive(values, env, key, int)
        for key in ("office_timeout_seconds", "office_slot_wait_seconds"):
            _positive(values, env, key, float)
        if env.get("DOCTOOL_OFFICE_WARMUP") == "0":
            values["office_warmup"] = False
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


def _positive(values: dict, env, key: str, kind) -> None:
    """Read DOCTOOL_<KEY>; a missing, non-numeric or < 1 (wait: <= 0) value keeps the default."""
    name = f"DOCTOOL_{key.upper()}"
    raw = env.get(name)
    if not raw:
        return
    try:
        value = kind(raw)
        ok = value > 0 and (kind is float or value >= 1) and value == value
    except ValueError:
        ok = False
    if ok and value != float("inf"):
        values[key] = value
    else:
        log.warning("ignoring invalid %s=%r; using the default", name, raw)
