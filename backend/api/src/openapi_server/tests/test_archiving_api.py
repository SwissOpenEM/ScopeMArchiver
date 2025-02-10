# coding: utf-8

from fastapi.testclient import TestClient


from pydantic import StrictInt, StrictStr  # noqa: F401
from typing import Any, List, Optional  # noqa: F401
from openapi_server.models.http_validation_error import HTTPValidationError  # noqa: F401
from openapi_server.models.storage_object import StorageObject  # noqa: F401


def test_create_new_dataset_new_dataset_post(client: TestClient):
    """Test case for create_new_dataset_new_dataset_post

    Create New Dataset
    """
    params = [("file_size_mb", 10), ("num_files", 10), ("datablock_size_mb", 20)]
    headers = {}
    # uncomment below to make a request
    # response = client.request(
    #    "POST",
    #    "/new_dataset/",
    #    headers=headers,
    #    params=params,
    # )

    # uncomment below to assert the status code of the HTTP response
    # assert response.status_code == 200


def test_get_archivable_objects_archivable_objects_get(client: TestClient):
    """Test case for get_archivable_objects_archivable_objects_get

    Get Archivable Objects
    """

    headers = {}
    # uncomment below to make a request
    # response = client.request(
    #    "GET",
    #    "/archivable_objects",
    #    headers=headers,
    # )

    # uncomment below to assert the status code of the HTTP response
    # assert response.status_code == 200


def test_get_retrievable_objects_retrievable_objects_get(client: TestClient):
    """Test case for get_retrievable_objects_retrievable_objects_get

    Get Retrievable Objects
    """

    headers = {}
    # uncomment below to make a request
    # response = client.request(
    #    "GET",
    #    "/retrievable_objects",
    #    headers=headers,
    # )

    # uncomment below to assert the status code of the HTTP response
    # assert response.status_code == 200


def test_job_created_jobs_post(client: TestClient):
    """Test case for job_created_jobs_post

    Job Created
    """
    body = None

    headers = {
        "storage_volume": "storage_volume_example",
    }
    # uncomment below to make a request
    # response = client.request(
    #    "POST",
    #    "/jobs/",
    #    headers=headers,
    #    json=body,
    # )

    # uncomment below to assert the status code of the HTTP response
    # assert response.status_code == 200
