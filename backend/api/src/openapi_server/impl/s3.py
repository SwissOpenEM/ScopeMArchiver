from typing import Dict, List
import boto3
from botocore.exceptions import ClientError
from botocore.client import Config
from fastapi.responses import JSONResponse
from pydantic import BaseModel, SecretStr
from openapi_server.models.abort_dataset_upload_resp import AbortDatasetUploadResp
from openapi_server.models.upload_request_successful_resp import UploadRequestSuccessfulResp
from openapi_server.models.upload_request_unsuccessful_resp import UploadRequestUnsuccessfulResp
from openapi_server.settings import GetSettings
import minio
import os
import json

from openapi_server.models.complete_upload_body import CompleteUploadBody
from openapi_server.models.complete_upload_resp import CompleteUploadResp
from prefect.blocks.system import Secret

from logging import getLogger

_LOGGER = getLogger("uvicorn.s3")
_GiB = 1024**3
_TB = 1000**4
boto3.set_stream_logger("api.s3.boto3", _LOGGER.level)


def create_bucket_name(dataset_id: str) -> str:
    sanitized_name = dataset_id
    for c in ["_", "/"]:
        sanitized_name = sanitized_name.replace(c, "-")
    sanitized_name = sanitized_name.lower()
    return sanitized_name


async def get_minio_credentials():
    user_block = await Secret.load("minio-user")
    password_block = await Secret.load("minio-password")
    return SecretStr(user_block.get()), SecretStr(password_block.get())


async def get_s3_client():
    settings = GetSettings()
    user, password = await get_minio_credentials()
    s3_client = boto3.client(
        "s3",
        endpoint_url=f"https://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=user.get_secret_value(),
        aws_secret_access_key=password.get_secret_value(),
        region_name=settings.MINIO_REGION,
        config=Config(signature_version="s3v4"),
    )

    return s3_client


async def get_s3_resource():
    settings = GetSettings()
    user, password = await get_minio_credentials()
    s3_resource = boto3.resource(
        "s3",
        endpoint_url=f"https://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=user.get_secret_value(),
        aws_secret_access_key=password.get_secret_value(),
        region_name=settings.MINIO_REGION,
        config=Config(signature_version="s3v4"),
    )

    return s3_resource


async def get_minio_admin_client():
    settings = GetSettings()
    user_block = await Secret.load("minio-user")
    password_block = await Secret.load("minio-password")
    os.environ["MINIO_ACCESS_KEY"] = user_block.get()
    os.environ["MINIO_SECRET_KEY"] = password_block.get()
    provider = minio.credentials.EnvMinioProvider()
    client = minio.MinioAdmin(
        endpoint=f"{settings.MINIO_ENDPOINT}", credentials=provider, region=settings.MINIO_REGION
    )
    return client


async def create_presigned_url(bucket_name, object_name) -> str:
    try:
        client = await get_s3_client()
        presigned_url = client.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket_name, "Key": object_name},
            ExpiresIn=3600,  # URL expiration time in seconds
        )
        return presigned_url
    except ClientError as e:
        _LOGGER.error(f"Error creating multipart upload: {e}")
        raise e


async def create_presigned_urls_multipart(
    bucket_name, object_name, part_count
) -> tuple[str, List[tuple[int, str]]]:
    settings = GetSettings()

    client = await get_s3_client()

    # Create a multipart upload
    try:
        response = client.create_multipart_upload(
            Bucket=bucket_name, Key=object_name, ChecksumAlgorithm="SHA256"
        )
        upload_id = response["UploadId"]
        _LOGGER.info(f"Upload ID: {upload_id}")
    except ClientError as e:
        _LOGGER.error(f"Error creating multipart upload: {e}")
        raise e

    # Generate presigned URLs for each part
    presigned_urls = []
    for part_number in range(1, part_count + 1):
        try:
            presigned_url = client.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": bucket_name,
                    "Key": object_name,
                    "UploadId": upload_id,
                    "PartNumber": part_number,
                },
                HttpMethod="PUT",
                ExpiresIn=settings.URL_EXPIRATION_SECONDS,
            )
            presigned_urls.append((part_number, presigned_url))
        except ClientError as e:
            _LOGGER.error(f"Error generating presigned URL for part {part_number}: {e}")
            raise e

    _LOGGER.debug(presigned_urls)
    return str(upload_id), presigned_urls


class CompletePart(BaseModel):
    # Part number identifies the part.
    PartNumber: int
    ETag: str
    ChecksumSHA256: str


async def complete_multipart_upload(bucket_name, body: CompleteUploadBody) -> CompleteUploadResp:
    parts = []

    # capitalization matters hence to conversion
    for p in body.parts:
        parts.append({"PartNumber": p.part_number, "ChecksumSHA256": p.checksum_sha256, "ETag": p.etag})
    client = await get_s3_client()
    resp = client.complete_multipart_upload(
        Bucket=bucket_name,
        Key=body.object_name,
        UploadId=body.upload_id,
        MultipartUpload={"Parts": parts},
        ChecksumSHA256=body.checksum_sha256,
    )
    return CompleteUploadResp(location=resp["Location"], key=resp["Key"])


async def abort_multipart_upload(
    bucket_name,
    object_name,
    upload_id,
):
    client = await get_s3_client()
    client.abort_multipart_upload(
        Bucket=bucket_name,
        Key=object_name,
        UploadId=upload_id,
    )
    _LOGGER.info(f"Multipart upload aborted successfully. UploadID={upload_id}, ObjectName={object_name}")


def set_bucket_quota(client: minio.MinioAdmin, bucket: str, quota_gib: int):
    minimum_quota = 1024**3
    client.bucket_quota_set(bucket=bucket, size=max(quota_gib * 1024**3, minimum_quota))
    _LOGGER.info(f"Quota set for Bucket {bucket} to {quota_gib} GiB")


def get_bucket_quota(client: minio.MinioAdmin, bucket: str) -> int:
    bucket_quota = client.bucket_quota_get(bucket)
    return json.loads(bucket_quota)["quota"] / _GiB


async def delete_bucket(bucket_name: str):
    resource = await get_s3_resource()
    client = await get_s3_client()
    bucket = resource.Bucket(bucket_name)
    objs = bucket.objects.all()
    for obj in objs:
        client.delete_object(Bucket=bucket_name, Key=obj.key)
    bucket.delete()

    _LOGGER.info(f"Successfully deleted bucket {bucket_name}.")


def create_bucket(client: boto3, bucket: str):
    client.create_bucket(
        ACL="authenticated-read",
        Bucket=bucket,
        CreateBucketConfiguration={
            "LocationConstraint": GetSettings().MINIO_REGION,
        },
        ObjectLockEnabledForBucket=False,
        ObjectOwnership="ObjectWriter",
    )

    _LOGGER.info(f"Bucket {bucket} created")


def get_bucket_names(client) -> List[str]:
    response = client.list_buckets(
        MaxBuckets=1000, ContinuationToken="", Prefix="", BucketRegion=GetSettings().MINIO_REGION
    )

    buckets = [r["Name"] for r in response["Buckets"]]
    return buckets


def get_total_quota(admin, buckets: List[str]) -> int:
    total_quota_gib = 0
    for bucket in buckets:
        try:
            bucket_quota = admin.bucket_quota_get(bucket)
            total_quota_gib += json.loads(bucket_quota)["quota"] / _GiB
        except Exception as e:
            _LOGGER.error(f"Failed to get quota for bucket '{bucket}': {e}")
            continue
    return total_quota_gib


def get_usage_info(client: minio.MinioAdmin) -> Dict:
    return json.loads(client.get_data_usage_info())


async def request_upload(
    dataset_id: str, dataset_size_gib: int
) -> UploadRequestSuccessfulResp | UploadRequestUnsuccessfulResp | JSONResponse:
    """Get all the bucket's quotas and total current usage to calculate if enough space is available.
    Creates a bucket for the dataset if so.
    """

    client = await get_s3_client()
    admin = await get_minio_admin_client()

    info = get_usage_info(admin)

    _LOGGER.info(info)
    total_usage_gib = info["objectsTotalSize"] / 1024**3
    _LOGGER.info(f"TotalSize Used {total_usage_gib}")

    buckets = get_bucket_names(client)
    total_quota_gib = get_total_quota(admin, buckets)
    free_space_factor = GetSettings().FREE_SPACE_FACTOR

    _TOTAL_AVAILABLE_GIB = GetSettings().MINIO_TOTAL_LANDING_SPACE_TB * _TB / _GiB
    max_available_storage_gib = _TOTAL_AVAILABLE_GIB * free_space_factor

    bucket_name = create_bucket_name(dataset_id)

    bucket_exists = bucket_name in buckets

    # in case there was any crashed upload that didn't clean up previously uploaded data
    # remove it here
    if bucket_exists:
        await delete_bucket(bucket_name)

    # Add some buffer to the datset size
    requested_size_gib = int(dataset_size_gib * 1.01)

    enough_space_available = (max_available_storage_gib - total_quota_gib) > requested_size_gib

    _LOGGER.info(f"Total Space: {int(_TOTAL_AVAILABLE_GIB)} GiB")
    _LOGGER.info(f"Total Buffer: {int(max_available_storage_gib)} GiB")
    _LOGGER.info(f"Total Quota: {int(total_quota_gib)} GiB")
    _LOGGER.info(f"Dataset Size: {int(dataset_size_gib)} GiB")
    _LOGGER.info(f"Bucket Quota: {int(requested_size_gib)} GiB")

    if not enough_space_available:
        message = f"Not enough free space for dataset {dataset_id}"
        _LOGGER.info(message)
        response = UploadRequestUnsuccessfulResp(
            message=message, dataset_id=dataset_id, requested_size_gib=requested_size_gib
        )
        return JSONResponse(content=response.model_dump(), status_code=507)

    try:
        message = f"Successfully created bucket for dataset {dataset_id} with name {bucket_name} and quota {requested_size_gib} GiB"
        _LOGGER.info(message)
        create_bucket(client, bucket_name)
        set_bucket_quota(admin, bucket_name, requested_size_gib)
        return UploadRequestSuccessfulResp(message=message)
    except Exception as e:
        message = f"Failed to create bucket or set quota: {e}"
        _LOGGER.error(message)
        response = UploadRequestUnsuccessfulResp(
            message=message, dataset_id=dataset_id, requested_size_gib=requested_size_gib
        )
        return JSONResponse(content=response.model_dump(), status_code=507)


async def abort_upload(dataset_id: str) -> AbortDatasetUploadResp:
    # check if upload in progress
    bucket = create_bucket_name(dataset_id=dataset_id)
    await delete_bucket(bucket)
    return AbortDatasetUploadResp(dataset_id=dataset_id, message=f"Upload {dataset_id} aborted.")
