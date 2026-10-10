"""Textos de respuesta del original, copiados letra por letra. Ningún otro módulo escribe textos.

Los defectos se copian tal cual (por ejemplo, el espacio final de E301).
"""

from fastapi.responses import JSONResponse

ERRORES = {
    "E001": (401, "no autorizado"),
    "E100": (400, "json inválido"),
    "E101": (413, "cuerpo demasiado grande"),
    "E102": (400, "falta m"),
    "E103": (400, "falta control"),
    "E104": (400, "segmento vacío"),
    "E201": (400, "control mal formado"),
    "E202": (400, "control inválido"),
    "E301": (400, "comando desconocido "),
    "E404": (404, "ruta desconocida"),
}

OK = {"ok": True}
PONG = {"pong": True}


def error(codigo: str, **extra) -> JSONResponse:
    status, mensaje = ERRORES[codigo]
    return JSONResponse({"error": codigo, "mensaje": mensaje, **extra}, status_code=status)


def ok(cuerpo: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(cuerpo, status_code=status)
