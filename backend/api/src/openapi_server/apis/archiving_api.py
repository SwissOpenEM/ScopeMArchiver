# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from openapi_server.apis.archiving_api_base import BaseArchivingApi
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
from openapi_server.models.create_job_body import CreateJobBody
from openapi_server.models.create_job_resp import CreateJobResp
from openapi_server.models.http_validation_error import HTTPValidationError
from openapi_server.models.internal_error import InternalError
from openapi_server.security_api import get_token_BasicAuth

router = APIRouter()

ns_pkg = openapi_server.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.post(
    "/archiver/jobs",
    responses={
        201: {"model": CreateJobResp, "description": "Job Created"},
        422: {"model": HTTPValidationError, "description": "Data Validation Error"},
        500: {"model": InternalError, "description": "Internal Server Error"},
    },
    tags=["archiving"],
    summary="Create Archiver Job",
    response_model_by_alias=True,
)
async def create_job(
    create_job_body: CreateJobBody = Body(None, description=""),
    token_BasicAuth: TokenModel = Security(
        get_token_BasicAuth
    ),
) -> CreateJobResp:
    if not BaseArchivingApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseArchivingApi.subclasses[0]().create_job(create_job_body)
