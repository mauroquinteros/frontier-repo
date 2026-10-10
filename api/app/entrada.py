"""Validación de la entrada de POST /msg, en el orden del original.

    tamaño (E101) → JSON (E100) → m (E102) → sin ';' (E103) → segmento vacío (E104)
    → PING (no valida el control) → formato del control (E201) → control (E202)

Evidencia en experimentos.jsonl: 32–44, 65–74, 75–93 (tamaño), 95–111 (control y PING).
"""

import json
import re

from . import control

MAX_BYTES = 8192
FORMATO_CONTROL = re.compile(r"[0-9]{1,2}")


class ErrorEntrada(Exception):
    def __init__(self, codigo: str):
        self.codigo = codigo


def _sin_constantes(nombre: str):
    # json.loads acepta NaN e Infinity, que no son JSON válido.
    raise ValueError(nombre)


def leer_m(cuerpo: bytes) -> str:
    if len(cuerpo) > MAX_BYTES:
        raise ErrorEntrada("E101")
    try:
        datos = json.loads(cuerpo, parse_constant=_sin_constantes)
    except ValueError:  # incluye JSONDecodeError y UnicodeDecodeError
        raise ErrorEntrada("E100")
    if not isinstance(datos, dict) or not isinstance(datos.get("m"), str):
        raise ErrorEntrada("E102")
    return datos["m"]


def segmentos(m: str) -> list[str]:
    """Separa `m` por ';' y valida el control. Devuelve los segmentos sin el control.

    El primer segmento es el comando, ya en mayúsculas (log 829: `alta` funciona como `ALTA`).
    """
    if ";" not in m:
        raise ErrorEntrada("E103")
    partes = m.split(";")
    if any(p == "" for p in partes):
        raise ErrorEntrada("E104")
    partes[0] = partes[0].upper()
    if partes[0] == "PING":
        return partes[:-1]
    c = partes[-1]
    if not FORMATO_CONTROL.fullmatch(c):
        raise ErrorEntrada("E201")
    if int(c) != control.calcular(m.rpartition(";")[0]):
        raise ErrorEntrada("E202")
    return partes[:-1]
