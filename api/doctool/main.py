from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from doctool import __version__
from doctool.config import Settings
from doctool.db import make_session_factory
from doctool.routers import library, tasks
from doctool.storage import BlobStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        app.state.settings = settings
        app.state.blobs = BlobStore(settings.blob_dir)
        app.state.session_factory = make_session_factory(settings.db_path)
        app.state.secrets = {}
        yield

    app = FastAPI(title="doctool", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    app.include_router(library.router)
    app.include_router(tasks.router)
    return app


def app_factory() -> FastAPI:
    return create_app()
