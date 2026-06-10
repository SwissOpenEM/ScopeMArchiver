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
        "S3_ENDPOINT": "min.io",
        "S3_TOTAL_LANDING_SPACE_TB": "1",
        "S3_USER": "user",
        "S3_PASSWORD": "pw",
        "IDP_CLIENT_SECRET": "secret",
        "IDP_PASSWORD": "pw",
        "IDP_USERNAME": "archiver-service",
        "IDP_REALM": "facility",
        "IDP_AUDIENCE": "account",
        "IDP_CLIENT_ID": "archiver-service-api",
        "IDP_URL": "https://scopem-openem2.ethz.ch/keycloak",
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
