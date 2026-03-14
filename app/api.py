from fastapi import APIRouter
from app.routes import router as routes_router

from core.config import app 
from fastapi.responses import HTMLResponse
from fastapi.openapi.docs import get_redoc_html
from core.config import get_settings

router = APIRouter()
router.include_router(routes_router)

app.include_router(router)

# Redoc con version estable del CDN
@app.get("/redoc", include_in_schema=False)
def redoc_html() -> HTMLResponse:
    print("redoc_html")
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=get_settings().PROJECT_NAME + " - ReDoc",
        redoc_js_url=get_settings().URL_API_REDOC,
    )


@app.get("/", tags=["Status Service"])
def validate_service():
    """Endpoint for validating responses from service."""
    return True