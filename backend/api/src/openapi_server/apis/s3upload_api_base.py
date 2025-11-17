# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from openapi_server.models.abort_upload_body import AbortUploadBody
from openapi_server.models.abort_upload_resp import AbortUploadResp
from openapi_server.models.complete_upload_body import CompleteUploadBody
from openapi_server.models.complete_upload_resp import CompleteUploadResp
from openapi_server.models.finalize_dataset_upload_body import FinalizeDatasetUploadBody
from openapi_server.models.finalize_dataset_upload_resp import FinalizeDatasetUploadResp
from openapi_server.models.http_validation_error import HTTPValidationError
from openapi_server.models.internal_error import InternalError
from openapi_server.models.presigned_url_body import PresignedUrlBody
from openapi_server.models.presigned_url_resp import PresignedUrlResp
from openapi_server.models.upload_request_body import UploadRequestBody
from openapi_server.models.upload_request_resp import UploadRequestResp
from openapi_server.security_api import get_token_BearerAuth

class BaseS3uploadApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseS3uploadApi.subclasses = BaseS3uploadApi.subclasses + (cls,)
    async def abort_multipart_upload(
        self,
        abort_upload_body: AbortUploadBody,
    ) -> AbortUploadResp:
        ...


    async def complete_upload(
        self,
        complete_upload_body: CompleteUploadBody,
    ) -> CompleteUploadResp:
        ...


    async def finalize_dataset_upload(
        self,
        finalize_dataset_upload_body: FinalizeDatasetUploadBody,
    ) -> FinalizeDatasetUploadResp:
        ...


    async def get_presigned_urls(
        self,
        presigned_url_body: PresignedUrlBody,
    ) -> PresignedUrlResp:
        ...


    async def request_dataset_upload(
        self,
        upload_request_body: UploadRequestBody,
    ) -> UploadRequestResp:
        ...
