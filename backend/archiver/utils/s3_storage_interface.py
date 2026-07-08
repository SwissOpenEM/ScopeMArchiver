from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
import functools
import time
from typing import Callable, List
import boto3
from boto3.s3.transfer import TransferConfig
from botocore.client import Config


from dataclasses import dataclass
from pathlib import Path

from pydantic import SecretStr

from .log import log_debug, log, getLogger

from config.variables import Variables
from config.blocks import Blocks


@dataclass
class Bucket:
    name: str

    @staticmethod
    def archival_bucket() -> Bucket:  # type: ignore
        return Bucket(Variables().S3_ARCHIVAL_BUCKET)

    @staticmethod
    def landingzone_bucket() -> Bucket:  # type: ignore
        return Bucket(Variables().S3_LANDINGZONE_BUCKET)


class S3Storage:
    def __init__(self, url: str, user: str, password: SecretStr, region: str):
        self._URL = url
        self._USER = user
        self._PASSWORD = password
        self._REGION = region

        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{self._URL}" if self._URL is not None and self._URL != "" else None,
            aws_access_key_id=self._USER.strip(),
            aws_secret_access_key=self._PASSWORD.get_secret_value().strip(),
            region_name=self._REGION,
            verify=False,
            config=Config(
                signature_version="s3v4",
                connect_timeout=30,
                read_timeout=60,
                retries={"max_attempts": 3, "mode": "adaptive"},
                max_pool_connections=5,  # Reduce for local node
                tcp_keepalive=True,  # Keep connection alive
                s3={"payload_signing_enabled": True, "addressing_style": "path"},
            ),
        )

        def remove_expect_header(request, **kwargs):
            request.headers.pop("Expect", None)

        self._client.meta.events.register("before-send.s3.PutObject", remove_expect_header)

        def force_standard_storage_class(params, **kwargs):
            params["StorageClass"] = "GLACIER"

        self._client.meta.events.register("provide-client-params.s3.PutObject", force_standard_storage_class)
        self._client.meta.events.register(
            "provide-client-params.s3.CreateMultipartUpload",
            force_standard_storage_class,
        )
        self._external_s3_client = boto3.client(
            "s3",
            endpoint_url=f"https://{Variables().S3_EXTERNAL_ENDPOINT}",
            aws_access_key_id=self._USER.strip(),
            aws_secret_access_key=self._PASSWORD.get_secret_value().strip(),
            verify=False,
            region_name=self._REGION,
            config=Config(
                signature_version="s3v4",
                connect_timeout=30,
                read_timeout=60,
                retries={"max_attempts": 3, "mode": "adaptive"},
                max_pool_connections=5,
                tcp_keepalive=True,
                s3={"payload_signing_enabled": True, "addressing_style": "path"},
            ),
        )

        self._resource = boto3.resource(
            "s3",
            endpoint_url=f"https://{self._URL}" if self._URL is not None and self._URL != "" else None,
            aws_access_key_id=self._USER.strip(),
            aws_secret_access_key=self._PASSWORD.get_secret_value().strip(),
            region_name=self._REGION,
            verify=False,
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

        presigned_url = self._external_s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket.name, "Key": filename},
            ExpiresIn=Variables().S3_URL_EXPIRATION_DAYS * days_to_seconds,  # URL expiration time in seconds
        )
        return presigned_url

    @dataclass
    class StatInfo:
        Size: int

    @log_debug
    def stat_object(self, bucket: Bucket, filename: str) -> StatInfo | None:
        try:
            object = self._client.head_object(Bucket=bucket.name, Key=filename)
            return S3Storage.StatInfo(Size=object["ContentLength"])
        except Exception:
            return None

    @log_debug
    def fget_object(self, bucket: Bucket, folder: str, object_name: str, target_path: Path) -> None:
        self.restore_objects(bucket=Bucket, objects=[object_name])
        self.check_restore(bucket=Bucket, object=object_name)

        self._client.download_file(Bucket=bucket.name, Key=object_name, Filename=str(target_path.absolute()))

    @log
    def restore_objects(self, bucket: Bucket, objects: List[str]) -> None:
        for obj in objects:
            self._client.restore_object(
                Bucket=bucket.name,
                Key=obj,
                RestoreRequest={
                    "Days": Variables().S3_URL_EXPIRATION_DAYS,
                    "GlacierJobParameters": {
                        "Tier": "Expedited"  # Expedited (~5min) | Standard (~5hr) | Bulk (~12hr)
                    },
                },
            )

    @log
    def check_restore(self, bucket: Bucket, object: str) -> None:
        while True:
            head = self._client.head_object(Bucket=bucket.name, Key=object)
            restore_status = head.get("Restore", "")
            getLogger().debug(restore_status)
            if 'ongoing-request="false"' in restore_status:
                getLogger().info("Restore complete, ready to download")
                break
            getLogger().debug("Still restoring, waiting 60s...")
            time.sleep(60)

    @log_debug
    def download_file(self, obj, prefix, destination_folder, bucket):
        item_name = Path(obj.key).name
        item_dir = Path(obj.key).parent
        item_parent_dirs = item_dir.relative_to(prefix)
        local_filedir = destination_folder / item_parent_dirs
        local_filedir.mkdir(parents=True, exist_ok=True)
        local_filepath = local_filedir / item_name

        if local_filepath.exists():
            return local_filepath

        self.check_restore(bucket, obj.key)

        config = TransferConfig(
            multipart_threshold=100 * 1024 * 1024,
            max_concurrency=2,
            multipart_chunksize=100 * 1024 * 1024,
        )

        self._client.download_file(bucket.name, obj.key, local_filepath, Config=config)
        return local_filepath

    @log
    def download_objects(
        self,
        prefix: Path,
        bucket: Bucket,
        destination_folder: Path,
        progress_callback: Callable[[float], None] | None = None,
    ) -> List[Path]:
        remote_bucket = self._resource.Bucket(bucket.name)
        objs = remote_bucket.objects.filter(Prefix=str(prefix))

        self.restore_objects(bucket=bucket, objects=[obj.key for obj in objs])

        files: List[Path] = []

        count = 0

        with ThreadPoolExecutor(max_workers=Variables().ARCHIVER_NUM_WORKERS) as executor:
            future_to_key = {
                executor.submit(
                    S3Storage.download_file,
                    self,
                    key,
                    prefix,
                    destination_folder,
                    bucket,
                ): key
                for key in objs
            }

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
        """Lists up to 1000 objects in a bucket. This is an s3 limitation"""
        f = folder or ""
        remote_bucket = self._resource.Bucket(bucket.name)
        objs = remote_bucket.objects.filter(Prefix=f)

        objects: List[S3Storage.ListedObject] = []
        for obj in objs:
            objects.append(S3Storage.ListedObject(Name=obj.key))

        return objects

    @log
    def fput_object(self, source_file: Path, destination_file: Path, bucket: Bucket):
        self._client.upload_file(
            Bucket=bucket.name,
            Key=str(destination_file),
            Filename=str(source_file),
            ExtraArgs={"StorageClass": "GLACIER"},
            Config=TransferConfig(
                multipart_threshold=64 * 1024 * 1024,
                multipart_chunksize=64 * 1024 * 1024,
            ),
        )

    @log
    def delete_objects(self, prefix: Path, bucket: Bucket) -> None:
        remote_bucket = self._resource.Bucket(bucket.name)
        objs = remote_bucket.objects.filter(Prefix=str(prefix))

        for obj in objs:
            self._client.delete_object(Bucket=bucket.name, Key=obj.key)

    @log
    def create_bucket(self, bucket: Bucket) -> None:
        self._client.create_bucket(
            ACL="authenticated-read",
            Bucket=bucket.name,
            CreateBucketConfiguration={
                "LocationConstraint": "eu-west-1",
            },
            ObjectLockEnabledForBucket=False,
            ObjectOwnership="ObjectWriter",
        )

    @log
    def delete_bucket(self, bucket: Bucket) -> None:
        self._client.delete_bucket(Bucket=bucket.name)


@functools.cache
def get_s3_client() -> S3Storage:
    return S3Storage(
        url=Variables().S3_ENDPOINT,
        user=Blocks().S3_USER,
        password=Blocks().S3_PASSWORD,
        region=Variables().S3_REGION,
    )
