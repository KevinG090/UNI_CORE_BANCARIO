from fastapi import APIRouter, HTTPException

from db.queries.clientes.clientes import (
    actualizar_cliente,
    crear_cliente,
    listar_clientes,
    obtener_cliente,
)
from db.queries.cupos.cupos import obtener_cupo_por_cliente
from db.queries.creditos.creditos import listar_creditos_por_cupo
from schemas.clientes import ClienteCreate, ClienteUpdate

router = APIRouter()


@router.get("/", summary="Listar clientes")
async def get_clientes(limit: int = 20, page: int = 1, estado: str = None):
    offset = (page - 1) * limit
    return listar_clientes(limit=limit, offset=offset, estado=estado)


@router.get("/{cliente_id}", summary="Obtener cliente por ID")
async def get_cliente(cliente_id: str):
    cliente = obtener_cliente(cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado.")
    return cliente


@router.post("/", status_code=201, summary="Crear cliente")
async def post_cliente(data: ClienteCreate):
    try:
        return crear_cliente(data)
    except Exception as e:
        raise HTTPException(400, str(e))


@router.patch("/{cliente_id}", summary="Actualizar cliente (parcial)")
async def patch_cliente(cliente_id: str, data: ClienteUpdate):
    result = actualizar_cliente(cliente_id, data)
    if not result:
        raise HTTPException(404, "Cliente no encontrado.")
    return result


@router.get("/{cliente_id}/resumen", summary="Resumen 360° del cliente")
async def get_resumen(cliente_id: str):
    cliente = obtener_cliente(cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado.")
    cupo = obtener_cupo_por_cliente(cliente_id)
    creditos = listar_creditos_por_cupo(str(cupo["id"])) if cupo else []
    return {"cliente": cliente, "cupo": cupo, "creditos": creditos}
