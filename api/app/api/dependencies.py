"""Dependencias de las rutas. Corren después del enrutado: una ruta desconocida da E404 antes
que el token (log 49, 64)."""

from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.respuestas import ErrorServicio
from app.services import entrada
from app.services.estado import Estado, get_estado

SettingsDep = Annotated[Settings, Depends(get_settings)]
EstadoDep = Annotated[Estado, Depends(get_estado)]


async def verificar_token(request: Request, settings: SettingsDep) -> None:
    if request.headers.get("authorization") != f"Bearer {settings.api_token}":
        raise ErrorServicio("E001")


async def leer_segmentos(request: Request, settings: SettingsDep) -> list[str]:
    m = entrada.leer_m(await request.body(), settings.max_bytes)
    return entrada.segmentos(m)


SegmentosDep = Annotated[list[str], Depends(leer_segmentos)]
