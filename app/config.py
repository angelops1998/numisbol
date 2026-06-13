from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    https_only: bool = False

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    try:
        settings = Settings()
    except Exception:
        raise SystemExit(
            "\n[ERROR] No se pudo cargar la configuración.\n"
            "Asegurate de que existe el archivo .env con DATABASE_URL y SECRET_KEY.\n"
        )
    if not settings.secret_key:
        raise SystemExit(
            "\n[ERROR] SECRET_KEY está vacío en el .env.\n"
            "Generá una clave con: python -c \"import secrets; print(secrets.token_hex(64))\"\n"
        )
    return settings
