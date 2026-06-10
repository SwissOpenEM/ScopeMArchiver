from typing import List
import boto3
from botocore.exceptions import ClientError
from botocore.client import Config
from fastapi.responses import JSONResponse
from pydantic import BaseModel, SecretStr
from openapi_server.models.abort_dataset_upload_resp import AbortDatasetUploadResp
from openapi_server.models.upload_request_successful_resp import (
    UploadRequestSuccessfulResp,
)
from openapi_server.models.upload_request_unsuccessful_resp import (
    UploadRequestUnsuccessfulResp,
)
from openapi_server.settings import GetSettings

from openapi_server.models.complete_upload_body import CompleteUploadBody
from openapi_server.models.complete_upload_resp import CompleteUploadResp
from prefect.blocks.system import Secret
from prefect.variables import Variable

from logging import getLogger

_LOGGER = getLogger("uvicorn.s3")

_settings = GetSettings()

_GiB = 1024**3
_TB = 1000**4
boto3.set_stream_logger("api.s3.boto3", _LOGGER.level)


async def landingzone_bucket_name():
    return await Variable.get("s3_landingzone_bucket")


async def s3_endpoint():
    return await Variable.get("s3_external_endpoint")


async def s3_region():
    return await Variable.get("s3_region")


async def get_s3_credentials():
    user_block = await Secret.load("s3-user")
    password_block = await Secret.load("s3-password")
    return SecretStr(user_block.get()), SecretStr(password_block.get())


async def get_s3_client():
    user, password = await get_s3_credentials()
    region = await s3_region()
    endpoint = await s3_endpoint()
    s3_client = boto3.client(
        "s3",
        endpoint_url=f"https://{endpoint}",
        aws_access_key_id=user.get_secret_value(),
        aws_secret_access_key=password.get_secret_value(),
        region_name=region,
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

    return s3_client


async def create_presigned_url(bucket_name, object_name) -> str:
    try:
        client = await get_s3_client()
        presigned_url = client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket_name,
                "Key": object_name,
                "StorageClass": "GLACIER",
            },
            ExpiresIn=_settings.URL_EXPIRATION_SECONDS,  # URL expiration time in seconds
        )
        return presigned_url
    except ClientError as e:
        _LOGGER.error(f"Error creating multipart upload: {e}")
        raise e


async def create_presigned_urls_multipart(
    bucket_name, object_name, part_count
) -> tuple[str, List[tuple[int, str]]]:
    client = await get_s3_client()

    # Create a multipart upload
    try:
        response = client.create_multipart_upload(
            Bucket=bucket_name,
            Key=object_name,
            ChecksumAlgorithm="SHA256",
            StorageClass="GLACIER",
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
                ExpiresIn=_settings.URL_EXPIRATION_SECONDS,
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
        parts.append(
            {
                "PartNumber": p.part_number,
                "ChecksumSHA256": p.checksum_sha256,
                "ETag": p.etag,
            }
        )
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


async def get_bucket_names(client) -> List[str]:
    region = await s3_region()
    response = client.list_buckets(
        MaxBuckets=10,
        ContinuationToken="",
        Prefix="",
        BucketRegion=region,
    )

    buckets = [r["Name"] for r in response["Buckets"]]
    return buckets


async def request_upload(
    dataset_id: str, dataset_size_gib: int
) -> UploadRequestSuccessfulResp | UploadRequestUnsuccessfulResp | JSONResponse:
    """Get all the bucket's quotas and total current usage to calculate if enough space is available.
    Creates a bucket for the dataset if so.
    """

    client = await get_s3_client()

    buckets = await get_bucket_names(client)

    landingzone_bucket = await landingzone_bucket_name()

    bucket_exists = landingzone_bucket in buckets

    if not bucket_exists:
        return UploadRequestUnsuccessfulResp(
            message=f"Bucket '{landingzone_bucket}' does not exist",
            dataset_id=dataset_id,
            requested_size_gib=0,
        )

    return UploadRequestSuccessfulResp(message="success")


async def abort_upload(dataset_id: str) -> AbortDatasetUploadResp:
    return AbortDatasetUploadResp(dataset_id=dataset_id, message=f"Upload {dataset_id} aborted.")
