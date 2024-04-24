from fastapi import APIRouter, HTTPException

from archiver.working_storage_interface import minioClient

from fastapi.responses import JSONResponse
from archiver.model import StorageObject, Job

router = APIRouter()


@router.get("/archivable_objects")
def get_archivable_objects() -> list[StorageObject]:
    objects = minioClient.get_objects(bucket=minioClient.STAGING_BUCKET)
    return [StorageObject(object_name=o.object_name or "") for o in objects]


@router.get("/retrievable_objects")
def get_retrievable_objects() -> list[StorageObject]:
    objects = minioClient.get_objects(bucket=minioClient.RETRIEVAL_BUCKET)
    return [StorageObject(object_name=o.object_name or "") for o in objects]


# @router.post("/job/")
# async def create_archive_job(job: Job):
#     try:
#         j: Job = Job.model_validate(job)

#         match j.type:
#             case "archive":
#                 await create_archival_flow(j)
#             case "retrieve":
#                 await create_retrieval_flow(j)
#             case _:
#                 return JSONResponse(content={"error": f"unknown job type {j.type}"}, status_code=500)

#     except Exception as e:
#         return JSONResponse(content={"error": str(e)}, status_code=500)
