from typing import List, Iterable
from abc import ABC, abstractmethod
from datetime import timedelta
import os
import minio
import minio.datatypes
from minio.deleteobjects import DeleteObject
from dataclasses import dataclass
from pathlib import Path

from .logging import getLogger


@dataclass
class Bucket():
    name: str


class MinioStorage():

    _USER = os.environ.get('MINIO_USER', "minioadmin")
    _PASSWORD = os.environ.get('MINIO_PASS', "minioadmin")
    _REGION = os.environ.get('MINIO_REGION', "eu-west-1")
    _URL = os.environ.get('MINIO_URL', "localhost:9000")

    STAGING_BUCKET: Bucket = Bucket(
        os.environ.get('MINIO_STAGING_BUCKET', "staging"))
    RETRIEVAL_BUCKET: Bucket = Bucket(
        os.environ.get('MINIO_RETRIEVAL_BUCKET', "retrieval"))
    LANDINGZONE_BUCKET: Bucket = Bucket(
        os.environ.get('MINIO_LANDINGZONE_BUCKET', "landing"))

    def __init__(self):
        self._minio = minio.Minio(
            endpoint=self._URL,
            access_key=self._USER,
            secret_key=self._PASSWORD,
            region=self._REGION,
            secure=False
        )

    @property
    def url(self):
        return self._URL

    def get_presigned_url(self, bucket: Bucket, filename: str) -> str:
        url = self._minio.presigned_get_object(
            bucket_name=bucket.name,
            object_name=filename,
            expires=timedelta(hours=2)
        )

        return url

    def stat_object(self, bucket: Bucket, filename: str) -> minio.datatypes.Object:
        return self._minio.stat_object(
            bucket_name=bucket.name,
            object_name=filename
        )

    def get_objects(self, bucket: Bucket, folder: str | None = None):
        f = folder or ""
        return self._minio.list_objects(bucket_name=bucket.name, prefix=f + "/", start_after=f"{f}/")

    def put_object(self, source_file: Path, destination_file: Path, bucket: Bucket):
        self._minio.fput_object(bucket.name, str(destination_file), str(source_file))

    def delete_object(self, minio_prefix: Path, bucket: Bucket) -> None:
        delete_object_list: Iterable[DeleteObject] = list(
            map(
                lambda x: DeleteObject(x.object_name or ""),
                self._minio.list_objects(
                    bucket.name,
                    str(minio_prefix),
                    recursive=True,
                ),
            )
        )

        errors = self._minio.remove_objects(bucket.name, delete_object_list)
        for e in errors:
            getLogger().error(f"Failed to remove objects from Minio {e}")


minioClient = MinioStorage()

__attributes__ = [
    minioClient
]
