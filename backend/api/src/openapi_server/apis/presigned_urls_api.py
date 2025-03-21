# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from openapi_server.apis.presigned_urls_api_base import BasePresignedUrlsApi
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
from openapi_server.models.abort_upload_body import AbortUploadBody
from openapi_server.models.abort_upload_resp import AbortUploadResp
from openapi_server.models.complete_upload_body import CompleteUploadBody
from openapi_server.models.complete_upload_resp import CompleteUploadResp
from openapi_server.models.http_validation_error import HTTPValidationError
from openapi_server.models.internal_error import InternalError
from openapi_server.models.presigned_url_body import PresignedUrlBody
from openapi_server.models.presigned_url_resp import PresignedUrlResp
from openapi_server.security_api import get_token_BearerAuth

router = APIRouter()

ns_pkg = openapi_server.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.post(
    "/s3/abortMultipartUpload",
    responses={
        201: {"model": AbortUploadResp, "description": "Abort multipart upload requested"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
        500: {"model": InternalError, "description": "Internal Server Error"},
    },
    tags=["presignedUrls"],
    summary="Abort Multipart Upload",
    response_model_by_alias=True,
)
async def abort_multipart_upload(
    abort_upload_body: AbortUploadBody = Body(None, description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> AbortUploadResp:
    if not BasePresignedUrlsApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePresignedUrlsApi.subclasses[0]().abort_multipart_upload(abort_upload_body)


@router.post(
    "/s3/completeUpload",
    responses={
        201: {"model": CompleteUploadResp, "description": "Upload completed"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
        500: {"model": InternalError, "description": "Internal Server Error"},
    },
    tags=["presignedUrls"],
    summary="Complete Upload",
    response_model_by_alias=True,
)
async def complete_upload(
    complete_upload_body: CompleteUploadBody = Body(None, description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> CompleteUploadResp:
    if not BasePresignedUrlsApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePresignedUrlsApi.subclasses[0]().complete_upload(complete_upload_body)


@router.post(
    "/s3/presignedUrls",
    responses={
        201: {"model": PresignedUrlResp, "description": "Presigned URLs created"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
        500: {"model": InternalError, "description": "Internal Server Error"},
    },
    tags=["presignedUrls"],
    summary="Get Presigned Urls",
    response_model_by_alias=True,
)
async def get_presigned_urls(
    presigned_url_body: PresignedUrlBody = Body(None, description=""),
    token_BearerAuth: TokenModel = Security(
        get_token_BearerAuth
    ),
) -> PresignedUrlResp:
    if not BasePresignedUrlsApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePresignedUrlsApi.subclasses[0]().get_presigned_urls(presigned_url_body)
