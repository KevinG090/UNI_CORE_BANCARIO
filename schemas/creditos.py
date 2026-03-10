from pydantic import BaseModel, Field


class CreditoCreate(BaseModel):
    """Generar un crédito (desembolso) contra el cupo del cliente."""
    cupo_id: str = Field(..., description="UUID del cupo")
    valor_credito: float = Field(..., gt=0)
    numero_cuotas: int = Field(..., ge=1, le=60)
    codigo_producto: str = Field(
        default="CRE-ROT-001",
        description="Código del producto: CRE-ROT-001 | CRE-CON-001",
    )
    created_by: str = Field(default="API", max_length=100)


class CompraCreate(BaseModel):
    """
    Usar el crédito para registrar una compra.
    Es equivalente a 'utilizar el cupo' para un nuevo crédito rotativo.
    Alias semántico de CreditoCreate para claridad en el dominio.
    """
    cupo_id: str = Field(..., description="UUID del cupo")
    valor_compra: float = Field(..., gt=0, description="Valor de la compra")
    numero_cuotas: int = Field(..., ge=1, le=36)
    descripcion: str = Field(default="Compra", max_length=255)
    created_by: str = Field(default="API", max_length=100)


class PagoCreate(BaseModel):
    """Abonar al total o a una parte de un crédito."""
    credito_id: str = Field(..., description="UUID del crédito")
    valor_pago: float = Field(..., gt=0, description="Monto a abonar")
    canal_pago: str = Field(default="API", max_length=50)
    referencia_externa: str = Field(default="", max_length=100)
    usuario: str = Field(default="API", max_length=100)
