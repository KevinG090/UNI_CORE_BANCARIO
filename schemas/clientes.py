from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class ClienteCreate(BaseModel):
    tipo_identificacion: str = Field(..., pattern="^(CC|CE|NIT|TI|PP)$")
    numero_identificacion: str = Field(..., max_length=20)
    primer_nombre: str = Field(..., max_length=80)
    segundo_nombre: Optional[str] = Field(None, max_length=80)
    primer_apellido: str = Field(..., max_length=80)
    segundo_apellido: Optional[str] = Field(None, max_length=80)
    fecha_nacimiento: date
    correo_electronico: EmailStr
    telefono_movil: str = Field(..., max_length=15)
    telefono_fijo: Optional[str] = Field(None, max_length=15)
    direccion: str = Field(..., max_length=255)
    ciudad: str = Field(..., max_length=100)
    departamento: str = Field(..., max_length=100)
    codigo_postal: Optional[str] = Field(None, max_length=10)
    score_credito: Optional[int] = Field(None, ge=0, le=1000)
    created_by: str = Field(default="API", max_length=100)


class ClienteUpdate(BaseModel):
    primer_nombre: Optional[str] = Field(None, max_length=80)
    segundo_nombre: Optional[str] = Field(None, max_length=80)
    primer_apellido: Optional[str] = Field(None, max_length=80)
    segundo_apellido: Optional[str] = Field(None, max_length=80)
    correo_electronico: Optional[EmailStr] = None
    telefono_movil: Optional[str] = Field(None, max_length=15)
    telefono_fijo: Optional[str] = Field(None, max_length=15)
    direccion: Optional[str] = Field(None, max_length=255)
    ciudad: Optional[str] = Field(None, max_length=100)
    departamento: Optional[str] = Field(None, max_length=100)
    codigo_postal: Optional[str] = Field(None, max_length=10)
    score_credito: Optional[int] = Field(None, ge=0, le=1000)
    estado: Optional[str] = Field(None, pattern="^(EN_ESTUDIO|ACTIVO|BLOQUEADO|INACTIVO)$")
    updated_by: str = Field(default="API", max_length=100)
