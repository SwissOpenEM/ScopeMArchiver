# coding: utf-8

from fastapi.testclient import TestClient


from openapi_server.models.create_service_token_resp import CreateServiceTokenResp  # noqa: F401
from openapi_server.models.http_validation_error import HTTPValidationError  # noqa: F401
from openapi_server.models.internal_error import InternalError  # noqa: F401


def test_create_new_service_token(client: TestClient):
    """Test case for create_new_service_token

    Create New Service Token
    """

    headers = {
        "Authorization": "Bearer special-key",
    }
    # uncomment below to make a request
    # response = client.request(
    #    "POST",
    #    "/token",
    #    headers=headers,
    # )

    # uncomment below to assert the status code of the HTTP response
    # assert response.status_code == 200
