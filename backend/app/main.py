from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import engine
from app.routers import health, stream


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="PEAD Trading System", lifespan=lifespan)

app.include_router(health.router)
app.include_router(stream.router, prefix="/stream")
