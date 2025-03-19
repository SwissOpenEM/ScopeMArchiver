import random
import tempfile
import time
from typing import Any, Dict, Optional
import uuid
from prefect import Flow, State, flow, task
import os
import datetime
import shutil
from pydantic import SecretStr
import requests
from pathlib import Path
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import FlowRun
import urllib
import asyncio

from archiver.config.variables import Variables
from archiver.utils.datablocks import upload_objects_to_s3
from archiver.utils.s3_storage_interface import Bucket, get_s3_client
from archiver.utils.model import OrigDataBlock, DataFile, Dataset, DatasetLifecycle

from archiver.utils.log import getLogger, log
from archiver.flows.utils import StoragePaths
from archiver.scicat.scicat_tasks import get_scicat_access_token
from archiver.utils.model import DatasetListEntry, Job
from .task_utils import generate_task_name_dataset

from prefect.flow_runs import wait_for_flow_run

def headers(token: SecretStr):
    return {
        "Authorization": f"Bearer {token.get_secret_value()}",
        "Content-Type": "application/json",
    }
    
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
    host = Variables().SCICAT_ENDPOINT
    api = Variables().SCICAT_API_PREFIX
    resp = requests.post(
        f"{host}{api}datasets/",
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
            f"{host}{api}origdatablocks",
            data=j,
            headers=headers,
        )
        resp.raise_for_status()

    shutil.rmtree(dataset_root)


SCICAT_JOB_PATH = "jobs"
SCICAT_DATASETS_PATH = "datasets"


@flow(name="create_test_dataset", persist_result=True)
def create_test_dataset_flow(
    dataset_id: str | None,
    file_size_MB: int = 10,
    num_files: int = 10,
    datablock_size_MB: int = 20,
):
    dataset_id = dataset_id or str()
    job = create_dummy_dataset(
        dataset_id=dataset_id,
        file_size_MB=file_size_MB,
        num_files=num_files,
        datablock_size_MB=datablock_size_MB,
    )
    return dataset_id



@task
def scicat_create_retrieval_job(dataset: str, token: SecretStr) -> uuid.UUID:
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
    host =  Variables().SCICAT_ENDPOINT
    api =  Variables().SCICAT_API_PREFIX
    response = requests.post(
        url=f"{host}{api}{SCICAT_JOB_PATH}",
        data=job.model_dump_json(exclude_none=True),
        headers=headers(token),
    )
    response.raise_for_status()
    job_uuid: uuid.UUID = uuid.UUID(response.json()["id"])
    return job_uuid


@task
def scicat_create_archival_job(dataset: str, token: SecretStr) -> uuid.UUID:
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
    host =  Variables().SCICAT_ENDPOINT
    api =  Variables().SCICAT_API_PREFIX
    response = requests.post(
        url=f"{host}{api}{SCICAT_JOB_PATH}",
        data=j,
        headers=headers(token),
    )
    response.raise_for_status()
    archive_job_uuid: uuid.UUID = uuid.UUID(response.json()["id"])
    return archive_job_uuid


@task(cache_result_in_memory=False, log_prints=True)
def get_scicat_dataset(dataset_pid: str, token: SecretStr) -> Dict[str, Any]:
    host =  Variables().SCICAT_ENDPOINT
    api =  Variables().SCICAT_API_PREFIX
    response = requests.get(
        url=f"{host}{api}{SCICAT_DATASETS_PATH}/{dataset_pid}",
        headers=headers(token),
    )
    return response.json()


@task(cache_result_in_memory=False)
def get_scicat_job(job_id: uuid.UUID, token: SecretStr) -> Dict[str, Any]:
    host =  Variables().SCICAT_ENDPOINT
    api =  Variables().SCICAT_API_PREFIX
    response = requests.get(
        url=f"{host}{api}{SCICAT_JOB_PATH}/{job_id}",
        headers=headers(token),
    )
    return response.json()

@task(cache_result_in_memory=False)
def get_scicat_job2(job_id: uuid.UUID, token: SecretStr) -> Dict[str, Any]:
    host =  Variables().SCICAT_ENDPOINT
    api =  Variables().SCICAT_API_PREFIX
    response = requests.get(
        url=f"{host}{api}{SCICAT_JOB_PATH}/{job_id}",
        headers=headers(token),
    )
    return response.json()

PREFECT_SERVER_URL = "https://scopem-openem.ethz.ch/archiver/prefect/api"

@log
async def get_flow_result(flow_run_id: uuid.UUID) -> Optional[State]:
    async with PrefectClient(api=PREFECT_SERVER_URL) as client:
        flow_run: FlowRun =  await wait_for_flow_run(flow_run_id=flow_run_id, client=client)
        flow_run =  await client.read_flow_run(flow_run.id)
        return flow_run.state

@log
def find_flow_in_prefect(job_id: uuid.UUID) -> uuid.UUID:
    url = f"{PREFECT_SERVER_URL}/flow_runs/filter"
    payload = {"flow_runs": {"name": {"like_": f"{job_id}"}}}

    # Headers to include, if necessary, e.g., authentication tokens
    headers = {
        "Content-Type": "application/json",
    }

    flow_run_ids = []
    max_retries = 30
    retry = 0
    while retry < max_retries:
        # Making the POST request
        response = requests.post(url, json=payload, headers=headers)
        assert response.status_code == 200
        flow_run_ids = response.json()
        if len(flow_run_ids) == 1:
            if flow_run_ids[0]["state_type"] == "COMPLETED":
                break
        time.sleep(10)
        retry += 1

    if retry >= max_retries:
        getLogger().error(f"Flow with job id {job_id} not found in state COMPLETED")
    assert len(flow_run_ids) == 1
    getLogger().info(flow_run_ids)
    return flow_run_ids[0]["id"]

@task(name="verify_dataset_in_scicat")
def verify_dataset_in_scicat(dataset_pid, scicat_token):
    dataset =  get_scicat_dataset.submit(dataset_pid=dataset_pid, token=scicat_token).result()
    assert dataset is not None

    getLogger().info(dataset)
    # Verify Scicat datasetlifecycle
    dataset_lifecycle = dataset.get("datasetlifecycle")
    getLogger().info(dataset_lifecycle)
    # assert dataset_lifecycle is not None
    # assert dataset_lifecycle.get("archiveStatusMessage") == "datasetCreated"
    # assert dataset_lifecycle.get("archivable")
    # assert not dataset_lifecycle.get("retrievable")

@task(name="verify_dataset_in_minio")
def verify_dataset_in_minio(dataset_pid):
    s3_client =  get_s3_client()
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

@log
async def wait_for_prefect_run(scicat_archival_job_id):
    archival_flow_run_id =  find_flow_in_prefect(scicat_archival_job_id)
    archival_state = await get_flow_result(flow_run_id=archival_flow_run_id)
    getLogger().info(archival_state)
    assert archival_state is not None

@task
def wait_for_flow(scicat_job_id):
    asyncio.run(wait_for_prefect_run(scicat_job_id))

@task
def verify_data_from_minio(dataset_pid, datablock_name, datablock_url):
        # verify file can be downloaded from MINIO via url in jobresult
    with tempfile.TemporaryDirectory() as temp_dir:
        dest_file: Path = Path(temp_dir) / datablock_name
        urllib.request.urlretrieve(datablock_url, dest_file)
        assert dest_file.exists()
    s3_client =  get_s3_client()
    # Verify retrieved datablock in MINIO
    retrieved_datablock = s3_client.stat_object(
        bucket=Bucket("retrieval"),
        filename=f"openem-network/datasets/{dataset_pid}/datablocks/{dataset_pid}_0.tar.gz",
    )
    assert retrieved_datablock is not None
    assert retrieved_datablock.Size > 80 * 1024 * 1024


class AssertionFailure(Exception):
    message: str
    pass

def on_test_flow_failure(flow: Flow, flow_run: FlowRun, state: State):
    try:
        state.result()
    except AssertionFailure as assertion:
        getLogger().error(f"TEST ASSERTION FAILED: {assertion.message}")



def ASSERT(expression: bool):
    if not expression:
        from inspect import getframeinfo, stack
        def debuginfo():
            caller = getframeinfo(stack()[2][0])
            return f"%s" % (caller.code_context[0])
        
        a = AssertionFailure()
        a.message=debuginfo()
        raise a
    


@flow(name="end_to_end_test_flow")
def end_to_end_test_flow(
    file_size_MB: int = 100,
    num_files: int = 10,
    orig_datablock_size_MB: int = 200,
):
    dataset_pid = str(uuid.uuid4())
    wait  = create_dummy_dataset.submit(
        dataset_id=dataset_pid,
        file_size_MB=file_size_MB,
        num_files=num_files,
        datablock_size_MB=orig_datablock_size_MB,
    )

    scicat_token = get_scicat_access_token()
    verify_scicat = verify_dataset_in_scicat.submit(dataset_pid=dataset_pid, scicat_token=scicat_token, wait_for=[wait])


   
    verify_s3 = verify_dataset_in_minio.submit(dataset_pid=dataset_pid, wait_for=[wait])
    
    # trigger archive job in scicat
    scicat_archival_job_id = scicat_create_archival_job.submit(dataset=dataset_pid, token=scicat_token, wait_for=[verify_scicat, verify_s3])

    # Verify Scicat Job status
    scicat_archival_job_status_future = get_scicat_job.submit(job_id=scicat_archival_job_id, token=scicat_token)
    job_id = scicat_archival_job_id.result()
    getLogger().info(f"Scicat job created: {job_id}")

    scicat_archival_job_status = scicat_archival_job_status_future.result()

    ASSERT(scicat_archival_job_status is not None)
    getLogger().info(scicat_archival_job_status)

    ASSERT(scicat_archival_job_status.get("type") == "archive")

    ASSERT (
        scicat_archival_job_status.get("statusCode") == "jobCreated"
        or scicat_archival_job_status.get("statusMessage") == "inProgress"
    )

    wait_for_flow.submit(scicat_job_id=scicat_archival_job_id).wait()
    getLogger().info("Archiving Flow finished")

    # Verify Scicat Job status
    scicat_archival_job_status_future = get_scicat_job.submit(job_id=job_id, token=scicat_token)
    scicat_archival_job_status  = scicat_archival_job_status_future.result()
    assert scicat_archival_job_status is not None

    getLogger().info(f"Scicat job status {scicat_archival_job_status}")

    ASSERT(scicat_archival_job_status.get("type") == "archive")
    ASSERT(scicat_archival_job_status.get("statusMessage") == "finishedSuccessful")

    # Verify Scicat datasetlifecycle
    dataset_future = get_scicat_dataset.submit(dataset_pid=dataset_pid, token=scicat_token)
    dataset = dataset_future.result()
    getLogger().info(dataset)
    ASSERT(dataset is not None)
    dataset_lifecycle = dataset.get("datasetlifecycle")
    ASSERT(dataset_lifecycle is not None)
    getLogger().info(f"Dataset lifecycle {dataset_lifecycle}")
    # ASSERT(dataset_lifecycle.get("archiveStatusMessage") == "datasetOnArchiveDisk")
    ASSERT(dataset_lifecycle.get("retrieveStatusMessage") == "")
    ASSERT(not dataset_lifecycle.get("archivable"))
    ASSERT(dataset_lifecycle.get("retrievable"))

    # trigger retrieval job in scicat
    scicat_retrieval_job_id = scicat_create_retrieval_job.submit(dataset=dataset_pid, token=scicat_token)

    # Verify Scicat Job status
    scicat_retrieval_job_status_future = get_scicat_job.submit(job_id=scicat_retrieval_job_id, token=scicat_token)
    scicat_retrieval_job_status =scicat_retrieval_job_status_future.result()
    getLogger().info(scicat_retrieval_job_status)
    ASSERT(scicat_retrieval_job_status is not None)
    ASSERT(scicat_retrieval_job_status.get("type") == "retrieve")
    ASSERT(
        scicat_retrieval_job_status.get("statusCode") == "jobCreated"
        or scicat_retrieval_job_status.get("statusMessage") == "inProgress"
    )

    wait_for_flow.submit(scicat_job_id=scicat_retrieval_job_id).wait()

    # Verify Scicat Job status
    scicat_retrieval_job_status_future = get_scicat_job.submit(job_id=scicat_retrieval_job_id, token=scicat_token)
    scicat_retrieval_job_status = scicat_retrieval_job_status_future.result()
    ASSERT(scicat_retrieval_job_status is not None)
    ASSERT(scicat_retrieval_job_status.get("type") == "retrieve")
    ASSERT(scicat_retrieval_job_status.get("statusMessage") == "finishedSuccessful")
    ASSERT(scicat_retrieval_job_status.get("jobResultObject") is not None)
    jobResult = scicat_retrieval_job_status.get("jobResultObject").get("result")
    ASSERT(len(jobResult) > 0)
    ASSERT(jobResult[0].get("datasetId") == dataset_pid)
    ASSERT(jobResult[0].get("url") is not None)
    
    verify_data_from_minio.submit(dataset_pid=dataset_pid,datablock_name = jobResult[0].get("name"), datablock_url = jobResult[0].get("url")).wait()

    # Verify Scicat datasetlifecycle
    dataset_future = get_scicat_dataset.submit(dataset_pid=dataset_pid, token=scicat_token)
    dataset = dataset_future.result()
    ASSERT(dataset is not None)
    dataset_lifecycle: Dict[Any, Any] = dataset.get("datasetlifecycle")
    ASSERT(dataset_lifecycle.get("retrieveStatusMessage") == "datasetRetrieved")
    # This is in fact a Scicat issue: fields in the datasetlifecycle are set to thedefault if not updated
    # https://github.com/SciCatProject/scicat-backend-next/blob/release-jobs/src/datasets/datasets.service.ts#L273
    # ASSERT(dataset_lifecycle.get("archiveStatusMessage") == "datasetOnArchiveDisk")
    ASSERT(not dataset_lifecycle.get("archivable"))
    ASSERT(dataset_lifecycle.get("retrievable"))
