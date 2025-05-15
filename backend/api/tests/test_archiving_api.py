# coding: utf-8
from fastapi.testclient import TestClient


from openapi_server.models.create_job_body import CreateJobBody  # noqa: F401
from openapi_server.models.create_job_resp import CreateJobResp  # noqa: F401
from openapi_server.models.http_validation_error import HTTPValidationError  # noqa: F401
from openapi_server.models.internal_error import InternalError  # noqa: F401

from prefect.client.schemas.objects import FlowRun  # noqa: F401
from prefect import flow  # noqa: F401 # required do to https://github.com/PrefectHQ/prefect/issues/16105

from unittest.mock import patch
import uuid


async def mock_run_archiving_deployment(*args, **kwargs) -> FlowRun:
    return FlowRun(flow_id=uuid.UUID("046b6c7f-0b8a-43b9-b35d-6489e6daee92"), name="flowrun")


@patch("openapi_server.impl.archiving_api_impl.run_archiving_deployment", mock_run_archiving_deployment)
def test_create_job(client: TestClient):
    """Test case for create_job

    Job Created
    """
    create_job_body = {"type": "archive", "id": "046b6c7f-0b8a-43b9-b35d-6489e6daee91"}

    headers = {
        "Authorization": "Basic dXNlcm5hbWU6cHc=",
    }

    response = client.request(
        "POST",
        "/archiver/jobs/",
        headers=headers,
        json=create_job_body,
    )

    assert response.status_code == 201
