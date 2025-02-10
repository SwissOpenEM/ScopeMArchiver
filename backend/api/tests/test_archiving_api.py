# coding: utf-8

from fastapi.testclient import TestClient


from openapi_server.models.create_dataset_body import CreateDatasetBody  # noqa: F401
from openapi_server.models.create_dataset_resp import CreateDatasetResp  # noqa: F401
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


def test_create_new_dataset(client: TestClient):
    """Test case for create_new_dataset

    Create New Dataset
    """
    create_dataset_body = {"file_size_in_mb": 40, "number_of_files": 20, "datablock_size_in_mb": 400}

    headers = {}
    # uncomment below to make a request
    # response = client.request(
    #    "POST",
    #    "/new_dataset/",
    #    headers=headers,
    #    json=create_dataset_body,
    # )

    # uncomment below to assert the status code of the HTTP response
    # assert response.status_code == 200
