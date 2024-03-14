from fastapi import APIRouter

from .working_storage_interface import minioClient

from fastapi.responses import JSONResponse
import archiver.tasks as tasks
from archiver.model import ArchiveJob, Object

router = APIRouter()


@router.get("/tasks", status_code=201)
def run_task():
    try:
        task = tasks.create_archiving_pipeline()
        task.delay()
        return JSONResponse({"task_id": task.id})
    except:
        return JSONResponse(status_code=500)


@router.get("/archivable_objects")
def get_archivable_objects() -> list[Object]:
    objects = minioClient.get_objects(bucket=minioClient.ARCHIVAL_BUCKET)
    return [Object(object_name=o.object_name) for o in objects]


@router.post("/archiving/")
async def create_archive_job(job: ArchiveJob):
    try:
        j = ArchiveJob.model_validate(job)
        task = tasks.create_archiving_pipeline(j.filename)
        task.delay()
        return JSONResponse({"task_id": task.id})
    except:
        return JSONResponse(content={"task_id": -1}, status_code=500)
