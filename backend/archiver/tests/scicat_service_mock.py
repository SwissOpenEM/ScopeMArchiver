from archiver.utils.model import Job, Dataset, DataBlock, OrigDataBlock
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Body
import logging
from typing import List, Dict
import os


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

origdatablocks: Dict[str, List[OrigDataBlock]] = {}
datablocks: Dict[str, List[DataBlock]] = {}


@app.patch("/Jobs/{JobId}/")
def jobs(JobId: int, job: Job):
    _LOGGER.info(f"{JobId}: {job.model_dump_json()}")


@app.post("/Datablocks/")
def datablock_post(datablock: DataBlock):
    _LOGGER.info(f"{datablock}: {datablock.model_dump_json()}")
    if datablock.datasetId is not None:
        if datablock.datasetId not in datablocks.keys():
            datablocks[datablock.datasetId] = []
        datablocks[datablock.datasetId].append(datablock)


@app.patch("/Datasets/{DatasetId}")
def datasets_patch(DatasetId: int, dataset: Dataset):
    _LOGGER.info(f"{DatasetId}: {dataset.model_dump_json()}")


@app.post("/Datasets/{DatasetId}")
def datasets_post(DatasetId: int, dataset: Dataset):
    _LOGGER.info(f"{DatasetId}: {dataset.model_dump_json()}")


@app.post("/OrigDatablocks")
def origdatablocks_post(origDatablock: OrigDataBlock) -> None:
    if origDatablock.datasetId is not None:
        if origDatablock.datasetId not in origdatablocks.keys():
            origdatablocks[origDatablock.datasetId] = []
        origdatablocks[origDatablock.datasetId].append(origDatablock)


@app.get("/Datasets/{DatasetId}/origdatablocks")
def origdatablocks_get(DatasetId: int) -> List[OrigDataBlock]:
    return origdatablocks[str(DatasetId)]


@app.get("/Datasets/{DatasetId}/datablocks")
def datablocks_get(DatasetId: int) -> List[DataBlock]:
    return datablocks[str(DatasetId)]
