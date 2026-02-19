import logging

from opensearchpy import AsyncOpenSearch

from ch03.config.config import settings

logger = logging.getLogger(__name__)

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
