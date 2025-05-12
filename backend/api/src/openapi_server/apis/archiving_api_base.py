# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from openapi_server.models.create_job_body import CreateJobBody
from openapi_server.models.create_job_resp import CreateJobResp
from openapi_server.models.http_validation_error import HTTPValidationError
from openapi_server.models.internal_error import InternalError
from openapi_server.security_api import get_token_BasicAuth

class BaseArchivingApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseArchivingApi.subclasses = BaseArchivingApi.subclasses + (cls,)
    async def create_job(
        self,
        create_job_body: CreateJobBody,
    ) -> CreateJobResp:
        ...
