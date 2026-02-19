import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ch01.dependencies import mysql, s3
from ch01.routers import article, comment, user

# 모든 모델을 import하여 Base.metadata에 등록
import ch01.models.article  # noqa: F401
import ch01.models.board  # noqa: F401
import ch01.models.comment  # noqa: F401
import ch01.models.jwt_blacklist  # noqa: F401
import ch01.models.user  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await mysql.startup()
    await s3.startup()
    yield
    await mysql.shutdown()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user.router)
app.include_router(article.router)
app.include_router(comment.router)


@app.get(
    "/health",
    tags=["Health Check"],
    summary="Health Check용 API",
)
async def health_check() -> str:
    return "ok"
