from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routers import tasks, upload, download


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="PPT Agent Worker",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(tasks.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(download.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ppt-agent-worker"}
