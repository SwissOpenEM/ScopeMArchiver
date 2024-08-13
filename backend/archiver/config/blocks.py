from prefect.blocks.system import Secret
from pydantic import SecretStr


class Blocks:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Blocks, cls).__new__(cls)
        return cls._instance

    def __get(self, name: str) -> str:
        s = None
        try:
            s = Secret.load(name)
        finally:
            if s is None:
                return ""
        return s.get()

    @property
    def MINIO_USER(self) -> str:
        return self.__get("minio-user")

    @property
    def MINIO_PASSWORD(self) -> SecretStr:
        return SecretStr(self.__get("minio-password"))

    @property
    def SCICAT_USER(self) -> str:
        return self.__get("scicat-user")

    @property
    def SCICAT_PASSWORD(self) -> SecretStr:
        return SecretStr(self.__get("scicat-password"))
