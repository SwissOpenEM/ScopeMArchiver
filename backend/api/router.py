from uuid import UUID
import asyncio
from fastapi import APIRouter, Body, Header
from typing import Any, List, Annotated
from fastapi.responses import JSONResponse
from prefect.deployments.deployments import run_deployment

from archiver.utils.working_storage_interface import S3Storage, Bucket
from archiver.utils.model import StorageObject

router = APIRouter()


def create_job_variables(header: str | None):
    volume_map = {
        "test-lts-share": "scopemarchiver_nfs-lts-share",
        "prod-lts-share": "scopemarchiver_nfs-lts-share",
        "mock-lts-share": "lts-mock-volume"
    }
    mapped_volume = volume_map.get(header or "", "lts-mock-volume")
    return {
        "volumes": [
            f"{mapped_volume}:/tmp/LTS"
        ]
    }


async def run_archiving_deployment(job_id: UUID, dataset_list: List[str], storage_volume: str | None):
    job_variables = create_job_variables(storage_volume)

    a = await asyncio.create_task(run_deployment("archive_datasetlist/datasets_archival",
                                                 parameters={
                                                     "dataset_ids": dataset_list,
                                                     "job_id": job_id
                                                 },
                                                 job_variables=job_variables,
                                                 timeout=0))
    return a


async def run_retrieval_deployment(job_id: UUID, dataset_list: List[str], storage_volume: str | None):
    job_variables = create_job_variables(storage_volume)
    a = await asyncio.create_task(run_deployment("retrieve_datasetlist/datasets_retrieval",
                                                 parameters={
                                                     "dataset_ids": dataset_list,
                                                     "job_id": job_id
                                                 }, job_variables=job_variables,
                                                 timeout=0))
    return a


async def run_create_dataset_deployment(
        file_size_MB: int = 10, num_files: int = 10, datablock_size_MB: int = 20, dataset_id: str | None = None):
    a = await asyncio.create_task(run_deployment("create_test_dataset/dataset_creation", parameters={
        "num_files": num_files,
        "file_size_MB": file_size_MB,
        "datablock_size_MB": datablock_size_MB,
        "dataset_id": dataset_id
    }, timeout=0))
    return a


@ router.get("/archivable_objects")
def get_archivable_objects() -> list[StorageObject]:
    objects = S3Storage().list_objects(bucket=Bucket.staging_bucket())
    return [StorageObject(object_name=o.object_name or "") for o in objects]


@ router.get("/retrievable_objects")
def get_retrievable_objects() -> list[StorageObject]:
    objects = S3Storage().list_objects(bucket=Bucket.retrieval_bucket())
    return [StorageObject(object_name=o.object_name or "") for o in objects]


@ router.post("/new_dataset/")
async def create_new_dataset():
    try:
        import random
        dataset_id = str(random.randint(0, 10000))
        m = await run_create_dataset_deployment(file_size_MB=10, num_files=10, datablock_size_MB=20, dataset_id=dataset_id)
        return JSONResponse(content={"name": m.name, "uuid": str(m.id), "dataset_id": dataset_id}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def create_job(payload: Any, storage_volume: str | None):

    try:
        print(payload)
        payload = payload.decode('ASCII')
        print(payload)
        import json
        payload = json.loads(payload)
        id = payload["id"]
        type = payload["type"]
        match type:
            case "archive":
                m = await run_archiving_deployment(job_id=id, dataset_list=[], storage_volume=storage_volume)
            case "retrieve":
                m = await run_retrieval_deployment(job_id=id, dataset_list=[], storage_volume=storage_volume)
            case _:
                return JSONResponse(content={"error": f"unknown job type {type}"}, status_code=500)

        return JSONResponse(content={"name": m.name, "uuid": str(m.id)}, status_code=200)
    except Exception as e:
        print(e)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@ router.post("/jobs/")
async def job_created(payload: Any = Body(None), storage_volume: Annotated[str | None, Header()] = None):

    return await create_job(payload=payload, storage_volume=storage_volume)
