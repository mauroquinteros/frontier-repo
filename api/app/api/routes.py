from fastapi import APIRouter, Depends

from app.api.dependencies import EstadoDep, SegmentosDep, verificar_token
from app.core.respuestas import OK, ok
from app.services import comandos

# El token se valida antes que el cuerpo: es la primera dependencia de cada ruta.
router = APIRouter(dependencies=[Depends(verificar_token)])


@router.get("/health")
async def health():
    return ok(OK)


@router.post("/__reset")
async def reset(estado: EstadoDep):
    estado.reiniciar()
    return ok(OK)


@router.post("/msg")
async def msg(partes: SegmentosDep, estado: EstadoDep):
    return comandos.ejecutar(partes, estado)
