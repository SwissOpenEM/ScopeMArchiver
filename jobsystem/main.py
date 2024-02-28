from celery.result import AsyncResult
from fastapi import Body, FastAPI, Form, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from working_storage_interface import minioClient

from pydantic import BaseModel


import tasks


class ArchiveJob(BaseModel):
    filename: str


class Object(BaseModel):
    object_name: str


app = FastAPI()

origins = [
    "http://127.0.0.1*",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/tasks", status_code=201)
def run_task():
    try:
        task = tasks.create_archiving_pipeline()
        task.delay()
        return JSONResponse({"task_id": task.id})
    except:
        return JSONResponse(status_code=500)


@app.get("/archivable_objects")
def get_archivable_objects() -> list[Object]:
    objects = minioClient.get_objects(bucket=minioClient.ARCHIVAL_BUCKET)
    return [Object(object_name=o.object_name) for o in objects]


@app.post("/archiving/")
async def create_archive_job(job: ArchiveJob):
    try:
        j = ArchiveJob.model_validate(job)
        task = tasks.create_archiving_pipeline(j.filename)
        task.delay()
        return JSONResponse({"task_id": task.id})
    except:
        return JSONResponse(content={"task_id": -1}, status_code=500)
