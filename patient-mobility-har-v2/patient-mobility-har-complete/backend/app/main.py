"""
Application entrypoint. Creates the FastAPI instance, configures CORS,
mounts the uploads directory for static file access (patient photos,
alert screenshots, reports), registers every router, and wires
startup/shutdown events.

Run with:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database.init_db import init_db
from app.pipeline.monitoring_worker import monitoring_worker
from app.utils.logger import get_logger

from app.api import (
    auth,
    patients,
    activities,
    alerts,
    reports,
    analytics,
    camera,
    settings as settings_api,
    websocket,
    caregivers,
    ml_metrics,
)

logger = get_logger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Based Human Activity Recognition System for Patient Mobility Assessment — REST API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=str(settings.upload_path)), name="uploads")

app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(activities.router)
app.include_router(alerts.router)
app.include_router(reports.router)
app.include_router(analytics.router)
app.include_router(camera.router)
app.include_router(settings_api.router)
app.include_router(websocket.router)
app.include_router(caregivers.router)
app.include_router(ml_metrics.router)


@app.on_event("startup")
def on_startup() -> None:
    logger.info("Starting %s (env=%s)", settings.APP_NAME, settings.APP_ENV)
    init_db()


@app.on_event("shutdown")
def on_shutdown() -> None:
    logger.info("Shutting down — stopping monitoring worker if active.")
    if monitoring_worker.is_running():
        monitoring_worker.stop()


@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}
