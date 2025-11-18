# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from openapi_server.apis.s3upload_api_base import BaseS3uploadApi
import openapi_server.impl

from fastapi import (  # noqa: F401
    APIRouter,
    Body,
    Cookie,
    Depends,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    Response,
    Security,
    status,
)

from openapi_server.models.extra_models import TokenModel  # noqa: F401
from openapi_server.models.abort_dataset_upload_body import AbortDatasetUploadBody
from openapi_server.models.abort_dataset_upload_resp import AbortDatasetUploadResp
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
from openapi_server.models.upload_request_successful_resp import UploadRequestSuccessfulResp
from openapi_server.models.upload_request_unsuccessful_resp import UploadRequestUnsuccessfulResp
from openapi_server.security_api import get_token_BearerAuth

router = APIRouter()

ns_pkg = openapi_server.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.post(
    "/s3/abortDatasetUpload",
    responses={
        201: {"model": AbortDatasetUploadResp, "description": "Finalize dataset upload requested"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
        500: {"model": InternalError, "description": "Internal Server Error"},
    },
    tags=["s3upload"],
    summary="Abort Dataset Upload",
    response_model_by_alias=True,
)
async def abort_dataset_upload(
    abort_dataset_upload_body: AbortDatasetUploadBody = Body(None, description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> AbortDatasetUploadResp:
    if not BaseS3uploadApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseS3uploadApi.subclasses[0]().abort_dataset_upload(abort_dataset_upload_body)


@router.post(
    "/s3/abortMultipartUpload",
    responses={
        201: {"model": AbortUploadResp, "description": "Abort multipart upload requested"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
        500: {"model": InternalError, "description": "Internal Server Error"},
    },
    tags=["s3upload"],
    summary="Abort Multipart Upload",
    response_model_by_alias=True,
)
async def abort_multipart_upload(
    abort_upload_body: AbortUploadBody = Body(None, description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> AbortUploadResp:
    if not BaseS3uploadApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseS3uploadApi.subclasses[0]().abort_multipart_upload(abort_upload_body)


@router.post(
    "/s3/completeUpload",
    responses={
        201: {"model": CompleteUploadResp, "description": "Upload completed"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
        500: {"model": InternalError, "description": "Internal Server Error"},
    },
    tags=["s3upload"],
    summary="Complete Upload",
    response_model_by_alias=True,
)
async def complete_upload(
    complete_upload_body: CompleteUploadBody = Body(None, description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> CompleteUploadResp:
    if not BaseS3uploadApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseS3uploadApi.subclasses[0]().complete_upload(complete_upload_body)


@router.post(
    "/s3/finalizeDatasetUpload",
    responses={
        201: {"model": FinalizeDatasetUploadResp, "description": "Finalize dataset upload requested"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
        500: {"model": InternalError, "description": "Internal Server Error"},
    },
    tags=["s3upload"],
    summary="Finalize Dataset Upload",
    response_model_by_alias=True,
)
async def finalize_dataset_upload(
    finalize_dataset_upload_body: FinalizeDatasetUploadBody = Body(None, description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> FinalizeDatasetUploadResp:
    if not BaseS3uploadApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseS3uploadApi.subclasses[0]().finalize_dataset_upload(finalize_dataset_upload_body)


@router.post(
    "/s3/presignedUrls",
    responses={
        201: {"model": PresignedUrlResp, "description": "Presigned URLs created"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
        500: {"model": InternalError, "description": "Internal Server Error"},
    },
    tags=["s3upload"],
    summary="Get Presigned urls",
    response_model_by_alias=True,
)
async def get_presigned_urls(
    presigned_url_body: PresignedUrlBody = Body(None, description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> PresignedUrlResp:
    if not BaseS3uploadApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseS3uploadApi.subclasses[0]().get_presigned_urls(presigned_url_body)


@router.post(
    "/s3/requestDatasetUpload",
    responses={
        201: {"model": UploadRequestSuccessfulResp, "description": "Upload request successful"},
        507: {"model": UploadRequestUnsuccessfulResp, "description": "Upload request unsuccessful"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
        500: {"model": InternalError, "description": "Internal Server Error"},
    },
    tags=["s3upload"],
    summary="Request a new upload",
    response_model_by_alias=True,
)
async def request_dataset_upload(
    upload_request_body: UploadRequestBody = Body(None, description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> UploadRequestSuccessfulResp:
    if not BaseS3uploadApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseS3uploadApi.subclasses[0]().request_dataset_upload(upload_request_body)
