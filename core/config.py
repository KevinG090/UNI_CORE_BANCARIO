from functools import lru_cache
from typing import List, Union

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html
from fastapi.responses import HTMLResponse
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Captura variables de entorno"""

    PROJECT_NAME: str = "Banking Core API"
    BACKEND_CORS_ORIGINS: List[Union[AnyHttpUrl, str]] = ["*"]

    # PostgreSQL — una sola conexión (simplificado vs proyecto referencia)
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    # Pool (psycopg2 no tiene pool nativo, se usa SimpleConnectionPool)
    POOL_MIN_CONN: int = 1
    POOL_MAX_CONN: int = 10
    
    URL_API_REDOC: str = "https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js"
    # JWT — NUNCA hardcodear, siempre desde env
    JWT_SECRET: str                        # openssl rand -hex 32
    JWT_EXPIRE_MINUTES: int = 30           # Expiracion del token en minutos



    OTP_EXPIRE_MINUTES: int = 5   # Cuanto dura el codigo
    OTP_MAX_INTENTOS:   int = 3   # Intentos antes de invalidar
    OTP_MAX_POR_HORA:   int = 3   # Solicitudes de OTP por hora

    # Resend — obtener en https://resend.com/api-keys
    RESEND_API_KEY: str

    # RSA
    REQ_PRIVATE_KEY:  str
    REQ_PUBLIC_KEY:   str
    RESP_PUBLIC_KEY:  str
    RESP_PRIVATE_KEY: str
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()  # type: ignore


def get_application() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title=settings.PROJECT_NAME,
        description="API para el Core Bancario — gestión de clientes, cupos y créditos.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url=None,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    

    return application



app = get_application()