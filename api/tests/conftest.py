import os

import pytest

os.environ.setdefault("API_TOKEN", "token-de-prueba")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

TOKEN = os.environ["API_TOKEN"]


@pytest.fixture
def cliente():
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {TOKEN}"
    c.post("/__reset")
    return c
