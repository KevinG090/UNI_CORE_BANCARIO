from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from core.config import get_settings
from core.email_service import enviar_otp
from core.otp import contar_solicitudes_recientes, crear_otp
from db.queries.clientes.clientes_auth import obtener_cliente_por_identificacion
from core.security import create_access_token

router = APIRouter()


class LoginRequest(BaseModel):
    tipo_identificacion: str = Field(..., pattern="^(CC|CE|NIT|TI|PP)$")
    numero_identificacion: str = Field(..., max_length=20)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int   # segundos
    cliente_id: str
    nombre: str

class RequestOtp(BaseModel):
    tipo_identificacion: str = Field(..., pattern="^(CC|CE|NIT|TI|PP)$")
    numero_identificacion: str = Field(..., max_length=20)

@router.post("/login", response_model=LoginResponse, summary="Login del cliente")
def login(data: LoginRequest):
    """
    Autentica al cliente por tipo + numero de identificacion.
    Devuelve un JWT firmado con HS256.
    No expone datos sensibles en el token.
    """
    cliente = obtener_cliente_por_identificacion(
        data.tipo_identificacion,
        data.numero_identificacion,
    )
    if not cliente:
        # Mismo mensaje para tipo incorrecto o numero incorrecto (evita enumeracion)
        raise HTTPException(status_code=401, detail="Credenciales invalidas.")

    if cliente["estado"] in ("BLOQUEADO", "INACTIVO"):
        raise HTTPException(status_code=403, detail="Cliente no habilitado.")

    payload = {
        "sub": str(cliente["id"]),
        "nombre": f"{cliente['primer_nombre']} {cliente['primer_apellido']}",
    }
    token, expires_in = create_access_token(payload)

    return LoginResponse(
        access_token=token,
        expires_in=expires_in,
        cliente_id=str(cliente["id"]),
        nombre=payload["nombre"],
    )


@router.post("/request-otp", summary="Solicitar codigo OTP por correo")
async def request_otp(data: RequestOtp):
    """
    Body cifrado esperado:
    {
      "tipo_identificacion":   "CC",
      "numero_identificacion": "52001001"
    }

    Envia un OTP de 6 digitos al correo registrado del cliente.
    Limite: 3 solicitudes por hora.
    """

    tipo   = data.tipo_identificacion
    numero = data.numero_identificacion

    # Siempre el mismo mensaje — no revelar si el cliente existe o no
    msg_generico = "Si el documento esta registrado, recibiras un codigo en tu correo."

    cliente = obtener_cliente_por_identificacion(tipo, numero)
    if not cliente:
        # Retornamos el mismo mensaje para no revelar si existe
        return {"ok": True, "message": msg_generico}

    if cliente["estado"] in ("BLOQUEADO", "INACTIVO"):
        return {"ok": True, "message": msg_generico}

    cliente_id = str(cliente["id"])

    # Rate limiting: max 3 OTPs por hora
    solicitudes = contar_solicitudes_recientes(cliente_id)
    settings    = get_settings()
    if solicitudes >= getattr(settings, 'OTP_MAX_INTENTOS', 3):
        raise HTTPException(
            429,
            "Demasiadas solicitudes. Espera un momento antes de pedir otro codigo."
        )

    # Generar OTP

    expire_min = getattr(settings, 'OTP_EXPIRE_MINUTES', 5)
    codigo     = crear_otp(cliente_id)

    # Enviar por correo
    nombre = f"{cliente['primer_nombre']} {cliente['primer_apellido']}"
    enviado = enviar_otp(
        correo     = cliente["correo_electronico"],
        nombre     = nombre,
        codigo     = codigo,
        expire_min = expire_min,
    )

    if not enviado:
        raise HTTPException(500, "Error al enviar el codigo. Intenta de nuevo.")

    # Enmascarar el correo en la respuesta: j***@gmail.com
    correo = cliente["correo_electronico"]
    partes = correo.split("@")
    correo_mascarado = partes[0][0] + "***@" + partes[1] if len(partes) == 2 else "***"

    return {
        "ok":      True,
        "message": msg_generico,
        "correo":  correo_mascarado,
        "expira_en_minutos": expire_min,
    }
