from __future__ import annotations
import functools
from typing import Iterable, List
import boto3
from boto3.s3.transfer import TransferConfig
from botocore.client import Config

from dataclasses import dataclass
from pathlib import Path

from pydantic import SecretStr

from .log import log

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

    def __init__(self, url: str, user: str, password: SecretStr, region: str):
        self._URL = url
        self._USER = user
        self._PASSWORD = password
        self._REGION = region

        self.STAGING_BUCKET: Bucket = Bucket.staging_bucket()
        self.RETRIEVAL_BUCKET: Bucket = Bucket.retrieval_bucket()
        self.LANDINGZONE_BUCKET: Bucket = Bucket.landingzone_bucket()

        self._minio = boto3.client(
            's3',
            endpoint_url=f"https://{self._URL}" if self._URL is not None and self._URL != '' else None,
            aws_access_key_id=self._USER.strip(),
            aws_secret_access_key=self._PASSWORD.get_secret_value().strip(),
            region_name=self._REGION,
            config=Config(signature_version="s3v4")
        )

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, S3Storage):
            return False
        return self._URL == value._URL and self._USER == value._USER and self._REGION == value._REGION

    @property
    def url(self):
        return self._URL

    @log
    def get_presigned_url(self, bucket: Bucket, filename: str) -> str:
        presigned_url = self._minio.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket.name, 'Key': filename},
            ExpiresIn=3600  # URL expiration time in seconds
        )
        return presigned_url

    @dataclass
    class StatInfo:
        Size: int

    @log
    def stat_object(self, bucket: Bucket, filename: str) -> StatInfo:
        object = self._minio.head_object(
            Bucket=bucket.name,
            Key=filename
        )
        return S3Storage.StatInfo(Size=object['ContentLength'])

    @log
    def fget_object(self, bucket: Bucket, folder: str, object_name: str, target_path: Path):
        self._minio.download_file(
            Bucket=bucket.name,
            Key=object_name,
            Filename=str(target_path.absolute())
        )

    @dataclass
    class ListedObject:
        Name: str

    @log
    def list_objects(self, bucket: Bucket, folder: str | None = None) -> List[S3Storage.ListedObject]:
        f = folder or ""
        response = self._minio.list_objects(
            Bucket=bucket.name,
            Prefix=f,
            Marker=f"{f}/"
        )

        objects: List[S3Storage.ListedObject] = []
        if response is not None and 'Contents' in response.keys():
            for c in response['Contents']:
                objects.append(S3Storage.ListedObject(Name=c['Key']))
            return objects

        return objects

    @ log
    def fput_object(self, source_file: Path, destination_file: Path, bucket: Bucket):
        self._minio.upload_file(
            Bucket=bucket.name,
            Key=str(destination_file),
            Filename=str(source_file),
            ExtraArgs={},
            Config=TransferConfig(
                multipart_threshold=64 * 1024 * 1024,
                multipart_chunksize=64 * 1024 * 1024
            )
        )

    @ log
    def delete_objects(self, minio_prefix: Path, bucket: Bucket) -> None:
        response = self._minio.list_objects(
            Bucket=bucket.name,
            Prefix=str(minio_prefix)
        )
        delete_object_list: Iterable[str] = list(
            map(
                lambda x: x['Key'],
                response['Contents']
            )
        )

        for obj in delete_object_list:
            response = self._minio.delete_object(
                Bucket=bucket.name,
                Key=obj)


@functools.cache
def get_s3_client() -> S3Storage:
    return S3Storage(
        url=Variables().MINIO_ENDPOINT,
        user=Blocks().MINIO_USER,
        password=Blocks().MINIO_PASSWORD,
        region=Variables().MINIO_REGION
    )