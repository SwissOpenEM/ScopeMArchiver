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
from openapi_server.models.create_dataset_body import CreateDatasetBody
from openapi_server.models.create_dataset_resp import CreateDatasetResp
from openapi_server.models.create_job_body import CreateJobBody
from openapi_server.models.create_job_resp import CreateJobResp
from openapi_server.models.http_validation_error import HTTPValidationError


router = APIRouter()

ns_pkg = openapi_server.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.post(
    "/jobs/",
    responses={
        200: {"model": CreateJobResp, "description": "Successful Response"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
    },
    tags=["archiving"],
    summary="Job Created",
    response_model_by_alias=True,
)
async def create_job(
    create_job_body: CreateJobBody = Body(None, description=""),
) -> CreateJobResp:
    if not BaseArchivingApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseArchivingApi.subclasses[0]().create_job(create_job_body)


@router.post(
    "/new_dataset/",
    responses={
        200: {"model": CreateDatasetResp, "description": "Successful Response"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
    },
    tags=["archiving"],
    summary="Create New Dataset",
    response_model_by_alias=True,
)
async def create_new_dataset(
    create_dataset_body: CreateDatasetBody = Body(None, description=""),
) -> CreateDatasetResp:
    if not BaseArchivingApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseArchivingApi.subclasses[0]().create_new_dataset(create_dataset_body)
