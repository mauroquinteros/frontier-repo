import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app
from app.services.estado import Estado, get_estado

TOKEN = "token-de-prueba"


@pytest.fixture
def cliente():
    estado = Estado()
    app.dependency_overrides[get_settings] = lambda: Settings(api_token=TOKEN)
    app.dependency_overrides[get_estado] = lambda: estado
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {TOKEN}"
    yield c
    app.dependency_overrides.clear()
