"""Rutas, URL del servicio antiguo y lectura del token."""

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
URL_BASE = "https://caja-negra-production-c64f.up.railway.app"

LOG = RAIZ / "experimentos.jsonl"
CACHE_CONTROLES = RAIZ / "explorador" / "controles.json"

CUPO_DIARIO = 8000
# 10 req/s por token; dejamos margen.
INTERVALO_MIN = 0.12
TOKEN_INVALIDO = "token-invalido-0000"


def token() -> str:
    """Lee BEARER_TOKEN del entorno o del .env de la raíz. Nunca se imprime ni se registra."""
    if valor := os.environ.get("BEARER_TOKEN"):
        return valor
    env = RAIZ / ".env"
    if env.exists():
        for linea in env.read_text().splitlines():
            clave, _, valor = linea.partition("=")
            if clave.strip() == "BEARER_TOKEN":
                return valor.strip().strip('"').strip("'")
    raise SystemExit("Falta BEARER_TOKEN en .env")
