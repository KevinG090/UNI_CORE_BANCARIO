"""
Utilidades de seguridad JWT.
- Firma HS256
- Expiración configurable via env JWT_EXPIRE_MINUTES
- No guarda estado en servidor (stateless)
"""

from datetime import datetime, timedelta, timezone
from typing import Tuple

from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core.config import get_settings

_bearer = HTTPBearer(auto_error=True)


def create_access_token(payload: dict) -> Tuple[str, int]:
    """
    Crea un JWT firmado.
    Retorna (token_string, expires_in_seconds).
    """
    settings = get_settings()
    expire_minutes = settings.JWT_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)

    to_encode = {
        **payload,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "iss": "keypago-api",
    }
    token = jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")
    return token, expire_minutes * 60


def get_current_cliente(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """
    Dependency para rutas protegidas.
    Extrae y valida el JWT del header Authorization: Bearer <token>.
    Devuelve el payload decodificado.
    """
    settings = get_settings()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalido o expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_iss": True},
            issuer="keypago-api",
        )
        cliente_id: str = payload.get("sub")
        if not cliente_id:
            raise credentials_exception
        return {"cliente_id": cliente_id, "nombre": payload.get("nombre", "")}
    except JWTError:
        raise credentials_exception
