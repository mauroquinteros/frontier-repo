"""Reproduce contra el reemplazo las secuencias del log corridas con la versión vigente.

Toma de experimentos.jsonl cada secuencia que empezó después del cambio de las 15:30, manda sus
pasos en orden y compara status y cuerpo como el evaluador (JSON: claves en cualquier orden).
Solo usa resets y `POST /msg` con token válido y cuerpo JSON normal; los casos de entrada (rutas,
token, cuerpo crudo) tienen sus propios tests.
"""

import json
import re
from collections import defaultdict
from pathlib import Path

import pytest

LOG = Path(__file__).resolve().parents[2] / "experimentos.jsonl"
CAMBIO = "2026-10-10T15:30:00"
ANOTACION = re.compile(r"\((?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) [^()]*\)$|sin token|token inválido|cuerpo crudo|Content-Type")
RESET = re.compile(r"\(POST /__reset\)$")
RATE_LIMIT = "Límite de infraestructura"


def _secuencias() -> dict[str, list[dict]]:
    if not LOG.exists():
        return {}
    por_seq: dict[str, list[dict]] = defaultdict(list)
    with LOG.open(encoding="utf-8") as f:
        for linea in f:
            if linea.strip():
                d = json.loads(linea)
                por_seq[d["seq"]].append(d)
    return {seq: lineas for seq, lineas in por_seq.items() if lineas[0]["ts"] >= CAMBIO}


def _es_reset(linea: dict) -> bool:
    return bool(RESET.search(linea.get("hipotesis") or ""))


def _es_msg(linea: dict) -> bool:
    request = linea.get("request")
    return (
        isinstance(request, dict)
        and isinstance(request.get("m"), str)
        and not ANOTACION.search(linea.get("hipotesis") or "")
    )


SECUENCIAS = _secuencias()


@pytest.mark.skipif(not SECUENCIAS, reason="no hay secuencias posteriores al cambio en el log")
@pytest.mark.parametrize("seq", sorted(SECUENCIAS, key=lambda s: SECUENCIAS[s][0]["id"]))
def test_secuencia_del_log(cliente, seq):
    distintas = []
    for linea in SECUENCIAS[seq]:
        if (linea.get("conclusion") or "").startswith(RATE_LIMIT):
            continue
        if _es_reset(linea):
            r = cliente.post("/__reset")
        elif _es_msg(linea):
            # Igual que el registrador: el tamaño del cuerpo cuenta (E101).
            contenido = json.dumps(linea["request"], ensure_ascii=False).encode()
            r = cliente.post("/msg", content=contenido, headers={"Content-Type": "application/json"})
        else:
            continue
        if (r.status_code, r.json()) != (linea["status"], linea["response"]):
            distintas.append(
                f"#{linea['id']} {linea['request']}: original {linea['status']} {linea['response']} · "
                f"reemplazo {r.status_code} {r.json()}"
            )
    assert not distintas, "\n".join(distintas)
