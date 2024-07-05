import random
from prefect import flow, task
from prefect.deployments.deployments import run_deployment
import os
import asyncio
import shutil
import requests
from pathlib import Path
from archiver.config.variables import Variables
from archiver.utils.datablocks import upload_objects_to_s3, create_tarballs
from archiver.utils.working_storage_interface import S3Storage
from archiver.utils.model import OrigDataBlock, DataFile
from archiver.flows.utils import StoragePaths
from .task_utils import generate_task_name_dataset
from archiver.flows.utils import StoragePaths


@task(task_run_name=generate_task_name_dataset)
def create_dummy_dataset(dataset_id: int, file_size_MB: int, num_files: int):
    scratch_folder = Variables().ARCHIVER_SCRATCH_FOLDER / str(dataset_id)
    if not scratch_folder.exists():
        scratch_folder.mkdir(parents=True)

    for i in range(num_files):
        os.system(f"dd if=/dev/urandom of={scratch_folder}/file_{i}.bin bs={file_size_MB}M count=1 iflag=fullblock")

    create_tarballs(dataset_id=dataset_id, src_folder=scratch_folder,
                    dst_folder=scratch_folder, target_size=file_size_MB * 2 * (1024**2) + 1)

    files = upload_objects_to_s3(prefix=Path(StoragePaths.relative_origdatablocks_folder(dataset_id)),
                                 bucket=S3Storage().LANDINGZONE_BUCKET, source_folder=scratch_folder, ext=".gz")

    shutil.rmtree(scratch_folder)
    checksums = []

    # create orig datablocks
    origdatablock = OrigDataBlock(id=str(dataset_id),
                                  datasetId=str(dataset_id),
                                  size=2 * file_size_MB,
                                  ownerGroup="0",
                                  dataFileList=[DataFile(path=str(p), chk=c) for p, c in zip(files, checksums)]
                                  )
    j = origdatablock.model_dump_json()

    # register orig datablocks
    requests.post(f"{Variables().SCICAT_ENDPOINT}{Variables().SCICAT_API_PREFIX}OrigDatablocks/",
                  data=j)


@flow(name="create_test_dataset")
def create_test_dataset_flow(file_size_MB: int = 10, num_files: int = 10):
    dataset_id = random.randint(0, 1000)
    create_dummy_dataset(dataset_id, file_size_MB, num_files)


async def run_create_dataset_deployment(dataset_id: int, file_size_MB: int, num_files: int):
    a = await asyncio.create_task(run_deployment("create_test_dataset/dataset_creation", parameters={
        "dataset_id": dataset_id,
        "file_size_MB": file_size_MB,
        "num_files": num_files
    }, timeout=0))
    return a
