from typing import List

from openapi_server.models.create_service_token_resp import CreateServiceTokenResp

from openapi_server.apis.service_token_api_base import BaseServiceTokenApi
from openapi_server.settings import Settings
from openapi_server.security_api import generate_token

from logging import getLogger

_LOGGER = getLogger("api.service_token")

_SETTINGS = Settings()


class BaseServiceTokenImpl(BaseServiceTokenApi):
    async def create_new_service_token(self) -> CreateServiceTokenResp:
        return generate_token()
