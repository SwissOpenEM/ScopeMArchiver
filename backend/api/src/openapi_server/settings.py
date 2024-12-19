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

    class Config:
        secrets_dir = os.environ.get('SECRETS_DIR', "/run/secrets")
