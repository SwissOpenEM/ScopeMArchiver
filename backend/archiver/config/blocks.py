from prefect.blocks.system import Secret


class Blocks:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Blocks, cls).__new__(cls)
        return cls._instance

    def __get(self, name: str) -> str:
        return Secret.load(name).get()

    @property
    def MINIO_USER(self) -> str:
        return self.__get("MINIO_USER")

    @property
    def MINIO_PASSWORD(self) -> str:
        return self.__get("MINIO_PASS")
