from celery.result import AsyncResult
from fastapi import Body, FastAPI, Form, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import tasks


app = FastAPI()
# app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/tasks", status_code=201)
def run_task():
    task = tasks.create_archiving_pipeline()
    task.delay()
    # task = tasks.update_job_status.delay()
    return JSONResponse({"task_id": task.id})
    # return JSONResponse({})
