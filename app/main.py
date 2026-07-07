"""Punto de entrada FastAPI — Sistema Automatizado de Gestión de Citas (Grupo 10)."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import get_settings
from app.models.db import init_db
from app.scheduler.jobs import start_scheduler

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    sched = start_scheduler()
    yield
    sched.shutdown(wait=False)


app = FastAPI(title="Sistema Automatizado de Gestión de Citas — Clínica San Gabriel",
              version="1.0.0", lifespan=lifespan)
app.include_router(router, prefix=get_settings().api_prefix)

# Frontend web de chat (canal de pruebas y demo)
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="frontend")
