import pytest
from fastapi.testclient import TestClient

from doctool.config import Settings
from doctool.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "data"))
    with TestClient(app) as c:
        yield c
