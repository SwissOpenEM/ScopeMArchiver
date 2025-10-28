# coding: utf-8

from typing import List
from fastapi.testclient import TestClient


from openapi_server.models.abort_upload_body import AbortUploadBody  # noqa: F401
from openapi_server.models.abort_upload_resp import AbortUploadResp  # noqa: F401
from openapi_server.models.complete_upload_body import CompleteUploadBody  # noqa: F401
from openapi_server.models.complete_upload_resp import CompleteUploadResp  # noqa: F401
from openapi_server.models.http_validation_error import HTTPValidationError  # noqa: F401
from openapi_server.models.internal_error import InternalError  # noqa: F401
from openapi_server.models.presigned_url_body import PresignedUrlBody  # noqa: F401
from openapi_server.models.presigned_url_resp import PresignedUrlResp  # noqa: F401

from unittest.mock import patch
from utils import mock_validate_token


def mock_abort_multipart_upload(*args, **kwargs) -> AbortUploadResp:
    return AbortUploadResp(message="", upload_id="", object_name="")


@patch("openapi_server.impl.s3upload_impl.abort_multipart_upload", mock_abort_multipart_upload)
@patch("openapi_server.security_api.validate_token", mock_validate_token)
def test_abort_multipart_upload(client: TestClient):
    """Test case for abort_multipart_upload

    Abort Multipart Upload
    """
    abort_upload_body = {"upload_id": "UploadID", "object_name": "ObjectName"}

    headers = {
        "Authorization": "Bearer special-key",
    }

    response = client.request(
        "POST",
        "/s3/abortMultipartUpload",
        headers=headers,
        json=abort_upload_body,
    )

    assert response.status_code == 201


def mock_complete_multipart_upload(*args, **kwargs) -> CompleteUploadResp:
    return CompleteUploadResp(location="", key="")


@patch("openapi_server.impl.s3upload_impl.complete_multipart_upload", mock_complete_multipart_upload)
@patch("openapi_server.security_api.validate_token", mock_validate_token)
def test_complete_upload(client: TestClient):
    """Test case for complete_upload

    Complete Upload
    """
    complete_upload_body = {"parts": [{"part_number": 1, "etag": "e_tag", "checksum_sha256": "ChecksumSHA256"}, {
        "part_number": 0, "etag": "ETag", "checksum_sha256": "ChecksumSHA256"}], "upload_id": "UploadID", "object_name": "ObjectName", "checksum_sha256": "ChecksumSHA256"}

    headers = {
        "Authorization": "Bearer special-key",
    }
    # uncomment below to make a request
    response = client.request(
        "POST",
        "/s3/completeUpload",
        headers=headers,
        json=complete_upload_body,
    )

    # uncomment below to assert the status code of the HTTP response
    assert response.status_code == 201


def mock_create_presigned_url(*args, **kwargs) -> str:
    return "https:/www.min.io/file"


@patch("openapi_server.impl.s3upload_impl.create_presigned_url", mock_create_presigned_url)
@patch("openapi_server.security_api.validate_token", mock_validate_token)
def test_get_presigned_urls(client: TestClient):
    """Test case for get_presigned_urls

    Get Presigned Urls
    """
    presigned_url_body = {"parts": 1, "object_name": "ObjectName"}

    headers = {
        "Authorization": "Bearer special-key",
    }
    # uncomment below to make a request
    response = client.request(
        "POST",
        "/s3/presignedUrls",
        headers=headers,
        json=presigned_url_body,
    )

    # uncomment below to assert the status code of the HTTP response
    assert response.status_code == 201


def mock_create_presigned_urls_multipart(*args, **kwargs) -> tuple[str, List[tuple[int, str]]]:
    return ("uploadID", [(0, "https:/www.min.io/file1"), (1, "https:/www.min.io/file2")])


@patch("openapi_server.impl.s3upload_impl.create_presigned_urls_multipart", mock_create_presigned_urls_multipart)
@patch("openapi_server.security_api.validate_token", mock_validate_token)
def test_get_presigned_urls_multipart(client: TestClient):
    """Test case for get_presigned_urls

    Get Presigned Urls
    """
    presigned_url_body = {"parts": 2, "object_name": "ObjectName"}

    headers = {
        "Authorization": "Bearer special-key",
    }
    # uncomment below to make a request
    response = client.request(
        "POST",
        "/s3/presignedUrls",
        headers=headers,
        json=presigned_url_body,
    )

    # uncomment below to assert the status code of the HTTP response
    assert response.status_code == 201


async def mock_mark_dataset_as_archivable(*args, **kwargs) -> None:
    pass


@patch("openapi_server.impl.s3upload_impl.mark_dataset_as_archivable", mock_mark_dataset_as_archivable)
@patch("openapi_server.security_api.validate_token", mock_validate_token)
def test_finalize_dataset_upload(client: TestClient):
    """Test case for get_presigned_urls

    Get Presigned Urls
    """
    finalize_upload_body = {
        "dataset_pid": "dataset/id",
        "create_archiving_job": False,
        "owner_group": "group",
        "owner_user": "user",
        "contact_email": "user@mail.com"
    }

    headers = {
        "Authorization": "Bearer special-key",
    }
    # uncomment below to make a request
    response = client.request(
        "POST",
        "/s3/finalizeDatasetUpload",
        headers=headers,
        json=finalize_upload_body,
    )

    # uncomment below to assert the status code of the HTTP response
    assert response.status_code == 201
