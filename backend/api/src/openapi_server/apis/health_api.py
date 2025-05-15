# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from openapi_server.apis.health_api_base import BaseHealthApi
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
from openapi_server.models.health_livez_get200_response import HealthLivezGet200Response
from openapi_server.models.health_livez_get503_response import HealthLivezGet503Response
from openapi_server.models.health_readyz_get200_response import HealthReadyzGet200Response
from openapi_server.models.health_readyz_get503_response import HealthReadyzGet503Response


router = APIRouter()

ns_pkg = openapi_server.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/health/livez",
    responses={
        200: {"model": HealthLivezGet200Response, "description": "Service is healthy"},
        503: {"model": HealthLivezGet503Response, "description": "Service is unavailable"},
    },
    tags=["health"],
    summary="Health Check",
    response_model_by_alias=True,
)
async def health_livez_get(
) -> HealthLivezGet200Response:
    """Returns the health status of the service"""
    if not BaseHealthApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseHealthApi.subclasses[0]().health_livez_get()


@router.get(
    "/health/readyz",
    responses={
        200: {"model": HealthReadyzGet200Response, "description": "Service is ready"},
        503: {"model": HealthReadyzGet503Response, "description": "Service is not ready"},
    },
    tags=["health"],
    summary="Readiness Check",
    response_model_by_alias=True,
)
async def health_readyz_get(
) -> HealthReadyzGet200Response:
    """Returns the Readiness status of the service"""
    if not BaseHealthApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseHealthApi.subclasses[0]().health_readyz_get()
