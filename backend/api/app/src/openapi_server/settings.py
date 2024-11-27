from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr


class Settings(BaseSettings):
    UVICORN_PORT: int = 8000
    UVICORN_ROOT_PATH: str = "/"
    UVICORN_RELOAD: bool = False
    UVICORN_LOG_LEVEL: str = "info"
    MINIO_ENDPOINT: str = "http://scopem-openem.ethz.ch:9000"
    MINIO_REGION: str = "eu-west1"                # secret
    MINIO_LANDINGZONE_BUCKET: str = "landingzone"  # string
    MINIO_USER: SecretStr
    MINIO_PASSWORD: SecretStr

    class Config:
        secrets_dir = '/run/secrets'
