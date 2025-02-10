import os
from pydantic_settings import BaseSettings
from pydantic import SecretStr


class Settings(BaseSettings):
    UVICORN_PORT: int = 8000
    UVICORN_ROOT_PATH: str = "/"
    UVICORN_RELOAD: bool = False
    UVICORN_LOG_LEVEL: str = "info"
    MINIO_ENDPOINT: str = "scopem-openem.ethz.ch:9000"
    MINIO_REGION: str = "eu-west-1"
    MINIO_LANDINGZONE_BUCKET: str = "landingzone"
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

    SCICAT_API: str = "https://scopem-openem.ethz.ch/scicat/backend/api/v3"

    class Config:
        secrets_dir = os.environ.get("SECRETS_DIR", "/run/secrets")
