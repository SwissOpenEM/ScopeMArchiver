# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from openapi_server.models.create_service_token_resp import CreateServiceTokenResp
from openapi_server.models.http_validation_error import HTTPValidationError
from openapi_server.models.internal_error import InternalError
from openapi_server.security_api import get_token_SciCatAuth

class BaseServiceTokenApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseServiceTokenApi.subclasses = BaseServiceTokenApi.subclasses + (cls,)
    async def create_new_service_token(
        self,
    ) -> CreateServiceTokenResp:
        ...
