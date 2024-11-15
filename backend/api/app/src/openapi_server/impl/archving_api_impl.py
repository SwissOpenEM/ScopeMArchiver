
import base64
from typing import Any, List, Optional

from fastapi import Body, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from pydantic import StrictInt, StrictStr

from openapi_server.apis.archiving_api_base import BaseArchivingApi
from openapi_server.models.create_dataset_body import CreateDatasetBody
from openapi_server.models.create_dataset_resp import CreateDatasetResp
from openapi_server.models.create_job_body import CreateJobBody
from openapi_server.models.create_job_resp import CreateJobResp

from .archiving import run_create_dataset_deployment, run_archiving_deployment, run_retrieval_deployment


class BaseArchivingApiImpl(BaseArchivingApi):

    async def create_new_dataset(
        self,
        create_dataset_body: CreateDatasetBody,
    ) -> CreateDatasetResp:
        try:
            import random
            data_set_id = create_dataset_body.data_set_id or str(random.randint(0, 10000))
            m = await run_create_dataset_deployment(file_size_MB=create_dataset_body.file_size_in_mb,
                                                    num_files=create_dataset_body.number_of_files,
                                                    datablock_size_MB=create_dataset_body.datablock_size_in_mb,
                                                    dataset_id=create_dataset_body.data_set_id)

            return CreateDatasetResp(Name=m.name, Uuid=m.id, DataSetId=data_set_id)
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    async def create_job(
        create_job_body: CreateJobBody,
    ) -> CreateJobResp:
        try:
            match create_job_body.type:
                case "archive":
                    m = await run_archiving_deployment(job_id=id, dataset_list=[])
                case "retrieve":
                    m = await run_retrieval_deployment(job_id=id, dataset_list=[])
                case _:
                    return JSONResponse(content={"error": f"unknown job type {type}"}, status_code=500)

            return CreateJobResp(Uuid=m.id, Name=m.name)
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)
            pass
