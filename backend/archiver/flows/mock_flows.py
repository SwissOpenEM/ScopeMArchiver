from prefect import flow, task
import os
import shutil
import requests
from pathlib import Path
from archiver.config.variables import Variables
from archiver.utils.datablocks import upload_objects_to_s3, create_tarballs
from archiver.utils.working_storage_interface import S3Storage
from archiver.utils.model import OrigDataBlock, DataFile
from archiver.flows.utils import StoragePaths


@task
def create_dummy_dataset(dataset_id: int):
    scratch_folder = Variables().ARCHIVER_SCRATCH_FOLDER / str(dataset_id)
    if not scratch_folder.exists():
        scratch_folder.mkdir(parents=True)

    size_MB = 64

    for i in range(10):
        os.system(f"dd if=/dev/urandom of={scratch_folder}/file_{i}.bin bs={size_MB}M count=1 iflag=fullblock")

    create_tarballs(dataset_id=dataset_id, src_folder=scratch_folder, dst_folder=scratch_folder, target_size=size_MB * 2 * (1024**2) + 1)

    files = upload_objects_to_s3(prefix=Path(StoragePaths.relative_datablocks_folder(dataset_id)), bucket=S3Storage().LANDINGZONE_BUCKET,
                                 source_folder=scratch_folder, ext=".gz")

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
