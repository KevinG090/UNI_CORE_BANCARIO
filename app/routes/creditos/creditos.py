from fastapi import APIRouter, HTTPException

from db.queries.creditos.creditos import (
    crear_credito_desde_compra,
    listar_creditos_por_cupo,
    obtener_credito,
    obtener_cuotas,
    registrar_pago,
)
from schemas.creditos import CompraCreate, PagoCreate

router = APIRouter()


@router.post("/compra", status_code=201, summary="Registrar compra (genera crédito rotativo)")
async def post_compra(data: CompraCreate):
    """
    Usa el cupo disponible del cliente para financiar una compra.
    Genera el crédito y el plan de cuotas automáticamente.
    """
    try:
        return crear_credito_desde_compra(data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{credito_id}", summary="Obtener crédito por ID")
async def get_credito(credito_id: str):
    credito = obtener_credito(credito_id)
    if not credito:
        raise HTTPException(404, "Crédito no encontrado.")
    return credito


@router.get("/{credito_id}/cuotas", summary="Plan de cuotas del crédito")
async def get_cuotas(credito_id: str):
    return obtener_cuotas(credito_id)


@router.get("/cupo/{cupo_id}", summary="Créditos de un cupo")
async def get_creditos_cupo(cupo_id: str):
    return listar_creditos_por_cupo(cupo_id)


@router.post("/pago", status_code=201, summary="Registrar pago (parcial o total)")
async def post_pago(data: PagoCreate):
    """
    Abona al crédito. Puede ser pago parcial o total.
    El sistema aplica el abono a cuotas en orden (más antigua primero),
    distribuyendo: mora → interés → capital.
    """
    try:
        return registrar_pago(data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))
