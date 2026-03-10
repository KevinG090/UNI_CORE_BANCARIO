from fastapi import APIRouter, HTTPException

from db.queries.cupos.cupos import crear_cupo, obtener_cupo, obtener_cupo_por_cliente
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
