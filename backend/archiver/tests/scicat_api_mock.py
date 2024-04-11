import os
import logging
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware

from archiver.model import Job, Dataset, DataBlock

app = FastAPI(root_path="")

_LOGGER = logging.getLogger()

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


@app.patch("/Jobs/{JobId}/")
def jobs(JobId: int, job: Job):
    _LOGGER.info(f"{JobId}: {job.model_dump_json()}")


@app.patch("/Datasets/{DatasetId}")
def datasets_patch(DatasetId: int, dataset: Dataset):
    _LOGGER.info(f"{DatasetId}: {dataset.model_dump_json()}")


@app.post("/Datasets/{DatasetId}")
def datasets_post(DatasetId: int, dataset: Dataset):
    _LOGGER.info(f"{DatasetId}: {dataset.model_dump_json()}")
