import pytest

from app import create_app
from app.db import reset_caches
from app.services.symbol_resolver import clear_resolution_cache


@pytest.fixture(autouse=True)
def _reset_process_caches():
    # Phase 18 Tier 1 introduced process-wide engine/resolution caches. Reset
    # them around every test so tests that reuse a database URL stay isolated.
    reset_caches()
    clear_resolution_cache()
    yield
    reset_caches()
    clear_resolution_cache()


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client
