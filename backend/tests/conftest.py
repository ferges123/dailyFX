import pytest

from app.immich.client import _client_cache
from app.limiter import limiter


@pytest.fixture(autouse=True)
def clear_immich_client_cache():
    _client_cache.clear()


@pytest.fixture(autouse=True)
def configure_limiter(request):
    if "test_rate_limits" not in request.node.fspath.strpath:
        limiter.enabled = False
