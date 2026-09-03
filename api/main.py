from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.metrics import handle_metrics_endpoint, prometheus_metrics_middleware
from api.response import make_error_response
from api.routers.alerts import router as alerts_router
from api.routers.freshness import router as freshness_router
from api.routers.health import router as health_router
from api.routers.pipelines import router as pipelines_router
from api.routers.ranking import router as ranking_router
from api.routers.regions import router as regions_router
from api.routers.stations import router as stations_router
from api.routers.system import router as system_router
from src.common.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="Bike Sharing Operation Intelligence API",
    version="1.0.0",
    description="Read-only REST API for Bike-Sharing operational data marts and pipeline health metrics.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    debug=True,
)

import os

# Register Prometheus HTTP metrics middleware
app.middleware("http")(prometheus_metrics_middleware)

frontend_origins_env = os.getenv("FRONTEND_ORIGINS", "*").strip()
if frontend_origins_env == "*" or not frontend_origins_env:
    allowed_origins = ["*"]
else:
    allowed_origins = [orig.strip() for orig in frontend_origins_env.split(",") if orig.strip()]
    for local_dev_origin in [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]:
        if local_dev_origin not in allowed_origins:
            allowed_origins.append(local_dev_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus /metrics endpoint (for internal scrape)
app.add_api_route("/metrics", handle_metrics_endpoint, methods=["GET"], include_in_schema=False)

# Include Routers under /api/v1 prefix
api_v1_prefix = "/api/v1"
app.include_router(health_router, prefix=api_v1_prefix)
app.include_router(system_router, prefix=api_v1_prefix)
app.include_router(stations_router, prefix=api_v1_prefix)
app.include_router(regions_router, prefix=api_v1_prefix)
app.include_router(ranking_router, prefix=api_v1_prefix)
app.include_router(pipelines_router, prefix=api_v1_prefix)
app.include_router(freshness_router, prefix=api_v1_prefix)
app.include_router(alerts_router, prefix=api_v1_prefix)


@app.get("/", tags=["Root"])
def read_root():
    """Root landing endpoint."""
    return {
        "message": "Welcome to Bike Sharing Operation Intelligence API",
        "docs": "/docs",
        "version": "1.0.0",
    }



# Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom handler for HTTPExceptions to format standard error JSON."""
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        code = exc.detail["code"]
        message = exc.detail["message"]
    else:
        code = "BAD_REQUEST" if exc.status_code == status.HTTP_400_BAD_REQUEST else "ERROR"
        message = str(exc.detail)

    return JSONResponse(
        status_code=exc.status_code,
        content=make_error_response(code=code, message=message),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Fallback handler for unhandled internal server errors."""
    logger.error(f"Unhandled API error on path '{request.url.path}': {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=make_error_response(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred while processing the request.",
        ),
    )
