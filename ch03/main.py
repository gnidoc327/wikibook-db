import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ch03.dependencies import mysql, opensearch, valkey, s3

# 모든 모델을 import하여 Base.metadata에 등록
import ch03.models.user  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await mysql.startup()
    await opensearch.startup()
    await valkey.startup()
    await s3.startup()
    yield
    await valkey.shutdown()
    await opensearch.shutdown()
    await mysql.shutdown()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/health",
    tags=["Health Check"],
    summary="Health Check용 API",
)
async def health_check() -> str:
    return "ok"
