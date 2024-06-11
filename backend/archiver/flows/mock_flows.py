from prefect import flow, task
import os
import shutil
import requests
from pathlib import Path
from archiver.config.variables import Variables
from archiver.utils.datablocks import upload_objects
from archiver.utils.working_storage_interface import MinioStorage
from archiver.utils.model import OrigDataBlock, DataFile
from archiver.flows.utils import StoragePaths


@task
def create_dummy_dataset(dataset_id: int):
    scratch_folder = Variables().ARCHIVER_SCRATCH_FOLDER / str(dataset_id)
    if not scratch_folder.exists():
        scratch_folder.mkdir(parents=True)

    size_MB = 64

    for i in range(10):
        os.system(f"dd if=/dev/urandom of={scratch_folder}/file_{i}.bin bs={size_MB}M count=2 iflag=fullblock")

    files = upload_objects(minio_prefix=Path(StoragePaths.relative_datablocks_folder(dataset_id)), bucket=MinioStorage().LANDINGZONE_BUCKET,
                           source_folder=scratch_folder)

    shutil.rmtree(scratch_folder)
    checksums = []

    # create orig datablocks
    origdatablock = OrigDataBlock(id=str(dataset_id),
                                  datasetId=str(dataset_id),
                                  size=2 * size_MB,
                                  ownerGroup="0",
                                  dataFileList=[DataFile(path=str(p), chk=c) for p, c in zip(files, checksums)]
                                  )
    j = origdatablock.model_dump_json()

    # register orig datablocks
    requests.post(f"{Variables().SCICAT_ENDPOINT}{Variables().SCICAT_API_PREFIX}OrigDatablocks/",
                  data=j)


@flow(name="create_test_dataset", )
def create_test_dataset_flow(dataset_id: int):
    create_dummy_dataset(dataset_id)
