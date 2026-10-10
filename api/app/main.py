from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.exceptions import HTTPException

from app.api.routes import router
from app.core.config import get_settings
from app.core.respuestas import ErrorServicio, error


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sin API_TOKEN el proceso no arranca, en vez de responder 401 a todo.
    get_settings()
    yield


async def manejar_error_servicio(request: Request, exc: ErrorServicio):
    return error(exc.codigo, **exc.extra)


async def manejar_ruta_desconocida(request: Request, exc: HTTPException):
    # Ruta o método desconocido: 404 E404 aun sin token (log 46–49, 62–64).
    return error("E404")


def create_app() -> FastAPI:
    # Sin /docs, /redoc ni /openapi.json: en el original esas rutas dan 404 E404.
    # Sin redirect_slashes: FastAPI respondería 307 a /health/ en vez de 404.
    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
        lifespan=lifespan,
    )
    app.add_exception_handler(ErrorServicio, manejar_error_servicio)
    app.add_exception_handler(HTTPException, manejar_ruta_desconocida)
    app.include_router(router)
    return app


app = create_app()
