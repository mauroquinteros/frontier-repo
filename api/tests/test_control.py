"""La copia de la fórmula da lo mismo que la del explorador y que el original."""

import json
import sys
from pathlib import Path

import pytest

from app import control

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from explorador import control as control_explorador  # noqa: E402


def mensajes_aceptados():
    """Mensajes del log que pasaron el control en el original (2xx, 404, 409 o 422)."""
    pares = json.loads((RAIZ / "explorador" / "controles.json").read_text())
    for linea in (RAIZ / "experimentos.jsonl").read_text().splitlines():
        fila = json.loads(linea)
        m = (fila.get("request") or {}).get("m") if isinstance(fila.get("request"), dict) else None
        if not isinstance(m, str) or ";" not in m or fila["status"] not in (200, 201, 404, 409, 422):
            continue
        cuerpo, _, c = m.rpartition(";")
        if c.isdigit() and not cuerpo.upper().startswith("PING"):
            pares[cuerpo] = int(c)
    return sorted(pares.items())


@pytest.mark.parametrize("mensaje,esperado", mensajes_aceptados())
def test_igual_al_original(mensaje, esperado):
    assert control.calcular(mensaje) == esperado


@pytest.mark.parametrize("mensaje,_", mensajes_aceptados())
def test_igual_al_explorador(mensaje, _):
    assert control.calcular(mensaje) == control_explorador.calcular(mensaje)


def test_mensaje_largo_no_falla():
    """Un mensaje cerca de los 8.192 bytes no supera el límite de dígitos de int()."""
    assert 2 <= control.calcular("ALTA;" + "z" * 8000) <= 98
