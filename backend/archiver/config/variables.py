from pathlib import Path
from prefect.variables import Variable
import os

from utils.log import getLogger

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class PrefectVariablesModel(BaseSettings):
    """Pydantic model of the Prefect Variables config

    Args:
        BaseSettings (_type_): _description_

    """

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="forbid",
        validate_default=True,
    )

    S3_REGION: str = ""
    S3_ARCHIVAL_BUCKET: str = ""
    S3_LANDINGZONE_BUCKET: str = ""
    S3_ENDPOINT: str = ""
    S3_EXTERNAL_ENDPOINT: str = ""
    S3_URL_EXPIRATION_DAYS: int = 7

    ARCHIVER_SCRATCH_FOLDER: Path = Path("")
    ARCHIVER_TARGET_SIZE_GB: int = 20
    ARCHIVER_NUM_WORKERS: int = 4

    SCICAT_ENDPOINT: str = ""
    SCICAT_API_PREFIX: str = ""
    SCICAT_DATASETS_API_PREFIX: str = ""
    SCICAT_JOBS_API_PREFIX: str = ""


class Variables:
    """Singleton abstracting access to all Variables expected to be defined in Prefect"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Variables, cls).__new__(cls)
        return cls._instance

    def __get(self, name: str) -> str:
        c = None

        # try for local overrides as env variables
        c = os.environ.get(name.upper())
        if c is not None:
            return c

        try:
            c = Variable.get(name)
        finally:
            if c is None:
                getLogger().warning(f"Value {name} not found in config, returning empty string")
                return ""
            return c

    @property
    def SCICAT_ENDPOINT(self) -> str:
        return self.__get("scicat_endpoint")

    @property
    def SCICAT_API_PREFIX(self) -> str:
        return self.__get("scicat_api_prefix") or ""

    @property
    def SCICAT_DATASETS_API_PREFIX(self) -> str:
        return self.__get("scicat_datasets_api_prefix") or ""

    @property
    def SCICAT_JOBS_API_PREFIX(self) -> str:
        return self.__get("scicat_jobs_api_prefix") or ""

    @property
    def S3_ARCHIVAL_BUCKET(self) -> str:
        return self.__get("s3_archival_bucket")

    @property
    def S3_LANDINGZONE_BUCKET(self) -> str:
        return self.__get("s3_landingzone_bucket")

    @property
    def S3_REGION(self) -> str:
        return self.__get("s3_region")

    @property
    def S3_ENDPOINT(self) -> str:
        return self.__get("s3_endpoint")

    @property
    def S3_URL_EXPIRATION_DAYS(self) -> int:
        return int(self.__get("s3_url_expiration_days") or 7)

    @property
    def S3_EXTERNAL_ENDPOINT(self) -> str:
        return self.__get("s3_external_endpoint")

    @property
    def ARCHIVER_SCRATCH_FOLDER(self) -> Path:
        return Path(self.__get("archiver_scratch_folder"))

    @property
    def ARCHIVER_TARGET_SIZE_GB(self) -> int:
        return int(self.__get("archiver_target_size_gb") or 200)

    @property
    def ARCHIVER_NUM_WORKERS(self) -> int:
        return int(self.__get("archiver_num_workers") or 30)


def register_variables_from_config(config: PrefectVariablesModel) -> None:
    model = config.model_dump()
    print(model)
    for s in [s for s in dir(Variables()) if not s.startswith("__") and not s.startswith("_")]:
        if s in model.keys():
            Variable.set(s.lower(), str(model[s]), overwrite=True)
