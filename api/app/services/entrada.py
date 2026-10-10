"""Validación de la entrada de POST /msg, en el orden del original.

    tamaño (E101) → JSON (E100) → m (E102) → sin ';' (E103) → segmento vacío (E104)
    → PING (no valida el control) → formato del control (E201) → control (E202)

Evidencia en experimentos.jsonl: 32–44, 65–74, 75–93 (tamaño), 95–111 (control y PING).
"""

import json
import re

from app.core.respuestas import ErrorServicio
from app.services import control

FORMATO_CONTROL = re.compile(r"[0-9]{1,2}")


def _sin_constantes(nombre: str):
    # json.loads acepta NaN e Infinity, que no son JSON válido.
    raise ValueError(nombre)


def leer_m(cuerpo: bytes, max_bytes: int) -> str:
    if len(cuerpo) > max_bytes:
        raise ErrorServicio("E101")
    try:
        datos = json.loads(cuerpo, parse_constant=_sin_constantes)
    except ValueError:  # incluye JSONDecodeError y UnicodeDecodeError
        raise ErrorServicio("E100")
    if not isinstance(datos, dict) or not isinstance(datos.get("m"), str):
        raise ErrorServicio("E102")
    return datos["m"]


def segmentos(m: str) -> list[str]:
    """Separa `m` por ';' y valida el control. Devuelve los segmentos sin el control.

    El primer segmento es el comando, ya en mayúsculas (log 829: `alta` funciona como `ALTA`).
    """
    if ";" not in m:
        raise ErrorServicio("E103")
    partes = m.split(";")
    if any(p == "" for p in partes):
        raise ErrorServicio("E104")
    partes[0] = partes[0].upper()
    if partes[0] == "PING":
        return partes[:-1]
    c = partes[-1]
    if not FORMATO_CONTROL.fullmatch(c):
        raise ErrorServicio("E201")
    if int(c) != control.calcular(m.rpartition(";")[0]):
        raise ErrorServicio("E202")
    return partes[:-1]
