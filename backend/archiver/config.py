from pathlib import Path
from prefect.variables import Variable
import argparse
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="forbid",
        validate_default=True,
    )

    MINIO_REGION: str = ""
    MINIO_USER: str = ""
    MINIO_PASSWORD: str = ""
    MINIO_RETRIEVAL_BUCKET: str = ""
    MINIO_STAGING_BUCKET: str = ""
    MINIO_LANDINGZONE_BUCKET: str = ""
    MINIO_URL: str = ""

    API_ROOT_PATH: str = ""
    API_PORT: int = 0
    API_LOG_LEVEL: str = ""
    API_RELOAD: bool = False

    LTS_STORAGE_ROOT: Path = Path("")
    ARCHIVER_SCRATCH_FOLDER: Path = Path("")

    SCICAT_ENDPOINT: str = ""
    SCICAT_API_PREFIX: str = ""


class Variables:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Variables, cls).__new__(cls)
            # Put any initialization here.
        return cls._instance

    def __get(self, name: str) -> str:
        c = Variable.get(name)
        return c.value if c is not None else ""

    @property
    def SCICAT_ENDPOINT(self) -> str:
        return self.__get("scicat_endpoint")

    @property
    def SCICAT_API_PREFIX(self) -> str:
        return self.__get("scicat_api_prefix")

    @property
    def MINIO_RETRIEVAL_BUCKET(self) -> str:
        return self.__get("minio_retrieval_bucket")

    @property
    def MINIO_LANDINGZONE_BUCKET(self) -> str:
        return self.__get("minio_landingzone_bucket")

    @property
    def MINIO_STAGING_BUCKET(self) -> str:
        return self.__get("minio_staging_bucket")

    @property
    def MINIO_REGION(self) -> str:
        return self.__get("minio_region")

    @property
    def MINIO_USER(self) -> str:
        return self.__get("minio_user")

    @property
    def MINIO_PASSWORD(self) -> str:
        return self.__get("minio_password")

    @property
    def MINIO_URL(self) -> str:
        return self.__get("minio_url")

    @property
    def ARCHIVER_SCRATCH_FOLDER(self) -> Path:
        return Path(self.__get("archiver_scratch_folder"))

    @property
    def LTS_STORAGE_ROOT(self) -> Path:
        return Path(self.__get("lts_storage_root"))


def parse_config():
    parser = argparse.ArgumentParser(
        prog='ProgramName',
        description='What the program does',
        epilog='Text at the bottom of help')

    parser.add_argument('-c', '--config', default=None, type=Path)

    args, _ = parser.parse_known_args()

    global config
    config = AppConfig(_env_file=args.config)
    return config


def register_variables_from_config() -> AppConfig:
    config = parse_config()
    model = config.model_dump()
    for s in [s for s in dir(Variables()) if not s.startswith('__') and not s.startswith('_')]:
        Variable.set(s.lower(), str(model[s]), overwrite=True)
    return config
