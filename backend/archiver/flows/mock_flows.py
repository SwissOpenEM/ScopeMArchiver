from prefect import flow
import os
import requests
from pathlib import Path
from archiver.config import settings
from archiver.datablocks import upload_objects
from archiver.working_storage_interface import minioClient
from archiver.model import OrigDataBlock, DataFile


def create_dummy_dataset(dataset_id: int):
    scratch_folder = settings.ARCHIVER_SCRATCH_FOLDER / str(dataset_id)
    if not scratch_folder.exists():
        scratch_folder.mkdir(parents=True)

    size_MB = 64

    for i in range(10):
        os.system(f"dd if=/dev/urandom of={scratch_folder}/file_{i}.bin bs={size_MB}M count=2 iflag=fullblock")

    files = upload_objects(minio_prefix=Path(str(dataset_id)), bucket=minioClient.LANDINGZONE_BUCKET,
                           source_folder=scratch_folder)

    # create orig datablocks
    origdatablock = OrigDataBlock(id=str(dataset_id),
                                  datasetId=str(dataset_id),
                                  size=2 * size_MB,
                                  ownerGroup="0",
                                  dataFileList=[DataFile(path=str(p)) for p in files]
                                  )
    j = origdatablock.model_dump_json()

    # register orig datablocks
    requests.post(f"{settings.SCICAT_ENDPOINT}{settings.SCICAT_API_PREFIX}OrigDatablocks/",
                  data=j)


@flow(name="create_test_dataset", )
def create_test_dataset_flow(dataset_id: int):
    create_dummy_dataset(dataset_id)
