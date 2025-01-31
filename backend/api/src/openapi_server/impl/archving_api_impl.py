import base64
from typing import Any, List, Optional

from fastapi import Body, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from pydantic import StrictInt, StrictStr
from uuid import UUID

from openapi_server.apis.archiving_api_base import BaseArchivingApi
from openapi_server.models.create_dataset_body import CreateDatasetBody
from openapi_server.models.create_dataset_resp import CreateDatasetResp
from openapi_server.models.create_job_body import CreateJobBody
from openapi_server.models.create_job_resp import CreateJobResp
from openapi_server.models.internal_error import InternalError

from .archiving import run_create_dataset_deployment, run_archiving_deployment, run_retrieval_deployment

from logging import getLogger

_LOGGER = getLogger("api.archiving")


class BaseArchivingApiImpl(BaseArchivingApi):
    async def create_new_dataset(
        self,
        create_dataset_body: CreateDatasetBody,
    ) -> CreateDatasetResp:
        try:
            import random

            data_set_id = create_dataset_body.data_set_id or str(random.randint(0, 10000))
            flowRun = await run_create_dataset_deployment(
                file_size_MB=create_dataset_body.file_size_in_mb,
                num_files=create_dataset_body.number_of_files,
                datablock_size_MB=create_dataset_body.datablock_size_in_mb,
                dataset_id=data_set_id,
            )

            _LOGGER.debug("Flow run for dataset % created. Id=%d Name=%s", data_set_id, flowRun.id, flowRun.name)
            return CreateDatasetResp(Name=flowRun.name, Uuid=str(flowRun.id), DataSetId=data_set_id)
        except Exception as e:
            _LOGGER.error(e)
            return JSONResponse(status_code=500, content={"message": "Failed to create new dataset", "details": str(e)})

    async def create_job(
        self,
        create_job_body: CreateJobBody,
    ) -> CreateJobResp:
        try:
            job_id = UUID(create_job_body.id)
        except ValueError as e:
            _LOGGER.warning(e)
            return JSONResponse(status_code=422, content={"message": "Failed to create job", "details": str(e)})

        try:
            match create_job_body.type:
                case "archive":
                    flowRun = await run_archiving_deployment(job_id=job_id, dataset_list=[])
                case "retrieve":
                    flowRun = await run_retrieval_deployment(job_id=job_id, dataset_list=[])
                case _:
                    return JSONResponse(status_code=500, content={"message": f"unknown job type {type}"})

            _LOGGER.debug("Flow run for job %s created. Id=%d Name=%s", create_job_body.id, flowRun.id, flowRun.name)
            return CreateJobResp(Uuid=str(flowRun.id), Name=flowRun.name)
        except Exception as e:
            _LOGGER.error(e)
            return JSONResponse(status_code=500, content={"message": "Failed to create job", "details": str(e)})
