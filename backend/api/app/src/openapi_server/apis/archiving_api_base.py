# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from openapi_server.models.create_dataset_body import CreateDatasetBody
from openapi_server.models.create_dataset_resp import CreateDatasetResp
from openapi_server.models.create_job_body import CreateJobBody
from openapi_server.models.create_job_resp import CreateJobResp
from openapi_server.models.http_validation_error import HTTPValidationError


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


    async def create_new_dataset(
        self,
        create_dataset_body: CreateDatasetBody,
    ) -> CreateDatasetResp:
        ...
