# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from openapi_server.apis.service_token_api_base import BaseServiceTokenApi
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
from openapi_server.models.create_service_token_resp import CreateServiceTokenResp
from openapi_server.models.http_validation_error import HTTPValidationError
from openapi_server.models.internal_error import InternalError
from openapi_server.security_api import get_token_SciCatAuth

router = APIRouter()

ns_pkg = openapi_server.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.post(
    "/token",
    responses={
        201: {"model": CreateServiceTokenResp, "description": "Service Token created"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
        500: {"model": InternalError, "description": "Internal Server Error"},
    },
    tags=["service_token"],
    summary="Create New Service Token",
    response_model_by_alias=True,
)
async def create_new_service_token(
    token_SciCatAuth: TokenModel = Security(
        get_token_SciCatAuth
    ),
) -> CreateServiceTokenResp:
    if not BaseServiceTokenApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseServiceTokenApi.subclasses[0]().create_new_service_token()
