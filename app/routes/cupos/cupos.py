from fastapi import APIRouter, HTTPException

from db.queries.cupos.cupos import crear_cupo, obtener_cupo, obtener_cupo_por_cliente
from db.queries.cupos.movimientos import (
    contar_movimientos_cupo,
    obtener_movimientos_cupo,
)
from schemas.cupos import CupoCreate

router = APIRouter()


@router.post("/", status_code=201, summary="Aprobar cupo para un cliente")
async def post_cupo(data: CupoCreate):
    try:
        return crear_cupo(data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{cupo_id}", summary="Obtener cupo por ID")
async def get_cupo(cupo_id: str):
    cupo = obtener_cupo(cupo_id)
    if not cupo:
        raise HTTPException(404, "Cupo no encontrado.")
    return cupo


@router.get("/cliente/{cliente_id}", summary="Cupo activo del cliente")
async def get_cupo_cliente(cliente_id: str):
    cupo = obtener_cupo_por_cliente(cliente_id)
    if not cupo:
        raise HTTPException(404, "Este cliente no tiene cupo activo.")
    return cupo


@router.get("/{cupo_id}/movimientos", summary="Movimientos del cupo")
async def get_movimientos_cupo(
    cupo_id: str,
    limite: int = 50,
    offset: int = 0,
):
    try:
        total = contar_movimientos_cupo(cupo_id)
        items = obtener_movimientos_cupo(cupo_id, limite, offset)
        return {
            "total":  total,
            "limite": limite,
            "offset": offset,
            "items":  items,
        }
    except Exception as e:
        raise HTTPException(500, str(e))