from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy import text

from app.database import engine

templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="Vineyard Smart IoT API",
    description=(
        "API интеллектуальной системы мониторинга "
        "виноградника и автоматизированного полива."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={},
    )

@app.get("/")
async def root():
    return {
        "project": "Vineyard Smart IoT",
        "message": "Backend is running",
        "version": "0.2.0",
    }


@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "ok",
        "service": "vineyard-smart-iot-backend",
    }


@app.get("/api/v1/db-health")
async def database_health():
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "database": "connected",
        "test_query": result.scalar_one(),
    }

from app.api.telemetry import router as telemetry_router
from app.api.dashboard import router as dashboard_router
from app.api.control import router as control_router


app.include_router(
    telemetry_router,
    prefix="/api/v1",
    tags=["Telemetry"],
)

app.include_router(
    dashboard_router,
    prefix="/api/v1",
    tags=["Dashboard"],
)


app.include_router(
    control_router,
    prefix="/api/v1",
    tags=["Control"],
)

