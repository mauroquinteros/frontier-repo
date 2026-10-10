"""Comandos. Por ahora solo PING; el resto responde E301."""

from fastapi.responses import JSONResponse

from app.core.respuestas import PONG, ErrorServicio, ok
from app.services.estado import Estado


def ejecutar(partes: list[str], estado: Estado) -> JSONResponse:
    if partes[0] == "PING":
        return ok(PONG)
    raise ErrorServicio("E301")
