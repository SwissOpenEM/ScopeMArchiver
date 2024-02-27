from typing import List
from abc import ABC, abstractmethod
from datetime import timedelta
import minio


class WorkingStorage(ABC):

    @abstractmethod
    def get_presigned_url(self, filename: str) -> str:
        pass

    # @abstractmethod
    def list_archiveable_objects(self) -> List[str]:
        pass


class MinioStorage(WorkingStorage):

    _USER = "minioadmin"
    _PASSWORD = "minioadmin"
    _REGION = "eu-west-1"
    _URL = "openem-dev.ethz.ch:9000"
    _ARCHIVAL_BUCKET = "archival"
    _RETRIEVAL_BUCKET = "archiving.openem-dev.ethz.ch"

    def __init__(self):
        self._minio = minio.Minio(
            endpoint=self._URL,
            access_key=self._USER,
            secret_key=self._PASSWORD,
            region=self._REGION,
            secure=False
        )

    def get_presigned_url(self, filename: str) -> str:
        url = self._minio.presigned_get_object(
            bucket_name=self._RETRIEVAL_BUCKET,
            object_name=filename,
            expires=timedelta(hours=2)
        )

        return url

    def stat_object(self, filename: str) -> minio.Minio.stat_object:
        return self._minio.stat_object(
            bucket_name=self._RETRIEVAL_BUCKET,
            object_name=filename
        )
