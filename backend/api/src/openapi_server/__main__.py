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
from openapi_server.apis.s3upload_api import router as S3UploadApiRouter
from openapi_server.apis.service_token_api import router as ServiceTokenRouter
from openapi_server.apis.health_api import router as HealthApiRouter
from starlette.middleware.base import BaseHTTPMiddleware

from .settings import GetSettings
from logging import getLogger

__version__ = version("archiver-service-api")


app = FastAPI(
    title="ETHZ Archiver Service",
    description="REST API endpoint provider for presigned S3 upload and archiving workflow scheduling",
    version=__version__,
)

_LOGGER = getLogger("uvicorn")


class Enforce201Middleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Ensure POST /token returns 201
        if request.method == "POST" and response.status_code == 200:
            response.status_code = 201

        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title="ETHZ Archiver Service",
        description="REST API endpoint provider for presigned S3 upload and archiving workflow scheduling",
        version=__version__,
    )
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
    app.include_router(S3UploadApiRouter)
    app.include_router(ServiceTokenRouter)
    app.include_router(HealthApiRouter)

    return app


app = create_app()

if __name__ == "__main__":
    settings = GetSettings()

    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["loggers"]["uvicorn"]["level"] = settings.UVICORN_LOG_LEVEL.upper()
    uvi_config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=settings.UVICORN_PORT,
        root_path=settings.UVICORN_ROOT_PATH,
        reload=settings.UVICORN_RELOAD,
        log_config=log_config,
        reload_dirs=[str(pathlib.Path(__file__).parent)],
    )

    _LOGGER.info(f"Version: {__version__}")

    server = uvicorn.Server(uvi_config)
    server.run()
