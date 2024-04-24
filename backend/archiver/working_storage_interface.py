from typing import Iterable
from datetime import timedelta
import minio
import minio.datatypes
from minio.deleteobjects import DeleteObject
from dataclasses import dataclass
from pathlib import Path

from .logging import getLogger
from .config import settings


@dataclass
class Bucket():
    name: str


class MinioStorage():

    _USER = settings.MINIO_USER
    _PASSWORD = settings.MINIO_PASSWORD
    _REGION = settings.MINIO_REGION
    _URL = settings.MINIO_URL

    STAGING_BUCKET: Bucket = Bucket(settings.MINIO_STAGING_BUCKET)
    RETRIEVAL_BUCKET: Bucket = Bucket(settings.MINIO_RETRIEVAL_BUCKET)
    LANDINGZONE_BUCKET: Bucket = Bucket(settings.MINIO_LANDINGZONE_BUCKET)

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
