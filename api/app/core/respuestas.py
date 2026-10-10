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
    "E302": (400, "aridad inválida"),
    "E303": (400, "monto inválido"),
    "E304": (400, "origen y destino iguales"),
    "E401": (404, "cuenta inexistente"),
    "E402": (404, "operación inexistente"),
    "E404": (404, "ruta desconocida"),
    "E506": (422, "límite excedido"),
    "E507": (422, "saldo insuficiente"),
    "E510": (423, "cuenta bloqueada"),  # 409 antes de las 15:30 (log 634 → 1075)
    "E520": (409, "operación destructiva: detiene el servicio; reenvía con confirmación"),
}

OK = {"ok": True}
PONG = {"pong": True}
# "recieved" con el error de ortografía del original.
RECIBIDA = "recieved"
YA_ANULADA = {"ok": False, "motivo": "ya anulada"}


class ErrorServicio(Exception):
    """Cualquier error del protocolo. El manejador de main.py lo convierte en respuesta."""

    def __init__(self, codigo: str, **extra):
        self.codigo = codigo
        self.extra = extra


def error(codigo: str, **extra) -> JSONResponse:
    status, mensaje = ERRORES[codigo]
    return JSONResponse({"error": codigo, "mensaje": mensaje, **extra}, status_code=status)


def ok(cuerpo: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(cuerpo, status_code=status)
