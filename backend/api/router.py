import asyncio
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from prefect.deployments.deployments import run_deployment

from archiver.utils.working_storage_interface import S3Storage
from archiver.utils.model import StorageObject, Job

router = APIRouter()

# Deployment function


async def run_archiving_deployment(job: Job):
    a = await asyncio.create_task(run_deployment("archive_datasetlist/datasets_archival", parameters={
        "dataset_ids": [d.pid for d in job.datasetList or []],
        "job_id": job.id
    }, timeout=0))
    return a


async def run_retrieval_deployment(job: Job):
    a = await asyncio.create_task(run_deployment("retrieve_datasetlist/dataset_retrieval", parameters={
        "dataset_ids": [d.pid for d in job.datasetList or []],
        "job_id": job.id
    }, timeout=0))
    return a


async def run_create_dataset_deployment(dataset_id: int, file_size_MB: int, num_files: int):
    a = await asyncio.create_task(run_deployment("create_test_dataset/dataset_creation", parameters={
        "dataset_id": dataset_id,
        "file_size_MB": file_size_MB,
        "num_files": num_files
    }, timeout=0))
    return a


@router.get("/archivable_objects")
def get_archivable_objects() -> list[StorageObject]:
    objects = S3Storage().list_objects(bucket=S3Storage().STAGING_BUCKET)
    return [StorageObject(object_name=o.object_name or "") for o in objects]


@router.get("/retrievable_objects")
def get_retrievable_objects() -> list[StorageObject]:
    objects = S3Storage().list_objects(bucket=S3Storage().RETRIEVAL_BUCKET)
    return [StorageObject(object_name=o.object_name or "") for o in objects]


@router.post("/new_dataset/")
async def create_new_dataset(id: int):
    try:
        m = await run_create_dataset_deployment(id, 10, 10)
        return JSONResponse(content={f"status: flow scheduled '{m.name}'"}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post("/job/")
async def create_job(job: Job):
    try:
        j: Job = Job.model_validate(job)

        m = None
        match j.type:
            case "archive":
                m = await run_archiving_deployment(j)
            case "retrieve":
                m = await run_retrieval_deployment(j)
            case _:
                return JSONResponse(content={"error": f"unknown job type {j.type}"}, status_code=500)

        return JSONResponse(content={"status": f"{j.type} flow scheduled '{m.name}'"}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
