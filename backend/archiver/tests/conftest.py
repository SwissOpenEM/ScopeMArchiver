import pytest


@pytest.fixture(scope="function")
def celery_config():
    return {"broker_url": "pyamqp://", "result_backend": "rpc://"}
