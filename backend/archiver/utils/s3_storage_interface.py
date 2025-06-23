from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
import functools
from typing import Callable, Iterable, List
import boto3
from boto3.s3.transfer import TransferConfig
from botocore.client import Config

import datetime

from dataclasses import dataclass
from pathlib import Path

from pydantic import SecretStr

from .log import log_debug, log

from archiver.config.variables import Variables
from archiver.config.blocks import Blocks


@dataclass
class Bucket:
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


@log_debug
def download_file(s3_client, obj, minio_prefix, destination_folder, bucket):
    item_name = Path(obj.key).name
    item_dir = Path(obj.key).parent
    item_parent_dirs = item_dir.relative_to(minio_prefix)
    local_filedir = destination_folder / item_parent_dirs
    local_filedir.mkdir(parents=True, exist_ok=True)
    local_filepath = local_filedir / item_name

    if local_filepath.exists():
        return local_filepath

    config = TransferConfig(
        multipart_threshold=100 * 1024 * 1024,
        max_concurrency=2,
        multipart_chunksize=100 * 1024 * 1024,
    )
    s3_client.download_file(bucket.name, obj.key, local_filepath, Config=config)
    return local_filepath


class S3Storage:
    def __init__(self, url: str, user: str, password: SecretStr, region: str):
        self._URL = url
        self._USER = user
        self._PASSWORD = password
        self._REGION = region

        self.STAGING_BUCKET: Bucket = Bucket.staging_bucket()
        self.RETRIEVAL_BUCKET: Bucket = Bucket.retrieval_bucket()
        self.LANDINGZONE_BUCKET: Bucket = Bucket.landingzone_bucket()

        self._minio = boto3.client(
            "s3",
            endpoint_url=f"https://{self._URL}" if self._URL is not None and self._URL != "" else None,
            aws_access_key_id=self._USER.strip(),
            aws_secret_access_key=self._PASSWORD.get_secret_value().strip(),
            region_name=self._REGION,
            config=Config(signature_version="s3v4", max_pool_connections=32))
        self._resource = boto3.resource(
            "s3",
            endpoint_url=f"https://{self._URL}" if self._URL is not None and self._URL != "" else None,
            aws_access_key_id=self._USER.strip(),
            aws_secret_access_key=self._PASSWORD.get_secret_value().strip(),
            region_name=self._REGION,
            config=Config(signature_version="s3v4"),
        )

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, S3Storage):
            return False
        return self._URL == value._URL and self._USER == value._USER and self._REGION == value._REGION

    @property
    def url(self):
        return self._URL

    @log_debug
    def get_presigned_url(self, bucket: Bucket, filename: str) -> str:
        days_to_seconds = 60 * 60 * 24
        presigned_url = self._minio.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket.name, "Key": filename},
            ExpiresIn=Variables().MINIO_URL_EXPIRATION_DAYS * days_to_seconds,  # URL expiration time in seconds
        )
        return presigned_url

    @dataclass
    class StatInfo:
        Size: int

    @log_debug
    def reset_expiry_date(self, bucket_name: str, filename: str, retention_period_days: int) -> None:

        new_expiration_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=retention_period_days)

        # the only way to reset the expiration date is to copy the object to itself apparently
        copy_source = {
            'Bucket': bucket_name,
            'Key': filename
        }
        self._minio.copy_object(
            Bucket=bucket_name,
            Key=filename,
            CopySource=copy_source,
            MetadataDirective='REPLACE',  # This is important to replace metadata
            Expires=new_expiration_date.isoformat()
        )

    @log_debug
    def stat_object(self, bucket: Bucket, filename: str) -> StatInfo | None:
        try:
            object = self._minio.head_object(Bucket=bucket.name, Key=filename)
            return S3Storage.StatInfo(Size=object["ContentLength"])
        except:
            return None

    @log_debug
    def fget_object(self, bucket: Bucket, folder: str, object_name: str, target_path: Path):
        self._minio.download_file(Bucket=bucket.name, Key=object_name, Filename=str(target_path.absolute()))

    @log
    def download_objects(self,
                         minio_prefix: Path,
                         bucket: Bucket,
                         destination_folder: Path,
                         progress_callback: Callable[[float], None] | None = None) -> List[Path]:
        remote_bucket = self._resource.Bucket(bucket.name)
        objs = remote_bucket.objects.filter(Prefix=str(minio_prefix))

        files: List[Path] = []

        count = 0

        with ThreadPoolExecutor(max_workers=Variables().ARCHIVER_NUM_WORKERS) as executor:
            future_to_key = {executor.submit(download_file, self._minio, key, minio_prefix,
                                             destination_folder, bucket): key for key in objs}

            for future in as_completed(future_to_key):
                count = count + 1
                if progress_callback:
                    progress_callback(count)
                exception = future.exception()

                if not exception:
                    files.append(future.result())
                else:
                    raise exception

        return files

    @dataclass
    class ListedObject:
        Name: str

    @log_debug
    def list_objects(self, bucket: Bucket, folder: str | None = None) -> List[S3Storage.ListedObject]:
        ''' Lists up to 1000 objects in a bucket. This is an s3 limitation
        '''
        f = folder or ""
        remote_bucket = self._resource.Bucket(bucket.name)
        objs = remote_bucket.objects.filter(Prefix=f)

        objects: List[S3Storage.ListedObject] = []
        for obj in objs:
            objects.append(S3Storage.ListedObject(Name=obj.key))

        return objects

    @log
    def fput_object(self, source_file: Path, destination_file: Path, bucket: Bucket):
        self._minio.upload_file(
            Bucket=bucket.name,
            Key=str(destination_file),
            Filename=str(source_file),
            ExtraArgs={},
            Config=TransferConfig(
                multipart_threshold=64 * 1024 * 1024,
                multipart_chunksize=64 * 1024 * 1024,
            ),
        )

    @log
    def delete_objects(self, minio_prefix: Path, bucket: Bucket) -> None:
        remote_bucket = self._resource.Bucket(bucket.name)
        objs = remote_bucket.objects.filter(Prefix=str(minio_prefix))

        for obj in objs:
            self._minio.delete_object(Bucket=bucket.name, Key=obj.key)


@functools.cache
def get_s3_client() -> S3Storage:
    return S3Storage(
        url=Variables().MINIO_ENDPOINT,
        user=Blocks().MINIO_USER,
        password=Blocks().MINIO_PASSWORD,
        region=Variables().MINIO_REGION,
    )
