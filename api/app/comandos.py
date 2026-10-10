"""Comandos y estado en memoria. Por ahora solo PING; el resto responde E301."""

from .respuestas import PONG, error, ok


def reiniciar() -> None:
    pass


def ejecutar(partes: list[str]):
    if partes[0] == "PING":
        return ok(PONG)
    return error("E301")
