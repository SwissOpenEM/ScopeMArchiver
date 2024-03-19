from fastapi import APIRouter

from .working_storage_interface import minioClient

from fastapi.responses import JSONResponse
import archiver.tasks as tasks
from archiver.model import ArchiveJob, RetrievalJob, StorageObject

router = APIRouter()


@router.get("/archivable_objects")
def get_archivable_objects() -> list[StorageObject]:
    objects = minioClient.get_objects(bucket=minioClient.ARCHIVAL_BUCKET)
    return [StorageObject(object_name=o.object_name) for o in objects]


@router.get("/retrievable_objects")
def get_retrievable_objects() -> list[StorageObject]:
    objects = minioClient.get_objects(bucket=minioClient.RETRIEVAL_BUCKET)
    return [StorageObject(object_name=o.object_name) for o in objects]


@router.post("/archive_dataset/")
async def create_archive_job(job: RetrievalJob):
    try:
        j = ArchiveJob.model_validate(job)
        task = tasks.create_archiving_pipeline(j.filename)
        task.delay()
        return JSONResponse({"task_id": task.id})
    except:
        return JSONResponse(content={"task_id": -1}, status_code=500)


@router.post("/retrieve_dataset/")
async def create_archive_job(job: ArchiveJob):
    try:
        j = ArchiveJob.model_validate(job)
        task = tasks.create_archiving_pipeline(j.filename)
        task.delay()
        return JSONResponse({"task_id": task.id})
    except:
        return JSONResponse(content={"task_id": -1}, status_code=500)


# @router.post("/create_datablocks/")
# async def create_archive_job(dataset: Dataset):
#     try:
#         j = ArchiveJob.model_validate(dataset)
#         # TODO: check for available dataset in storage
#         task = tasks.create_datablocks.delay(j.id)
#         return JSONResponse({"task_id": task.id})
#     except:
#         return JSONResponse(content={"task_id": -1}, status_code=500)
