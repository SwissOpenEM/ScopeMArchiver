
from fastapi.responses import JSONResponse
import pytest
from openapi_server.impl.s3 import request_upload
from unittest.mock import patch, MagicMock

from openapi_server.models.upload_request_successful_resp import UploadRequestSuccessfulResp


async def mock_get_s3_client(*args, **kwargs):
    return None


async def mock_get_minio_admin_client(*args, **kwargs):
    return None


async def mock_get_bucket_names(*args, **kwargs):
    return ['dev.landingzone', 'bucket-2']


async def mock_landingzone_bucket_names(*args, **kwargs):
    return 'dev.landingzone'

@patch("openapi_server.impl.s3.get_s3_client", mock_get_s3_client)
@patch("openapi_server.impl.s3.get_bucket_names", mock_get_bucket_names)
@patch("openapi_server.impl.s3.landingzone_bucket_name", mock_landingzone_bucket_names)
@pytest.mark.asyncio
async def test_request_upload():
    # More than 10% left
    dataset_pid = "test/11.22.33"
    dataset_size_gb = 100

    resp = await request_upload(dataset_pid, dataset_size_gb)

    assert type(resp) is UploadRequestSuccessfulResp

