"""
Gestion de OTP (One-Time Password).

- Codigo de 6 digitos generado con secrets (criptograficamente seguro)
- Guardado como hash PBKDF2-HMAC-SHA256 (nunca el codigo en texto)
- Expira en OTP_EXPIRE_MINUTES (default 5)
- Max 3 intentos por OTP antes de invalidarlo
- Rate limiting: max 3 solicitudes de OTP por hora por cliente
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from psycopg2.extras import RealDictCursor
from db.connection import get_conn
from core.config import get_settings


# ── Generar y hashear ─────────────────────────────────────────────────────────

def generar_codigo() -> str:
    """Genera un codigo OTP de 6 digitos criptograficamente seguro."""
    return str(secrets.randbelow(900000) + 100000)  # 100000-999999


def hash_codigo(codigo: str) -> str:
    """Hash PBKDF2-HMAC-SHA256 con salt aleatorio. Formato: salt$hash"""
    salt = secrets.token_hex(16)
    dk   = hashlib.pbkdf2_hmac(
        "sha256",
        codigo.encode(),
        salt.encode(),
        iterations=100_000,  # Menos iteraciones que el PIN porque expira rapido
    )
    return f"{salt}${dk.hex()}"


def verificar_codigo(codigo: str, code_hash: str) -> bool:
    """Verificacion timing-safe."""
    try:
        salt, stored = code_hash.split("$")
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            codigo.encode(),
            salt.encode(),
            iterations=100_000,
        )
        return hmac.compare_digest(dk.hex(), stored)
    except Exception:
        return False


# ── Rate limiting para solicitudes de OTP ────────────────────────────────────

def contar_solicitudes_recientes(cliente_id: str) -> int:
    """Cuantos OTPs ha solicitado en la ultima hora."""
    desde = datetime.now(timezone.utc) - timedelta(hours=1)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM banking.otp_tokens
                WHERE cliente_id = %(id)s
                  AND created_at >= %(desde)s
            """, {"id": cliente_id, "desde": desde})
            return cur.fetchone()["total"]


# ── Crear OTP ─────────────────────────────────────────────────────────────────

def crear_otp(cliente_id: str) -> str:
    """
    Invalida cualquier OTP anterior, crea uno nuevo y retorna el codigo en texto
    para enviarlo por correo. El codigo NO se guarda en texto en la BD.
    """
    settings   = get_settings()
    expire_min = getattr(settings, 'OTP_EXPIRE_MINUTES', 5)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expire_min)
    codigo     = generar_codigo()
    code_hash  = hash_codigo(codigo)

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Invalidar OTPs anteriores del cliente
            cur.execute("""
                UPDATE banking.otp_tokens
                SET used = TRUE
                WHERE cliente_id = %(id)s AND used = FALSE
            """, {"id": cliente_id})

            # Crear el nuevo OTP
            cur.execute("""
                INSERT INTO banking.otp_tokens
                    (cliente_id, code_hash, expires_at, used, intentos)
                VALUES
                    (%(id)s, %(hash)s, %(exp)s, FALSE, 0)
            """, {"id": cliente_id, "hash": code_hash, "exp": expires_at})

    return codigo  # Solo se retorna aqui para enviarlo por correo


# ── Verificar OTP ─────────────────────────────────────────────────────────────

def verificar_otp(cliente_id: str, codigo: str) -> tuple[bool, str]:
    """
    Verifica el OTP. Retorna (ok, mensaje).
    - Incrementa intentos en cada intento fallido
    - Invalida si supera max_intentos
    - Invalida si expiro
    """
    settings    = get_settings()
    max_intentos = getattr(settings, 'OTP_MAX_INTENTOS', 3)
    ahora       = datetime.now(timezone.utc)

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            cur.execute("""
                SELECT id, code_hash, expires_at, intentos
                FROM banking.otp_tokens
                WHERE cliente_id = %(id)s
                  AND used = FALSE
                ORDER BY created_at DESC
                LIMIT 1
            """, {"id": cliente_id})

            otp = cur.fetchone()

            if not otp:
                return False, "No hay un codigo activo. Solicita uno nuevo."

            # Verificar expiracion
            if otp["expires_at"].replace(tzinfo=timezone.utc) < ahora:
                cur.execute(
                    "UPDATE banking.otp_tokens SET used = TRUE WHERE id = %(id)s",
                    {"id": otp["id"]}
                )
                return False, "El codigo expiro. Solicita uno nuevo."

            # Verificar intentos
            if otp["intentos"] >= max_intentos:
                cur.execute(
                    "UPDATE banking.otp_tokens SET used = TRUE WHERE id = %(id)s",
                    {"id": otp["id"]}
                )
                return False, "Demasiados intentos. Solicita un nuevo codigo."

            # Verificar codigo
            if not verificar_codigo(codigo, otp["code_hash"]):
                nuevos_intentos = otp["intentos"] + 1
                cur.execute("""
                    UPDATE banking.otp_tokens
                    SET intentos = %(intentos)s
                    WHERE id = %(id)s
                """, {"intentos": nuevos_intentos, "id": otp["id"]})
                restantes = max_intentos - nuevos_intentos
                return False, f"Codigo incorrecto. Intentos restantes: {restantes}."

            # Todo ok — marcar como usado
            cur.execute(
                "UPDATE banking.otp_tokens SET used = TRUE WHERE id = %(id)s",
                {"id": otp["id"]}
            )
            return True, "OK"
