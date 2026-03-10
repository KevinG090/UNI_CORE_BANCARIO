from pydantic import BaseModel, Field


class CupoCreate(BaseModel):
    """
    Aprobar un cupo para un cliente ya existente.
    Los parámetros de interés y configuración se toman de los activos en BD.
    """
    cliente_id: str = Field(..., description="UUID del cliente")
    cupo_aprobado: float = Field(..., gt=0, description="Monto del cupo aprobado")
    perfil_riesgo: str = Field(
        ...,
        pattern="^(BAJO|MEDIO|ALTO)$",
        description="Perfil de riesgo: BAJO | MEDIO | ALTO",
    )
    created_by: str = Field(default="API", max_length=100)
