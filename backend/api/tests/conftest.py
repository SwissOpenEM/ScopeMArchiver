import os
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openapi_server.__main__ import app as application


@pytest.fixture(autouse=True)
def env_fixture():
    envs = {
        "PREFECT_API_URL": "https://prefect.io/api",
        "PREFECT_LOGGING_LEVEL": "debug",
        "MINIO_ENDPOINT": "min.io",
        "MINIO_TOTAL_LANDING_SPACE_TB": "1",
        "MINIO_USER": "user",
        "MINIO_PASSWORD": "pw",
        "IDP_CLIENT_SECRET": "secret",
        "IDP_PASSWORD": "pw",
        "JOB_ENDPOINT_PASSWORD": "pw",
        "JOB_ENDPOINT_USERNAME": "username",
    }

    for k, v in envs.items():
        os.environ[k] = v

    yield

    for k, v in envs.items():
        os.environ.pop(k)


@pytest.fixture
def app() -> FastAPI:
    application.dependency_overrides = {}

    return application


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)
