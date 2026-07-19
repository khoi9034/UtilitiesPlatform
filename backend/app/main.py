from fastapi import FastAPI

from app.api.routes import router
from app.core.config import get_settings
from app.schemas.responses import HealthResponse

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="healthy", application=settings.app_name)
