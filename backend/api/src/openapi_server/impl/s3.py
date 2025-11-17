from collections import defaultdict
import re
from typing import Dict, List, Tuple
import boto3
from botocore.exceptions import ClientError
from botocore.client import Config
from pydantic import BaseModel, SecretStr
from openapi_server.settings import GetSettings
import httpx


from openapi_server.models.complete_upload_body import CompleteUploadBody
from openapi_server.models.complete_upload_resp import CompleteUploadResp
from openapi_server.models.upload_request_resp import UploadRequestResp
from prefect.blocks.system import Secret
from prefect.variables import Variable

from logging import getLogger

_LOGGER = getLogger("uvicorn.s3")

boto3.set_stream_logger("api.s3.boto3", _LOGGER.level)


async def get_landingzone_bucket() -> str:
    return await Variable.get("minio_landingzone_bucket")


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


def prometheus_metrics_to_dict(metrics_string):
    """Chat-GPT inspired function to parse a metrics string"""
    metrics_dict = defaultdict(list)

    for line in metrics_string.strip().split("\n"):
        if line.startswith("#"):
            continue  # Skip comments

        # Regular expression to match metric name with labels and value
        match = re.match(r"([^{} ]+)(?:{([^}]*)})?\s+(.*)", line)
        if match:
            metric_name = match.group(1)
            labels_string = match.group(2)
            value = float(match.group(3))

            # Parse labels
            labels = {}
            if labels_string:
                for label in labels_string.split(","):
                    key, val = label.split("=")
                    labels[key.strip()] = val.strip().strip('"')

            # Append the metric data to the corresponding metric name
            metrics_dict[metric_name].append({"value": value, "labels": labels})

    return metrics_dict


async def fetch_metrics() -> Tuple[List[Dict], List[Dict]]:
    metric_url = f"https://{GetSettings().MINIO_ENDPOINT}/minio/v2/metrics/bucket"

    token = GetSettings().MINIO_METRICS_TOKEN

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token.get_secret_value()}"}
    try:
        resp = httpx.get(url=metric_url, headers=headers)
    except Exception as e:
        _LOGGER.error(e)
        return UploadRequestResp(Ok=False)

    metrics = prometheus_metrics_to_dict(resp.content.decode("utf-8"))

    return metrics["minio_bucket_quota_total_bytes"], metrics["minio_bucket_usage_total_bytes"]


async def request_upload(dataset_pid: str, dataset_size_gb: int) -> UploadRequestResp:
    """Get the landing zone bucket's quota and current usage. The s3 api does not
    provide a way to query that so the metrics are the only way to get that.
    """

    quota_metric, usage_metric = await fetch_metrics()

    bucket_name = await get_landingzone_bucket()
    bucket_quota = 0

    for m in quota_metric:
        if m["labels"]["bucket"] == bucket_name:
            bucket_quota = m["value"]

    bucket_usage = 0
    for m in usage_metric:
        if m["labels"]["bucket"] == bucket_name:
            bucket_usage = m["value"]

    bytes_to_gigabytes = 1024**3

    free_space_factor = GetSettings().FREE_SPACE_FACTOR
    # of no quota is set, the quota is reported as 0. Allowing the upload in that case
    ok = (
        bucket_quota == 0
        or (bucket_quota * free_space_factor - bucket_usage) / bytes_to_gigabytes > dataset_size_gb
    )

    _LOGGER.info(f"Bucket '{bucket_name}' Quota: {bucket_quota / bytes_to_gigabytes} GB")
    _LOGGER.info(f"Bucket '{bucket_name}' Usage: {bucket_usage / bytes_to_gigabytes} GB")
    _LOGGER.info(f"Dataset '{dataset_pid}' Size: {dataset_size_gb} GB")

    return UploadRequestResp(Ok=ok)
