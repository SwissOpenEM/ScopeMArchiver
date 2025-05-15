from datetime import datetime, timezone
from logging import getLogger
from typing import List

from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
from openapi_server.models.health_livez_get200_response import HealthLivezGet200Response

from openapi_server.models.health_readyz_get200_response import HealthReadyzGet200Response

from openapi_server.apis.health_api_base import BaseHealthApi
from openapi_server.settings import GetSettings

_LOGGER = getLogger("uvicorn.health")


class HealthCheck(BaseModel):
    endpoint: str
    description: str
    verbose: bool = False


class HealthCheckError(BaseModel):
    dependency: str
    endpoint: str
    message: str


class HealthCheckErrors(BaseModel):
    errors: List[HealthCheckError] = []
    status: str = "not ready"


def run_healthcheck(check: HealthCheck) -> HealthCheckError | None:
    try:
        response = requests.get(check.endpoint, timeout=5)
        if response.status_code == 200:
            return None
        else:
            return HealthCheckError(
                dependency=check.description, endpoint=check.endpoint, message=str(response.status_code)
            )
    except requests.RequestException as e:
        return HealthCheckError(dependency=check.description, endpoint=check.endpoint, message=str(e))


class BaseDefaultApiImpl(BaseHealthApi):
    def getHealthChecks(self):
        return [
            HealthCheck(
                description="Minio", endpoint=f"https://{GetSettings().MINIO_ENDPOINT}/minio/health/live"
            ),
            HealthCheck(description="Prefect", endpoint=f"{GetSettings().PREFECT_API_URL}/health"),
            HealthCheck(description="Scicat", endpoint=f"{GetSettings().SCICAT_API}/health"),
        ]

    async def health_readyz_get(self):
        errors = HealthCheckErrors()
        for check in self.getHealthChecks():
            error = run_healthcheck(check)
            if error is not None:
                errors.errors.append(error)

        if len(errors.errors) == 0:
            return HealthReadyzGet200Response(
                status="ready", timestamp=datetime.now(timezone.utc).isoformat()
            )
        else:
            return JSONResponse(status_code=503, content=errors.model_dump())

    async def health_livez_get(self):
        return HealthLivezGet200Response(status="healthy", timestamp=datetime.now(timezone.utc).isoformat())
