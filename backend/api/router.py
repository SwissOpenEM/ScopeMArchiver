from fastapi import APIRouter
from fastapi.responses import JSONResponse

from archiver.utils.working_storage_interface import S3Storage
from archiver.utils.model import StorageObject, Job
from archiver.flows import archive_datasets_flow, retrieve_datasets_flow

router = APIRouter()


@router.get("/archivable_objects")
def get_archivable_objects() -> list[StorageObject]:
    objects = S3Storage().list_objects(bucket=S3Storage().STAGING_BUCKET)
    return [StorageObject(object_name=o.object_name or "") for o in objects]


@router.get("/retrievable_objects")
def get_retrievable_objects() -> list[StorageObject]:
    objects = S3Storage().list_objects(bucket=S3Storage().RETRIEVAL_BUCKET)
    return [StorageObject(object_name=o.object_name or "") for o in objects]


@router.post("/job/")
async def create_job(job: Job):
    try:
        j: Job = Job.model_validate(job)

        m = None
        match j.type:
            case "archive":
                m = await archive_datasets_flow.run_archiving_deployment(j)
            case "retrieve":
                m = await retrieve_datasets_flow.run_retrieval_deployment(j)
            case _:
                return JSONResponse(content={"error": f"unknown job type {j.type}"}, status_code=500)

        return JSONResponse(content={"status": f"{j.type} flow scheduled '{m.name}'"}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
