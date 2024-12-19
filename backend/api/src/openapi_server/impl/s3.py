from typing import List
import boto3
from botocore.exceptions import ClientError
from botocore.client import Config
from pydantic import BaseModel
from openapi_server.settings import Settings


from openapi_server.models.complete_upload_body import CompleteUploadBody
from openapi_server.models.complete_upload_resp import CompleteUploadResp

from logging import getLogger

_LOGGER = getLogger("api.s3")
_SETTINGS = Settings()

boto3.set_stream_logger('api.s3.boto3', _LOGGER.level)

s3_client = boto3.client(
    's3',
    endpoint_url=f"https://{_SETTINGS.MINIO_ENDPOINT}",
    aws_access_key_id=_SETTINGS.MINIO_USER.get_secret_value(),
    aws_secret_access_key=_SETTINGS.MINIO_PASSWORD.get_secret_value(),
    region_name=_SETTINGS.MINIO_REGION,
    config=Config(signature_version="s3v4")
)


def create_presigned_url(bucket_name, object_name) -> str:
    try:
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=3600  # URL expiration time in seconds
        )
        return presigned_url
    except ClientError as e:
        _LOGGER.error(f"Error creating multipart upload: {e}")
        raise e


def create_presigned_urls_multipart(bucket_name, object_name, part_count) -> tuple[str, List[tuple[int, str]]]:
    # Create a multipart upload
    try:
        response = s3_client.create_multipart_upload(
            Bucket=bucket_name, Key=object_name, ChecksumAlgorithm='SHA256')
        upload_id = response['UploadId']
        _LOGGER.info(f"Upload ID: {upload_id}")
    except ClientError as e:
        _LOGGER.error(f"Error creating multipart upload: {e}")
        raise e

    # Generate presigned URLs for each part
    presigned_urls = []
    for part_number in range(1, part_count + 1):
        try:
            presigned_url = s3_client.generate_presigned_url(
                'upload_part',
                Params={
                    'Bucket': bucket_name,
                    'Key': object_name,
                    'UploadId': upload_id,
                    'PartNumber': part_number
                },
                HttpMethod="PUT",
                ExpiresIn=_SETTINGS.URL_EXPIRATION_SECONDS

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


# object_name, upload_id, parts: List[CompletePart], checksumSHA256):
def complete_multipart_upload(bucket_name, body: CompleteUploadBody) -> CompleteUploadResp:
    resp = s3_client.complete_multipart_upload(Bucket=bucket_name,
                                               Key=body.object_name,
                                               UploadId=body.upload_id,
                                               MultipartUpload={'Parts': [p.model_dump(by_alias=True) for p in body.parts]},
                                               ChecksumSHA256=body.checksum_sha256
                                               )
    return CompleteUploadResp(Location=resp["Location"], Key=resp["Key"])


def abort_multipart_upload(bucket_name, object_name, upload_id,):
    s3_client.abort_multipart_upload(Bucket=bucket_name,
                                     Key=object_name,
                                     UploadId=upload_id,
                                     )
    _LOGGER.info(f"Multipart upload aborted successfully. UploadID={upload_id}, ObjectName={object_name}")
