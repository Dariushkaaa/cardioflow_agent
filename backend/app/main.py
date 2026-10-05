import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models as _models  # noqa: F401  (регистрация моделей в metadata)
from app.api.v1.router import api_router
from app.api.websockets.endpoint import router as ws_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.seed import seed_demo_data
from app.worker.tasks import setup_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("cardioflow")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    if settings.SEED_DEMO_DATA:
        await seed_demo_data()

    scheduler = None
    if settings.ENABLE_SCHEDULER:
        scheduler = setup_scheduler()
        scheduler.start()
        logger.info("Планировщик эскалации запущен")

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(title="CardioFlow Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}
