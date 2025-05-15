# coding: utf-8

from unittest.mock import patch
from fastapi.testclient import TestClient


from openapi_server.models.create_service_token_resp import CreateServiceTokenResp  # noqa: F401
from openapi_server.models.http_validation_error import HTTPValidationError  # noqa: F401
from openapi_server.models.internal_error import InternalError
from utils import mock_validate_token  # noqa: F401


def mock_generate_token(*args, **kwargs) -> CreateServiceTokenResp:
    return CreateServiceTokenResp(
        access_token="046b6c7f-0b8a-43b9-b35d-6489e6daee92",
        refresh_token="046b6c7f-0b8a-43b9-b35d-6489e6daee92"
    )


@patch("openapi_server.impl.service_token_impl.generate_token", mock_generate_token)
@patch("openapi_server.security_api.validate_token", mock_validate_token)
def test_create_new_service_token(client: TestClient):
    """Test case for create_new_service_token

    Create New Service Token
    """

    headers = {
        "Authorization": "Bearer someToken",
    }
    # uncomment below to make a request
    response = client.request(
        "POST",
        "/token",
        headers=headers,
    )

    # uncomment below to assert the status code of the HTTP response
    assert response.status_code == 201
