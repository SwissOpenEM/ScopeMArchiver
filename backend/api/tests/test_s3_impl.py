
import pytest
from openapi_server.impl.s3 import request_upload
from unittest.mock import patch

LANDING_ZONE = "dev.landingzone"


async def mock_get_landingzone_bucket():
    return LANDING_ZONE


async def mock_fetch_metrics():
    landingzone = await mock_get_landingzone_bucket()
    metric_quota = {"labels": {"bucket": landingzone}}
    metric_quota["value"] = 1000 * 1024**3

    metric_usage = dict()
    metric_usage = {"labels": {"bucket": landingzone}}
    metric_usage["value"] = 700 * 1024**3

    return [metric_quota], [metric_usage]


@patch("openapi_server.impl.s3.get_landingzone_bucket", mock_get_landingzone_bucket)
@patch("openapi_server.impl.s3.fetch_metrics", mock_fetch_metrics)
@pytest.mark.asyncio
async def test_request_upload():
    # More than 10% left
    dataset_pid = "test/11.22.33"
    dataset_size_gb = 100

    resp = await request_upload(dataset_pid, dataset_size_gb)

    assert resp.ok is True

    # Less than 10% left
    dataset_pid = "test/11.22.33"
    dataset_size_gb = 200

    resp = await request_upload(dataset_pid, dataset_size_gb)

    assert resp.ok is False
