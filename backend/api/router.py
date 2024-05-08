from fastapi import APIRouter
from fastapi.responses import JSONResponse

from archiver.working_storage_interface import MinioStorage
from archiver.model import StorageObject, Job
from archiver.flows import archiving_flow, retrieval_flow

router = APIRouter()


@router.get("/archivable_objects")
def get_archivable_objects() -> list[StorageObject]:
    objects = MinioStorage().get_objects(bucket=MinioStorage().STAGING_BUCKET)
    return [StorageObject(object_name=o.object_name or "") for o in objects]


@router.get("/retrievable_objects")
def get_retrievable_objects() -> list[StorageObject]:
    objects = MinioStorage().get_objects(bucket=MinioStorage().RETRIEVAL_BUCKET)
    return [StorageObject(object_name=o.object_name or "") for o in objects]


@router.post("/job/")
async def create_job(job: Job):
    try:
        j: Job = Job.model_validate(job)

        match j.type:
            case "archive":
                archiving_flow.run_archiving_deployment(j)
            case "retrieve":
                retrieval_flow.run_retrieval_deployment(j)
            case _:
                return JSONResponse(content={"error": f"unknown job type {j.type}"}, status_code=500)

        return JSONResponse(content={"status": f"{j.type} flow scheduled"}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
