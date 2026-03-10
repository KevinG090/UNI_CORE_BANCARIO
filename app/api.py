from fastapi import APIRouter
from app.routes import router as routes_router

from core.config import app 


router = APIRouter()
router.include_router(routes_router)

app.include_router(router)

@app.get("/", tags=["Status Service"])
def validate_service():
    """Endpoint for validating responses from service."""
    return True