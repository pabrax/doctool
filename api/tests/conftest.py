import shutil

import pytest
from fastapi.testclient import TestClient

from doctool.config import Settings
from doctool.db import make_session_factory
from doctool.main import create_app


@pytest.fixture(scope="session")
def db_template(tmp_path_factory):
    """Creating a SQLite file is slow on Windows; build the schema once and copy it per test."""
    path = tmp_path_factory.mktemp("template") / "doctool.sqlite3"
    make_session_factory(path).kw["bind"].dispose()
    return path


@pytest.fixture
def client(tmp_path, db_template):
    settings = Settings(data_dir=tmp_path / "data")
    settings.data_dir.mkdir()
    shutil.copy(db_template, settings.db_path)
    app = create_app(settings)
    with TestClient(app) as c:
        yield c
