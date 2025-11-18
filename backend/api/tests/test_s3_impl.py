
import pytest
from openapi_server.impl.s3 import request_upload
from unittest.mock import patch, MagicMock


async def mock_get_s3_client(*args, **kwargs):
    return None


async def mock_get_minio_admin_client(*args, **kwargs):
    return None


def mock_get_usage_info(*args, **kwargs):
    return {'objectsTotalSize': 100}


def mock_get_bucket_names(*args, **kwargs):
    return ['bucket-1', 'bucket-2']


def mock_get_bucket_quota(*args, **kwargs):
    return None


def mock_get_total_quota(*args, **kwargs):
    return 700


def create_bucket(*args, **kwargs):
    pass


def set_bucket_quota(*args, **kwargs):
    pass


@patch("openapi_server.impl.s3.get_s3_client", mock_get_s3_client)
@patch("openapi_server.impl.s3.get_minio_admin_client", mock_get_minio_admin_client)
@patch("openapi_server.impl.s3.get_usage_info", mock_get_usage_info)
@patch("openapi_server.impl.s3.get_bucket_names", mock_get_bucket_names)
@patch("openapi_server.impl.s3.get_bucket_quota", mock_get_bucket_quota)
@patch("openapi_server.impl.s3.get_total_quota", mock_get_total_quota)
@patch("openapi_server.impl.s3.create_bucket")
@patch("openapi_server.impl.s3.set_bucket_quota")
@pytest.mark.asyncio
async def test_request_upload(create_bucket: MagicMock, set_bucket_quota: MagicMock):
    # More than 10% left
    dataset_pid = "test/11.22.33"
    dataset_size_gb = 100

    resp = await request_upload(dataset_pid, dataset_size_gb)

    assert resp.ok is True

    create_bucket.assert_called_once()
    set_bucket_quota.assert_called_once()

    # Less than 10% left
    dataset_pid = "test/11.22.33"
    dataset_size_gb = 200

    resp = await request_upload(dataset_pid, dataset_size_gb)

    assert resp.ok is False

    create_bucket.assert_called_once()
    set_bucket_quota.assert_called_once()
