import os
from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr


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
    REALM: str = "facility"
    AUDIENCE: str = "account"
    CLIENT_ID: str = "archiver-service-api"
    CLIENT_SECRET: SecretStr
    IDP_USERNAME: str = "archiver-service"
    IDP_PASSWORD: SecretStr
    ALGORITHM: str = "RS256"
    ISSUER: str = "OpenEMIssuer"

    class Config:
        secrets_dir = os.environ.get("SECRETS_DIR", "/run/secrets")
