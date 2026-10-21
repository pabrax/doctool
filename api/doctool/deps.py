from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from doctool.config import Settings
from doctool.storage import BlobStore


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_blobs(request: Request) -> BlobStore:
    return request.app.state.blobs


def get_settings(request: Request) -> Settings:
    return request.app.state.settings
