import logging
from typing import AsyncGenerator

import aioboto3
from botocore.exceptions import ClientError

from ch04.config.config import settings

logger = logging.getLogger(__name__)

# aioboto3 Session은 thread-safe하며 재사용 가능합니다.
# S3 client는 요청마다 async context manager로 생성합니다.
_session = aioboto3.Session(
    aws_access_key_id=settings.s3.access_key,
    aws_secret_access_key=settings.s3.secret_key,
    region_name=settings.s3.region,
)


async def get_s3_client() -> AsyncGenerator:
    """FastAPI Depends()에서 사용할 S3 client dependency."""
    async with _session.client(
        "s3",
        endpoint_url=settings.s3.endpoint_url,
    ) as client:
        yield client


async def startup() -> None:
    """서버 시작 시 S3 연결 확인 및 버킷 초기화를 수행합니다."""
    async with _session.client("s3", endpoint_url=settings.s3.endpoint_url) as s3:
        try:
            await s3.create_bucket(Bucket=settings.s3.bucket_name)
            logger.info("S3 버킷 생성 완료: %s", settings.s3.bucket_name)
        except ClientError as e:
            if e.response["Error"]["Code"] not in (
                "BucketAlreadyExists",
                "BucketAlreadyOwnedByYou",
            ):
                raise
        logger.info("S3 연결 완료: bucket=%s", settings.s3.bucket_name)
