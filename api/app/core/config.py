from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración desde variables de entorno. Sin env_file: el .env de la raíz es del explorador."""

    api_token: str
    max_bytes: int = 8192  # log 84–93


@lru_cache
def get_settings() -> Settings:
    return Settings()
