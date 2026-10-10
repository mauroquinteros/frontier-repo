import os

from fastapi import FastAPI, Request
from starlette.exceptions import HTTPException

from . import comandos, entrada
from .respuestas import OK, error, ok

TOKEN = os.environ["API_TOKEN"]

# Sin /docs, /redoc ni /openapi.json: en el original esas rutas dan 404 E404.
# Sin redirect_slashes: FastAPI respondería 307 a /health/ en vez de 404.
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False)


@app.exception_handler(HTTPException)
async def ruta_desconocida(request: Request, exc: HTTPException):
    # Ruta o método desconocido: 404 E404 aun sin token (log 46–49, 62–64).
    return error("E404")


def autorizado(request: Request) -> bool:
    return request.headers.get("authorization") == f"Bearer {TOKEN}"


@app.get("/health")
async def health(request: Request):
    if not autorizado(request):
        return error("E001")
    return ok(OK)


@app.post("/__reset")
async def reset(request: Request):
    if not autorizado(request):
        return error("E001")
    comandos.reiniciar()
    return ok(OK)


@app.post("/msg")
async def msg(request: Request):
    if not autorizado(request):
        return error("E001")
    try:
        m = entrada.leer_m(await request.body())
        partes = entrada.segmentos(m)
    except entrada.ErrorEntrada as e:
        return error(e.codigo)
    return comandos.ejecutar(partes)
