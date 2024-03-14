from typing import List
from abc import ABC, abstractmethod
from datetime import timedelta
import os
import minio
from dataclasses import dataclass


@dataclass
class Bucket():
    name: str


class WorkingStorage(ABC):

    @abstractmethod
    def get_presigned_url(self, filename: str, bucket: Bucket) -> str:
        pass

    # @abstractmethod
    def list_archiveable_objects(self) -> List[str]:
        pass


class MinioStorage(WorkingStorage):

    _USER = os.environ.get('MINIO_USER', "minioadmin")
    _PASSWORD = os.environ.get('MINIO_PASS', "minioadmin")
    _REGION = os.environ.get('MINIO_REGION', "eu-west-1")
    _URL = os.environ.get('MINIO_URL', "localhost:9000")

    ARCHIVAL_BUCKET: Bucket = Bucket(
        os.environ.get('MINIO_ARCHIVAL_BUCKET', "archival"))
    RETRIEVAL_BUCKET: Bucket = Bucket(
        os.environ.get('MINIO_RETRIEVAL_BUCKET', "retrieval"))

    def __init__(self):
        self._minio = minio.Minio(
            endpoint=self._URL,
            access_key=self._USER,
            secret_key=self._PASSWORD,
            region=self._REGION,
            secure=False
        )

    def get_presigned_url(self, filename: str, bucket: Bucket) -> str:
        url = self._minio.presigned_get_object(
            bucket_name=bucket.name,
            object_name=filename,
            expires=timedelta(hours=2)
        )

        return url

    def stat_object(self, filename: str, bucket: Bucket) -> minio.Minio.stat_object:
        return self._minio.stat_object(
            bucket_name=bucket.name,
            object_name=filename
        )

    def get_objects(self, bucket: Bucket):
        return self._minio.list_objects(bucket_name=bucket.name)


minioClient = MinioStorage()

__attributes__ = [
    minioClient
]
