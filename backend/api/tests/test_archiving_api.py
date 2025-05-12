# coding: utf-8

from fastapi.testclient import TestClient


from openapi_server.models.create_job_body import CreateJobBody  # noqa: F401
from openapi_server.models.create_job_resp import CreateJobResp  # noqa: F401
from openapi_server.models.http_validation_error import HTTPValidationError  # noqa: F401
from openapi_server.models.internal_error import InternalError  # noqa: F401


def test_create_job(client: TestClient):
    """Test case for create_job

    Job Created
    """
    create_job_body = {"type": "archive", "id": "046b6c7f-0b8a-43b9-b35d-6489e6daee91"}

    headers = {}
    # uncomment below to make a request
    # response = client.request(
    #    "POST",
    #    "/jobs/",
    #    headers=headers,
    #    json=create_job_body,
    # )

    # uncomment below to assert the status code of the HTTP response
    # assert response.status_code == 200

