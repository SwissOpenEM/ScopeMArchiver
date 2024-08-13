from __future__ import annotations
from typing import Iterable
from datetime import timedelta
import minio
import minio.datatypes
from minio.deleteobjects import DeleteObject
from dataclasses import dataclass
from pathlib import Path

from .log import getLogger, log

from archiver.config.variables import Variables
from archiver.config.blocks import Blocks


@dataclass
class Bucket():
    name: str

    @staticmethod
    def retrieval_bucket() -> Bucket:  # type: ignore
        return Bucket(Variables().MINIO_RETRIEVAL_BUCKET)

    @staticmethod
    def staging_bucket() -> Bucket:  # type: ignore
        return Bucket(Variables().MINIO_STAGING_BUCKET)

    @staticmethod
    def landingzone_bucket() -> Bucket:  # type: ignore
        return Bucket(Variables().MINIO_LANDINGZONE_BUCKET)


class S3Storage():

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(S3Storage, cls).__new__(cls)
            # Put any initialization here.
        return cls._instance

    def __init__(self):
        self._USER = Blocks().MINIO_USER
        self._PASSWORD = Blocks().MINIO_PASSWORD
        self._REGION = Variables().MINIO_REGION
        self._URL = Variables().MINIO_ENDPOINT

        self.STAGING_BUCKET: Bucket = Bucket.staging_bucket()
        self.RETRIEVAL_BUCKET: Bucket = Bucket.retrieval_bucket()
        self.LANDINGZONE_BUCKET: Bucket = Bucket.landingzone_bucket()

        self._minio = minio.Minio(
            endpoint=self._URL,
            access_key=self._USER,
            secret_key=self._PASSWORD.get_secret_value(),
            region=self._REGION,
            secure=False
        )

    @property
    def url(self):
        return self._URL

    @log
    def get_presigned_url(self, bucket: Bucket, filename: str) -> str:
        external_minio = minio.Minio(
            endpoint=Variables().MINIO_EXTERNAL_ENDPOINT,
            access_key=self._USER,
            secret_key=self._PASSWORD.get_secret_value(),
            region=self._REGION,
            secure=False
        )
        url = external_minio.presigned_get_object(
            bucket_name=bucket.name,
            object_name=filename,
            expires=timedelta(hours=2)
        )

        return url

    @log
    def stat_object(self, bucket: Bucket, filename: str) -> minio.datatypes.Object:
        return self._minio.stat_object(
            bucket_name=bucket.name,
            object_name=filename
        )

    @log
    def fget_object(self, bucket: Bucket, folder: str, object_name: str, target_path: Path):
        self._minio.fget_object(
            bucket_name=bucket.name, object_name=object_name, file_path=str(target_path.absolute()))

    @log
    def list_objects(self, bucket: Bucket, folder: str | None = None):
        f = folder or ""
        return self._minio.list_objects(bucket_name=bucket.name, prefix=f + "/", start_after=f"{f}/")

    @log
    def fput_object(self, source_file: Path, destination_file: Path, bucket: Bucket):
        self._minio.fput_object(bucket.name, str(
            destination_file), str(source_file))

    @log
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
