"""Arranque y orden de las dependencias."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import get_settings
from app.main import app


def test_no_arranca_sin_token(monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        with TestClient(app):
            pass
    get_settings.cache_clear()


def test_token_antes_que_el_cuerpo(cliente):
    # Supuesto: sin evidencia en el log de qué gana entre el token y un cuerpo inválido.
    r = cliente.post("/msg", content=b"{", headers={"Authorization": ""})
    assert (r.status_code, r.json()) == (401, {"error": "E001", "mensaje": "no autorizado"})
