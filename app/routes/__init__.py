from fastapi import APIRouter

from app.routes.clientes.clientes import router as clientes_router
from app.routes.cupos.cupos import router as cupos_router
from app.routes.creditos.creditos import router as creditos_router

router = APIRouter()

router.include_router(clientes_router, prefix="/clientes", tags=["Clientes"])
router.include_router(cupos_router,    prefix="/cupos",    tags=["Cupos"])
router.include_router(creditos_router, prefix="/creditos", tags=["Créditos & Pagos"])
