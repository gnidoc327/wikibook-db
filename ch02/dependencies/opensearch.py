import logging

from opensearchpy import AsyncOpenSearch

from ch02.config.config import settings

logger = logging.getLogger(__name__)

# OpenSearch는 HTTP 기반 클라이언트로 내부적으로 urllib3/aiohttp의
# connection pooling을 사용하므로 별도의 connection pool 설정이 불필요합니다.
_client = AsyncOpenSearch(
    hosts=[{"host": settings.opensearch.host, "port": settings.opensearch.port}],
    use_ssl=False,
    verify_certs=False,
)


def get_client() -> AsyncOpenSearch:
    """
    `client: AsyncOpenSearch = Depends(get_client)`로 사용
    """
    return _client
