import os
import shutil

import pytest
from fastapi.testclient import TestClient

from doctool.config import Settings
from doctool.db import make_session_factory
from doctool.main import create_app


@pytest.fixture(scope="session", autouse=True)
def isolated_data_dir(tmp_path_factory):
    """Tools read Settings.from_env() (LibreOffice work dir, limits): point it at a per-session
    temp dir so parallel test runs never share one LibreOffice profile or the repo's data/."""
    previous = os.environ.get("DOCTOOL_DATA_DIR")
    os.environ["DOCTOOL_DATA_DIR"] = str(tmp_path_factory.mktemp("doctool-data"))
    yield
    if previous is None:
        os.environ.pop("DOCTOOL_DATA_DIR", None)
    else:
        os.environ["DOCTOOL_DATA_DIR"] = previous


@pytest.fixture(scope="session")
def db_template(tmp_path_factory):
    """Creating a SQLite file is slow on Windows; build the schema once and copy it per test."""
    path = tmp_path_factory.mktemp("template") / "doctool.sqlite3"
    make_session_factory(path).kw["bind"].dispose()
    return path


@pytest.fixture
def client(tmp_path, db_template):
    settings = Settings(
        data_dir=tmp_path / "data", allowed_hosts=["testserver", "localhost"], office_warmup=False
    )
    settings.data_dir.mkdir()
    shutil.copy(db_template, settings.db_path)
    app = create_app(settings)
    with TestClient(app) as c:
        yield c
