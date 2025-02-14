# coding: utf-8

"""Archiver Service API

Main routine that starts the FastAPI server.
"""

from importlib.metadata import version
import pathlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from openapi_server.apis.archiving_api import router as ArchivingApiRouter
from openapi_server.apis.presigned_urls_api import router as PresignedUrlsApiRouter
from openapi_server.apis.service_token_api import router as ServiceTokenRouter
from openapi_server.security_api import generate_token
from starlette.middleware.base import BaseHTTPMiddleware

from .settings import Settings
from logging import getLogger

__version__ = version("archiver-service")

_LOGGER = getLogger("api")

app = FastAPI(
    title="ETHZ Archiver Service",
    description="REST API endpoint provider for presigned S3 upload and archiving workflow scheduling",
    version=__version__,
)

settings = Settings()


class Enforce201Middleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Ensure POST /token returns 201
        if request.method == "POST" and response.status_code == 200:
            response.status_code = 201

        return response


if __name__ == "__main__":
    _LOGGER.setLevel(settings.UVICORN_LOG_LEVEL.upper())
    _LOGGER.info(f"Version: {__version__}")

    origins = [
        "http://127.0.0.1*",
        "http://localhost:5173",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(Enforce201Middleware)

    app.include_router(ArchivingApiRouter)
    app.include_router(PresignedUrlsApiRouter)
    app.include_router(ServiceTokenRouter)

    uvi_config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=settings.UVICORN_PORT,
        root_path=settings.UVICORN_ROOT_PATH,
        reload=settings.UVICORN_RELOAD,
        log_level=settings.UVICORN_LOG_LEVEL,
        reload_dirs=[str(pathlib.Path(__file__).parent)],
    )

    # TODO: for testing purposes only. To be removed later.
    token = generate_token()
    if token:
        _LOGGER.info(f"Test Bearer token: {token.get('access_token', 'No access_token found')}")

    server = uvicorn.Server(uvi_config)
    server.run()
