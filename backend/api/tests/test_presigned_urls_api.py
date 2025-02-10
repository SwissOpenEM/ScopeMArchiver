# coding: utf-8

from fastapi.testclient import TestClient


from typing import Any  # noqa: F401
from openapi_server.models.abort_upload_body import AbortUploadBody  # noqa: F401
from openapi_server.models.complete_upload_body import CompleteUploadBody  # noqa: F401
from openapi_server.models.complete_upload_resp import CompleteUploadResp  # noqa: F401
from openapi_server.models.http_validation_error import HTTPValidationError  # noqa: F401
from openapi_server.models.internal_error import InternalError  # noqa: F401
from openapi_server.models.presigned_url_body import PresignedUrlBody  # noqa: F401
from openapi_server.models.presigned_url_resp import PresignedUrlResp  # noqa: F401


def test_abort_multipart_upload(client: TestClient):
    """Test case for abort_multipart_upload

    Abort Multipart Upload
    """
    abort_upload_body = {"upload_id": "UploadID", "object_name": "ObjectName"}

    headers = {}
    # uncomment below to make a request
    # response = client.request(
    #    "POST",
    #    "/abortMultipartUpload",
    #    headers=headers,
    #    json=abort_upload_body,
    # )

    # uncomment below to assert the status code of the HTTP response
    # assert response.status_code == 200


def test_complete_upload(client: TestClient):
    """Test case for complete_upload

    Complete Upload
    """
    complete_upload_body = {
        "parts": [
            {"part_number": 0, "e_tag": "ETag", "checksum_sha256": "ChecksumSHA256"},
            {"part_number": 0, "e_tag": "ETag", "checksum_sha256": "ChecksumSHA256"},
        ],
        "upload_id": "UploadID",
        "object_name": "ObjectName",
        "checksum_sha256": "ChecksumSHA256",
    }

    headers = {}
    # uncomment below to make a request
    # response = client.request(
    #    "POST",
    #    "/completeUpload",
    #    headers=headers,
    #    json=complete_upload_body,
    # )

    # uncomment below to assert the status code of the HTTP response
    # assert response.status_code == 200


def test_get_presigned_urls(client: TestClient):
    """Test case for get_presigned_urls

    Get Presigned Urls
    """
    presigned_url_body = {"parts": 0, "object_name": "ObjectName"}

    headers = {}
    # uncomment below to make a request
    # response = client.request(
    #    "POST",
    #    "/presignedUrls",
    #    headers=headers,
    #    json=presigned_url_body,
    # )

    # uncomment below to assert the status code of the HTTP response
    # assert response.status_code == 200
