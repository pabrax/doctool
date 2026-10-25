import mimetypes
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from doctool import __version__
from doctool.config import Settings
from doctool.db import make_session_factory
from doctool.library import purge_expired_tasks
from doctool.routers import library, tasks
from doctool.storage import BlobStore

CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self'",
        "connect-src 'self'",
        "frame-src 'self'",
        "object-src 'self'",  # our own PDF previews
        "frame-ancestors 'self'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
)
# The Windows registry has no woff2 entry, so StaticFiles would send octet-stream.
mimetypes.add_type("font/woff2", ".woff2")
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class ImmutableStatic(StaticFiles):
    """Vite emits content-hashed asset names, so they can be cached forever."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    allowed_hostnames = {h.split(":")[0] for h in settings.allowed_hosts}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        app.state.settings = settings
        app.state.blobs = BlobStore(settings.blob_dir)
        app.state.session_factory = make_session_factory(settings.db_path)
        app.state.secrets = {}
        with app.state.session_factory() as db:
            purge_expired_tasks(db, app.state.blobs, settings.task_ttl_hours)
        yield

    app = FastAPI(title="doctool", version=__version__, lifespan=lifespan)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.method in WRITE_METHODS:
            origin = request.headers.get("origin")
            # Browsers always send Origin on cross-site writes; scripts/curl send none.
            if origin and urlsplit(origin).hostname not in allowed_hostnames:
                return JSONResponse({"detail": "cross-origin request blocked"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        if not request.url.path.startswith("/api/"):
            response.headers["Content-Security-Policy"] = CSP
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    app.include_router(library.router)
    app.include_router(tasks.router)
    _mount_web(app, settings)
    return app


def _mount_web(app: FastAPI, settings: Settings) -> None:
    if not settings.web_dir or not (settings.web_dir / "index.html").is_file():
        return
    root = settings.web_dir.resolve()
    if (root / "assets").is_dir():
        app.mount("/assets", ImmutableStatic(directory=root / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(404, "not found")
        candidate = (root / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        if "." in full_path.rsplit("/", 1)[-1]:  # looks like a file that does not exist
            raise HTTPException(404, "not found")
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})


def app_factory() -> FastAPI:
    return create_app(Settings.from_env())
