from fastapi.responses import JSONResponse
from uuid import UUID

from openapi_server.apis.archiving_api_base import BaseArchivingApi
from openapi_server.models.create_job_body import CreateJobBody
from openapi_server.models.create_job_resp import CreateJobResp

from .archiving import run_archiving_deployment, run_retrieval_deployment

from logging import getLogger

_LOGGER = getLogger("uvicorn.archiving")


class BaseArchivingApiImpl(BaseArchivingApi):
    async def create_job(
        self,
        create_job_body: CreateJobBody,
    ) -> CreateJobResp:
        try:
            job_id = UUID(str(create_job_body.id))
        except ValueError as e:
            _LOGGER.warning(e)
            return JSONResponse(
                status_code=422, content={"message": "Failed to create job", "details": str(e)}
            )

        try:
            match create_job_body.type:
                case "archive":
                    flowRun = await run_archiving_deployment(job_id=job_id)
                case "retrieve":
                    flowRun = await run_retrieval_deployment(job_id=job_id)
                case "publish":
                    # a publish job is exactly the same as a retrieval
                    flowRun = await run_retrieval_deployment(job_id=job_id)
                case _:
                    return JSONResponse(status_code=500, content={"message": f"unknown job type {type}"})

            _LOGGER.debug(
                "Flow run for job %s created. Id=%d Name=%s", create_job_body.id, flowRun.id, flowRun.name
            )
            return CreateJobResp(Uuid=str(flowRun.id), Name=flowRun.name)
        except Exception as e:
            _LOGGER.error(e)
            return JSONResponse(
                status_code=500, content={"message": "Failed to create job", "details": str(e)}
            )
