import pytest


@pytest.fixture(scope="function")
def celery_config():
    return {
        "broker_url": 'memory://localhost/',
        "result_backend": "rpc://"
    }
