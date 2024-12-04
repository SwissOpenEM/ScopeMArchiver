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
from typing import Any
from openapi_server.models.abort_upload_body import AbortUploadBody
from openapi_server.models.complete_upload_body import CompleteUploadBody
from openapi_server.models.complete_upload_resp import CompleteUploadResp
from openapi_server.models.http_validation_error import HTTPValidationError
from openapi_server.models.presigned_url_body import PresignedUrlBody
from openapi_server.models.presigned_url_resp import PresignedUrlResp


router = APIRouter()

ns_pkg = openapi_server.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.post(
    "/abortMultipartUpload",
    responses={
        200: {"model": object, "description": "Successful Response"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
    },
    tags=["presignedUrls"],
    summary="Abort Multipart Upload",
    response_model_by_alias=True,
)
async def abort_multipart_upload(
    abort_upload_body: AbortUploadBody = Body(None, description=""),
) -> object:
    if not BasePresignedUrlsApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePresignedUrlsApi.subclasses[0]().abort_multipart_upload(abort_upload_body)


@router.post(
    "/completeUpload",
    responses={
        200: {"model": CompleteUploadResp, "description": "Successful Response"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
    },
    tags=["presignedUrls"],
    summary="Complete Upload",
    response_model_by_alias=True,
)
async def complete_upload(
    complete_upload_body: CompleteUploadBody = Body(None, description=""),
) -> CompleteUploadResp:
    if not BasePresignedUrlsApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePresignedUrlsApi.subclasses[0]().complete_upload(complete_upload_body)


@router.post(
    "/presignedUrls",
    responses={
        200: {"model": PresignedUrlResp, "description": "Successful Response"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
    },
    tags=["presignedUrls"],
    summary="Get Presigned Urls",
    response_model_by_alias=True,
)
async def get_presigned_urls(
    presigned_url_body: PresignedUrlBody = Body(None, description=""),
) -> PresignedUrlResp:
    if not BasePresignedUrlsApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePresignedUrlsApi.subclasses[0]().get_presigned_urls(presigned_url_body)
