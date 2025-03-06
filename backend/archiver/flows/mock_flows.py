import random
import tempfile
import time
from typing import Any, Dict, Optional
from uuid import UUID
from prefect import State, flow, task, FlowRun
import os
import datetime
import shutil
from pydantic import SecretStr
import requests
from pathlib import Path
from prefect.client.orchestration import PrefectClient
import urllib

from archiver.config.variables import Variables
from archiver.utils.datablocks import upload_objects_to_s3
from archiver.utils.s3_storage_interface import Bucket, get_s3_client
from archiver.utils.model import OrigDataBlock, DataFile, Dataset, DatasetLifecycle

from archiver.utils import getLogger
from archiver.flows.utils import StoragePaths
from archiver.scicat.scicat_tasks import get_scicat_access_token
from tests.test_e2e import headers
from utils.model import DatasetListEntry, Job
from .task_utils import generate_task_name_dataset

from prefect.flow_runs import wait_for_flow_run


@task(task_run_name=generate_task_name_dataset, persist_result=True, log_prints=True)
def create_dummy_dataset(
    dataset_id: str,
    file_size_MB: int,
    num_files: int,
    datablock_size_MB: int,
    create_job: bool = False,
):
    dataset_root = Variables().ARCHIVER_SCRATCH_FOLDER / dataset_id

    raw_files_folder = dataset_root / "raw_files"
    if not raw_files_folder.exists():
        raw_files_folder.mkdir(parents=True)

    for i in range(num_files):
        os.system(
            f"dd if=/dev/urandom of={raw_files_folder}/file_{i}.bin bs={file_size_MB}M count=1 iflag=fullblock"
        )

    files = upload_objects_to_s3(
        get_s3_client(),
        prefix=Path(StoragePaths.relative_raw_files_folder(dataset_id)),
        bucket=Bucket.landingzone_bucket(),
        source_folder=raw_files_folder,
    )

    checksums = []
    for f in files:
        checksums.append("1234")

    dataset = Dataset(
        datasetName=f"mock_dataset_{dataset_id}",
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
        datasetlifecycle=DatasetLifecycle(id=dataset_id, archivable=True, isOnCentralDisk=True),
        # origdatablocks=[origdatablock]
    )
    j = dataset.model_dump_json(exclude_none=True)

    token = get_scicat_access_token()

    # register orig datablocks
    token_value = token.get_secret_value()
    headers = {
        "Authorization": f"Bearer {token_value}",
        "Content-Type": "application/json",
    }
    resp = requests.post(
        f"{Variables().SCICAT_ENDPOINT}{Variables().SCICAT_API_PREFIX}datasets/",
        data=j,
        headers=headers,
    )
    resp.raise_for_status()

    orig_data_blocks = []

    current_origdatablock = OrigDataBlock(
        datasetId=dataset_id, size=0, ownerGroup="ingestor", dataFileList=[]
    )

    for file in raw_files_folder.iterdir():
        current_origdatablock.dataFileList.append(
            DataFile(  # type: ignore
                path=str(file.absolute()),
                chk="1234",
                size=file.stat().st_size,
                time=str(datetime.datetime.now(datetime.UTC).isoformat()),
            )
        )
        current_origdatablock.size = current_origdatablock.size + file.stat().st_size

        if current_origdatablock.size > datablock_size_MB * 1024 * 1024:
            orig_data_blocks.append(current_origdatablock)
            current_origdatablock = OrigDataBlock(
                datasetId=dataset_id, size=0, ownerGroup="ingestor", dataFileList=[]
            )

    for origdatablock in orig_data_blocks:
        j = origdatablock.model_dump_json(exclude_none=True)

        print(f"Register datablock {origdatablock}")
        resp = requests.post(
            f"{Variables().SCICAT_ENDPOINT}{Variables().SCICAT_API_PREFIX}origdatablocks",
            data=j,
            headers=headers,
        )
        resp.raise_for_status()

    shutil.rmtree(dataset_root)


SCICAT_JOB_PATH = "/jobs"
SCICAT_DATASETS_PATH = "/datasets"


@flow(name="create_test_dataset", persist_result=True)
def create_test_dataset_flow(
    dataset_id: str | None,
    file_size_MB: int = 10,
    num_files: int = 10,
    datablock_size_MB: int = 20,
):
    dataset_id = dataset_id or str(UUID())
    job = create_dummy_dataset(
        dataset_id=dataset_id,
        file_size_MB=file_size_MB,
        num_files=num_files,
        datablock_size_MB=datablock_size_MB,
    )
    return dataset_id


async def create_dataset() -> str:
    getLogger().info("Creating dataset")

    response = requests.post(
        url=f"https://{EXTERNAL_BACKEND_SERVER_URL}{BACKEND_API_PREFIX}{BACKEND_API_CREATE_DATASET_PATH}",
        json={
            "FileSizeInMB": 10,
            "NumberOfFiles": 10,
            "DatablockSizeInMB": 10,
        },
    )
    response.raise_for_status()
    new_dataset_flow_id = UUID(response.json()["Uuid"])
    new_dataset_flow_name = response.json()["Name"]
    new_dataset_id = response.json()["DataSetId"]
    getLogger().info(f"created flow {new_dataset_flow_name}")
    assert new_dataset_flow_id is not None

    getLogger().info("Waiting for dataset flow")
    flow_state = await get_flow_result(new_dataset_flow_id)
    assert flow_state is not None and flow_state.is_completed()
    return new_dataset_id


async def scicat_create_retrieval_job(dataset: str, token: SecretStr) -> UUID:
    getLogger().info("Creating retrieve job")

    job = Job(
        jobParams={
            "username": "ingestor",
            "datasetList": [DatasetListEntry(pid=str(dataset), files=[])],
        },
        type="retrieve",
        ownerGroup="ingestor",
    )
    # TODO: this entry point needs alignment with SciCat
    response = requests.post(
        url=f"https://{Variables().SCICAT_BACKEND}{Variables().SCICAT_API_PREFIX}{SCICAT_JOB_PATH}",
        data=job.model_dump_json(exclude_none=True),
        headers=headers(token),
    )
    response.raise_for_status()
    job_uuid: UUID = UUID(response.json()["id"])
    return job_uuid


async def scicat_create_archival_job(dataset: str, token: SecretStr) -> UUID:
    getLogger().info("Creating archive job")

    job = Job(
        jobParams={
            "username": "ingestor",
            "datasetList": [DatasetListEntry(pid=str(dataset), files=[])],
        },
        type="archive",
        ownerGroup="ingestor",
    )

    j = job.model_dump_json(exclude_none=True)
    response = requests.post(
        url=f"https://{Variables().SCICAT_BACKEND}{Variables().SCICAT_API_PREFIX}{SCICAT_JOB_PATH}",
        data=j,
        headers=headers(token),
    )
    response.raise_for_status()
    archive_job_uuid: UUID = UUID(response.json()["id"])
    return archive_job_uuid


async def get_scicat_dataset(dataset_pid: str, token: SecretStr) -> Dict[str, Any]:
    response = requests.get(
        url=f"https://{Variables().SCICAT_BACKEND}{Variables().SCICAT_API_PREFIX}{SCICAT_DATASETS_PATH}/{dataset_pid}",
        headers=headers(token),
    )
    return response.json()


async def get_scicat_job(job_id: UUID, token: SecretStr) -> Dict[str, Any]:
    response = requests.get(
        url=f"https://{Variables().SCICAT_BACKEND}{Variables().SCICAT_API_PREFIX}{SCICAT_JOB_PATH}/{job_id}",
        headers=headers(token),
    )
    return response.json()


PREFECT_SERVER_URL = "https://scopem-openem.ethz.ch/archiver/prefect/api"


async def get_flow_result(flow_run_id: UUID) -> Optional[State]:
    async with PrefectClient(api=PREFECT_SERVER_URL) as client:
        flow_run: FlowRun = await wait_for_flow_run(flow_run_id=flow_run_id, client=client)
        flow_run = await client.read_flow_run(flow_run.id)
        return flow_run.state


async def find_flow_in_prefect(job_id: UUID) -> UUID:
    url = f"{PREFECT_SERVER_URL}/flow_runs/filter"
    payload = {"flow_runs": {"name": {"like_": f"{job_id}"}}}

    # Headers to include, if necessary, e.g., authentication tokens
    headers = {
        "Content-Type": "application/json",
    }

    flow_run_ids = []
    max_retries = 4
    retry = 0
    while len(flow_run_ids) == 0 and retry < max_retries:
        # Making the POST request
        response = requests.post(url, json=payload, headers=headers)

        assert response.status_code == 200
        flow_run_ids = response.json()
        time.sleep(3)
        retry += 1

    assert len(flow_run_ids) == 1
    return flow_run_ids[0]["id"]


@flow(name="end_to_end_test", persist_result=True)
async def end_to_end_test_flow(
    dataset_id: str | None,
    file_size_MB: int = 10,
    num_files: int = 10,
    datablock_size_MB: int = 20,
):
    dataset_pid = dataset_id or str(UUID())
    create_dummy_dataset(
        dataset_id=dataset_id,
        file_size_MB=file_size_MB,
        num_files=num_files,
        datablock_size_MB=datablock_size_MB,
    )

    scicat_token = get_scicat_access_token()

    dataset = await get_scicat_dataset(dataset_pid=dataset_pid, token=scicat_token)
    assert dataset is not None

    # Verify Scicat datasetlifecycle
    dataset_lifecycle = dataset.get("datasetlifecycle")
    assert dataset_lifecycle is not None
    assert dataset_lifecycle.get("archiveStatusMessage") == "datasetCreated"
    assert dataset_lifecycle.get("archivable")
    assert not dataset_lifecycle.get("retrievable")

    s3_client = get_s3_client()
    # Verify datablocks in MINIO
    orig_datablocks = list(
        map(
            lambda idx: s3_client.stat_object(
                bucket=Bucket("landingzone"),
                filename=f"openem-network/datasets/{dataset_pid}/raw_files/file_{idx}.bin",
            ),
            range(9),
        )
    )
    assert len(orig_datablocks) == 9

    # trigger archive job in scicat
    scicat_archival_job_id = await scicat_create_archival_job(dataset=dataset_pid, token=scicat_token)

    # Verify Scicat Job status
    scicat_archival_job_status = await get_scicat_job(job_id=scicat_archival_job_id, token=scicat_token)
    assert scicat_archival_job_status is not None
    assert scicat_archival_job_status.get("type") == "archive"
    assert (
        scicat_archival_job_status.get("statusCode") == "jobCreated"
        or scicat_archival_job_status.get("statusMessage") == "inProgress"
    )

    time.sleep(10)
    # Verify Prefect Flow
    archival_flow_run_id = await find_flow_in_prefect(scicat_archival_job_id)
    archival_state = await get_flow_result(flow_run_id=archival_flow_run_id)
    assert archival_state is not None

    # Verify Scicat Job status
    scicat_archival_job_status = await get_scicat_job(job_id=scicat_archival_job_id, token=scicat_token)
    assert scicat_archival_job_status is not None
    assert scicat_archival_job_status.get("type") == "archive"
    assert scicat_archival_job_status.get("statusMessage") == "finishedSuccessful"

    # Verify Scicat datasetlifecycle
    dataset = await get_scicat_dataset(dataset_pid=dataset_pid, token=scicat_token)
    assert dataset is not None
    dataset_lifecycle = dataset.get("datasetlifecycle")
    assert dataset_lifecycle is not None
    assert dataset_lifecycle.get("archiveStatusMessage") == "datasetOnArchiveDisk"
    assert dataset_lifecycle.get("retrieveStatusMessage") == ""
    assert not dataset_lifecycle.get("archivable")
    assert dataset_lifecycle.get("retrievable")

    # trigger retrieval job in scicat
    scicat_retrieval_job_id = await scicat_create_retrieval_job(dataset=dataset_pid, token=scicat_token)

    # Verify Scicat Job status
    scicat_retrieval_job_status = await get_scicat_job(job_id=scicat_retrieval_job_id, token=scicat_token)
    assert scicat_retrieval_job_status is not None
    assert scicat_retrieval_job_status.get("type") == "retrieve"
    assert (
        scicat_retrieval_job_status.get("statusCode") == "jobCreated"
        or scicat_retrieval_job_status.get("statusMessage") == "inProgress"
    )

    time.sleep(10)
    # Verify Prefect Flow
    retrieve_flow_run_id = await find_flow_in_prefect(scicat_retrieval_job_id)
    retrieval_state = await get_flow_result(retrieve_flow_run_id)
    assert retrieval_state is not None

    # Verify Scicat Job status
    scicat_retrieval_job_status = await get_scicat_job(job_id=scicat_retrieval_job_id, token=scicat_token)
    assert scicat_retrieval_job_status is not None
    assert scicat_retrieval_job_status.get("type") == "retrieve"
    assert scicat_retrieval_job_status.get("statusMessage") == "finishedSuccessful"
    assert scicat_retrieval_job_status.get("jobResultObject") is not None
    jobResult = scicat_retrieval_job_status.get("jobResultObject").get("result")
    assert len(jobResult) == 1
    assert jobResult[0].get("datasetId") == dataset_pid
    assert jobResult[0].get("url") is not None
    datablock_url = jobResult[0].get("url")
    datablock_name = jobResult[0].get("name")

    # verify file can be downloaded from MINIO via url in jobresult
    with tempfile.TemporaryDirectory() as temp_dir:
        dest_file: Path = Path(temp_dir) / datablock_name
        urllib.request.urlretrieve(datablock_url, dest_file)
        assert dest_file.exists()

    # Verify retrieved datablock in MINIO
    retrieved_datablock = s3_client.stat_object(
        bucket=Bucket("retrieval"),
        filename=f"openem-network/datasets/{dataset_pid}/datablocks/{dataset_pid}_0.tar.gz",
    )
    assert retrieved_datablock is not None
    assert retrieved_datablock.Size > 80 * 1024 * 1024

    # Verify Scicat datasetlifecycle
    dataset = await get_scicat_dataset(dataset_pid=dataset_pid, token=scicat_token)
    assert dataset is not None
    dataset_lifecycle: Dict[Any, Any] = dataset.get("datasetlifecycle")
    assert dataset_lifecycle.get("retrieveStatusMessage") == "datasetRetrieved"
    # This is in fact a Scicat issue: fields in the datasetlifecycle are set to the default if not updated
    # https://github.com/SciCatProject/scicat-backend-next/blob/release-jobs/src/datasets/datasets.service.ts#L273
    # assert dataset_lifecycle.get("archiveStatusMessage") == "datasetOnArchiveDisk"
    assert not dataset_lifecycle.get("archivable")
    assert dataset_lifecycle.get("retrievable")
