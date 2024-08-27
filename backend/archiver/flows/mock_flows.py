import random
from prefect import flow, task
import os
import datetime
import shutil
import requests
from pathlib import Path
from archiver.config.variables import Variables
from archiver.utils.datablocks import upload_objects_to_s3, create_tarballs
from archiver.utils.working_storage_interface import Bucket
from archiver.utils.model import OrigDataBlock, DataFile, Dataset, DatasetLifecycle
from archiver.flows.utils import StoragePaths
from archiver.scicat.scicat_tasks import get_scicat_access_token
from .task_utils import generate_task_name_dataset


@task(task_run_name=generate_task_name_dataset, persist_result=True, log_prints=True)
def create_dummy_dataset(dataset_id: str, file_size_MB: int, num_files: int, datablock_size_MB: int, create_job: bool = False):
    dataset_root = Variables().ARCHIVER_SCRATCH_FOLDER / dataset_id

    raw_files_folder = dataset_root / "raw_files"
    if not raw_files_folder.exists():
        raw_files_folder.mkdir(parents=True)

    datablocks_folder = dataset_root / "datablocks"
    if not datablocks_folder.exists():
        datablocks_folder.mkdir(parents=True)

    for i in range(num_files):
        os.system(f"dd if=/dev/urandom of={raw_files_folder}/file_{i}.bin bs={file_size_MB}M count=1 iflag=fullblock")

    orig_data_blocks = create_tarballs(dataset_id=dataset_id, src_folder=raw_files_folder,
                                       dst_folder=datablocks_folder, target_size=datablock_size_MB * (1024**2))

    files = upload_objects_to_s3(prefix=Path(StoragePaths.relative_origdatablocks_folder(dataset_id)),
                                 bucket=Bucket.landingzone_bucket(), source_folder=datablocks_folder, ext=".gz")

    checksums = []
    for f in files:
        checksums.append("1234")

    dataset = Dataset(
        pid=dataset_id,
        # createdAt=datetime.datetime.now(datetime.UTC).isoformat(),
        principalInvestigator="testPI",
        ownerGroup="ingestor",
        owner="ingestor",
        sourceFolder=str(dataset_root),
        contactEmail="testuser@testfacility.com",
        size=1234,
        numberOfFiles=len(files),
        creationTime=datetime.datetime.now(datetime.UTC).isoformat(),
        type="raw",
        creationLocation="ETHZ",
        datasetlifecycle=DatasetLifecycle(
            id=dataset_id,
            archivable=True,
            isOnCentralDisk=True
        )
        # origdatablocks=[origdatablock]
    )
    j = dataset.model_dump_json(exclude_none=True)

    token = get_scicat_access_token()

    # register orig datablocks
    token_value = token.get_secret_value()
    headers = {"Authorization": f"Bearer {token_value}", "Content-Type": "application/json"}
    resp = requests.post(f"{Variables().SCICAT_ENDPOINT}{Variables().SCICAT_API_PREFIX}datasets/",
                         data=j, headers=headers)
    resp.raise_for_status()

    import tarfile

    for orig in orig_data_blocks:
        with tarfile.open(orig, 'r') as file:
            files_in_tar = file.getnames()
            datafiles = [DataFile(
                path=str(raw_files_folder / f),
                chk="1234",
                size=Path(raw_files_folder / f).stat().st_size,
                time=str(datetime.datetime.now(datetime.UTC).isoformat())) for f in files_in_tar]

            origdatablock = OrigDataBlock(
                datasetId=dataset_id,
                size=2 * file_size_MB,
                ownerGroup="ingestor",
                dataFileList=datafiles
                # dataFileList=[DataFile(
                #     path=str(p),
                #     chk=c,
                #     size=1111,
                #     time=str(datetime.datetime.now(datetime.UTC).isoformat())) for p, c in zip(files, checksums)]
            )

            j = origdatablock.model_dump_json(exclude_none=True)

            print(f"Register datablock {orig}")
            resp = requests.post(f"{Variables().SCICAT_ENDPOINT}{Variables().SCICAT_API_PREFIX}origdatablocks",
                                 data=j, headers=headers)
            resp.raise_for_status()

    shutil.rmtree(dataset_root)


@ flow(name="create_test_dataset", persist_result=True)
def create_test_dataset_flow(dataset_id: str | None, file_size_MB: int = 10, num_files: int = 10, datablock_size_MB: int = 20):
    dataset_id = dataset_id or str(random.randint(0, 10000))
    job = create_dummy_dataset(dataset_id=dataset_id,
                               file_size_MB=file_size_MB,
                               num_files=num_files,
                               datablock_size_MB=datablock_size_MB)
    return dataset_id
