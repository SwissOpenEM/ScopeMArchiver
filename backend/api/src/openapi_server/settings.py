import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import SecretStr


class Settings(BaseSettings):
    UVICORN_PORT: int = 8000
    UVICORN_ROOT_PATH: str = "/"
    UVICORN_RELOAD: bool = False
    UVICORN_LOG_LEVEL: str = "info"
    MINIO_ENDPOINT: str = "scopem-openemdata.ethz.ch:9000"
    MINIO_REGION: str = "eu-west-1"
    MINIO_USER: SecretStr
    MINIO_PASSWORD: SecretStr
    URL_EXPIRATION_SECONDS: int = 3600

    # JWT Token settings
    IDP_URL: str = "https://scopem-openem.ethz.ch/keycloak"
    IDP_USERNAME: str = "archiver-service"
    IDP_PASSWORD: SecretStr
    IDP_REALM: str = "facility"
    IDP_AUDIENCE: str = "account"
    IDP_CLIENT_ID: str = "archiver-service-api"
    IDP_CLIENT_SECRET: SecretStr
    IDP_ALGORITHM: str = "RS256"

    PREFECT_API_URL: str = "http://prefect.io"

    SCICAT_INGESTOR_GROUP: str = "unx-openem"

    JOB_ENDPOINT_USERNAME: SecretStr
    JOB_ENDPOINT_PASSWORD: SecretStr

    class Config:
        secrets_dir = os.environ.get("SECRETS_DIR", "/run/secrets")


_settings: Optional[Settings] = None


def GetSettings() -> Settings:
    global _settings
    _settings = None
    if _settings is None:
        _settings = Settings()
    return _settings


__all__ = ["GetSettings"]
