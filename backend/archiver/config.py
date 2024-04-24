import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Self
import tomllib
import os
import pprint
from functools import lru_cache


@dataclass
class Settings():
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

    def get_env_overrides(self: Self):
        for a in [a for a in dir(self) if not a.startswith('__')]:
            if a in os.environ.keys():
                setattr(self, a, os.environ.get(a))

    @classmethod
    def from_file(cls, file: Path) -> Self:
        with open(file, "rb") as f:
            data = tomllib.load(f)
            s = cls()
            for k, v in data.items():
                for k2, v1 in v.items():
                    full_key = f"{k.upper()}_{k2.upper()}"
                    if not hasattr(s, full_key):
                        raise Exception("key not found")
                    setattr(s, full_key, v1)

            return s


@lru_cache
def parse_settings():
    parser = argparse.ArgumentParser(
        prog='ProgramName',
        description='What the program does',
        epilog='Text at the bottom of help')

    parser.add_argument('-c', '--config', default=None, type=Path)
    args, _ = parser.parse_known_args()

    if args.config is not None:
        settings = Settings.from_file(args.config)
    else:
        settings = Settings()

    settings.get_env_overrides()

    pprint.pprint(settings)

    return settings


settings = parse_settings()

__all__ = [
    "settings"
]
