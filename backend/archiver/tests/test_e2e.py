import logging
import pytest
import requests
import time
from typing import Dict, Optional, Any
from uuid import UUID
from archiver.utils.model import Job, DatasetListEntry
from pydantic import SecretStr
import minio

from prefect.client.schemas.objects import FlowRun, State
from prefect.client.orchestration import PrefectClient

from prefect.flow_runs import wait_for_flow_run

EXTERNAL_BACKEND_SERVER_URL = "scopem-openem.ethz.ch"
BACKEND_API_PREFIX = "/api/v1"
BACKEND_API_CREATE_DATASET_PATH = "/new_dataset/"


SCICAT_BACKEND_ENDPOINT = "scopem-openem.ethz.ch:89"
SCICAT_BACKEND_API_PREFIX = "/api/v3"
SCICAT_JOB_PATH = "/jobs"
SCICAT_DATASETS_PATH = "/datasets"
SCICAT_LOGIN_PATH = "/auth/login"

PREFECT_SERVER_URL = "http://scopem-openem.ethz.ch/api"
MINIO_SERVER_URL = "scopem-openem.ethz.ch:9000"


LTS_ROOT_PATH = "/tmp/LTS"

LOGGER = logging.getLogger(__name__)


def get_scicat_token(user: str = "ingestor", pw: str = "aman") -> SecretStr:

    resp = requests.post(url=f"http://{SCICAT_BACKEND_ENDPOINT}{SCICAT_BACKEND_API_PREFIX}{SCICAT_LOGIN_PATH}", json={
        "username": f"{user}",
        "password": f"{pw}"
    })

    resp.raise_for_status()

    return SecretStr(resp.json()["access_token"])


def headers(token: SecretStr):
    return {"Authorization": f"Bearer {token.get_secret_value()}", "Content-Type": "application/json"}


@pytest.fixture
def scicat_token_setup():
    yield get_scicat_token()


@pytest.fixture
def minio_client():
    return minio.Minio(
        endpoint=MINIO_SERVER_URL,
        access_key="minio_user",
        secret_key="minio_pass",
        region="eu-west1",
        secure=False
    )


@pytest.fixture
def set_env():
    import os

    envs = {
        'PREFECT_SERVER_URL': PREFECT_SERVER_URL,
    }

    for k, v in envs.items():
        os.environ[k] = v

    yield

    for k, v in envs.items():
        os.environ.pop(k)


async def create_dataset() -> str:
    LOGGER.info("Creating dataset")

    response = requests.post(
        url=f"http://{EXTERNAL_BACKEND_SERVER_URL}{BACKEND_API_PREFIX}{BACKEND_API_CREATE_DATASET_PATH}",
        json={

        }
    )
    response.raise_for_status()
    new_dataset_flow_id = UUID(response.json()["uuid"])
    new_dataset_flow_name = response.json()["name"]
    new_dataset_id = response.json()["dataset_id"]
    LOGGER.info(f"created flow {new_dataset_flow_name}")
    assert new_dataset_flow_id is not None

    LOGGER.info("Waiting for dataset flow")
    flow_state = await get_flow_result(new_dataset_flow_id)
    assert flow_state is not None and flow_state.is_completed()
    return new_dataset_id


async def scicat_create_retrieval_job(dataset: str, token: SecretStr) -> UUID:
    LOGGER.info("Creating retrieve job")

    job = Job(
        jobParams={"username": "ingestor",
                   "datasetList": [DatasetListEntry(pid=str(dataset), files=[])],
                   },
        emailJobInitiator="testuser@testfacility.com",
        type="retrieve",
        ownerGroup="ingestor",
        accessGroups=["ingestor"]
    )
    # TODO: this entry point needs alignment with SciCat
    response = requests.post(url=f"http://{SCICAT_BACKEND_ENDPOINT}{SCICAT_BACKEND_API_PREFIX}{SCICAT_JOB_PATH}",
                             data=job.model_dump_json(exclude_none=True),
                             headers=headers(token))
    response.raise_for_status()
    job_uuid: UUID = UUID(response.json()["id"])
    return job_uuid


async def scicat_create_archival_job(dataset: str, token: SecretStr) -> UUID:
    LOGGER.info("Creating archive job")

    job = Job(
        jobParams={"username": "ingestor",
                   "datasetList": [DatasetListEntry(pid=str(dataset), files=[])],
                   },
        emailJobInitiator="testuser@testfacility.com",
        type="archive",
        ownerGroup="ingestor",
        accessGroups=["ingestor"]
    )
    # TODO: this entry point needs alignment with SciCat

    j = job.model_dump_json(exclude_none=True)
    response = requests.post(url=f"http://{SCICAT_BACKEND_ENDPOINT}{SCICAT_BACKEND_API_PREFIX}{SCICAT_JOB_PATH}",
                             data=j,
                             headers=headers(token))
    response.raise_for_status()
    archive_job_uuid: UUID = UUID(response.json()["id"])
    return archive_job_uuid


async def get_scicat_dataset(dataset_pid: str, token: SecretStr) -> Dict[str, Any]:
    response = requests.get(url=f"http://{SCICAT_BACKEND_ENDPOINT}{SCICAT_BACKEND_API_PREFIX}{SCICAT_DATASETS_PATH}/{dataset_pid}",
                            headers=headers(token))
    return response.json()


async def get_scicat_job(job_id: UUID, token: SecretStr) -> Dict[str, Any]:
    response = requests.get(url=f"http://{SCICAT_BACKEND_ENDPOINT}{SCICAT_BACKEND_API_PREFIX}{SCICAT_JOB_PATH}/{job_id}",
                            headers=headers(token))
    return response.json()


async def get_flow_result(flow_run_id: UUID) -> Optional[State]:
    async with PrefectClient(api=PREFECT_SERVER_URL) as client:
        flow_run: FlowRun = await wait_for_flow_run(flow_run_id=flow_run_id, client=client)
        flow_run = await client.read_flow_run(flow_run.id)
        return flow_run.state


async def find_flow_in_prefect(job_id: UUID) -> UUID:
    url = f"{PREFECT_SERVER_URL}/flow_runs/filter"
    payload = {
        "flow_runs": {
            "name": {
                "like_": f"{job_id}"
            }
        }
    }

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
    return flow_run_ids[0]['id']


# @pytest.mark.endtoend
@pytest.mark.asyncio
async def test_end_to_end(scicat_token_setup, set_env, minio_client):
    """Runs a full workflow, i.e.
    - creating and registering a dataset
    - archving (on test volume)
    - retrieving

    It checks the following endpoints involved for the final result
    - Prefect for flow execution
    - Minio for the created/retrieved data
    - Scicat for dataset and job creation

    """

    # Create and register dataset -> dataset pid
    dataset_pid = await create_dataset()
    dataset = await get_scicat_dataset(dataset_pid=dataset_pid, token=scicat_token_setup)
    assert dataset is not None

    # Verify Scicat datasetlifecycle
    dataset_lifecycle = dataset.get("datasetlifecycle")
    assert dataset_lifecycle is not None
    assert dataset_lifecycle.get("archiveStatusMessage") == "datasetCreated"
    assert dataset_lifecycle.get("archivable")
    assert not dataset_lifecycle.get("retrievable")

    # Verify datablocks in MINIO
    orig_datablocks = list(map(lambda idx: minio_client.stat_object(bucket_name="landingzone",
                           object_name=f"openem-network/datasets/{dataset_pid}/origdatablocks/{dataset_pid}_{idx}.tar.gz"), range(9)))
    assert len(orig_datablocks) == 9

    # trigger archive job in scicat
    scicat_archival_job_id = await scicat_create_archival_job(dataset=dataset_pid, token=scicat_token_setup)

    # Verify Scicat Job status
    scicat_archival_job_status = await get_scicat_job(job_id=scicat_archival_job_id, token=scicat_token_setup)
    assert scicat_archival_job_status is not None
    assert scicat_archival_job_status.get("type") == "archive"
    assert scicat_archival_job_status.get(
        "statusMessage") == "jobCreated" or scicat_archival_job_status.get("statusMessage") == "inProgress"

    time.sleep(10)
    # Verify Prefect Flow
    archival_flow_run_id = await find_flow_in_prefect(scicat_archival_job_id)
    archival_state = await get_flow_result(flow_run_id=archival_flow_run_id)
    assert archival_state is not None

    # Verify Scicat Job status
    scicat_archival_job_status = await get_scicat_job(job_id=scicat_archival_job_id, token=scicat_token_setup)
    assert scicat_archival_job_status is not None
    assert scicat_archival_job_status.get("type") == "archive"
    assert scicat_archival_job_status.get("statusMessage") == "finishedSuccessful"

    # Verify Scicat datasetlifecycle
    dataset = await get_scicat_dataset(dataset_pid=dataset_pid, token=scicat_token_setup)
    assert dataset is not None
    dataset_lifecycle = dataset.get("datasetlifecycle")
    assert dataset_lifecycle is not None
    assert dataset_lifecycle.get("archiveStatusMessage") == "datasetOnArchiveDisk"
    assert dataset_lifecycle.get("retrieveStatusMessage") == ""
    assert not dataset_lifecycle.get("archivable")
    assert dataset_lifecycle.get("retrievable")

    # trigger retrieval job in scicat
    scicat_retrieval_job_id = await scicat_create_retrieval_job(dataset=dataset_pid, token=scicat_token_setup)

    # Verify Scicat Job status
    scicat_retrieval_job_status = await get_scicat_job(job_id=scicat_retrieval_job_id, token=scicat_token_setup)
    assert scicat_retrieval_job_status is not None
    assert scicat_retrieval_job_status.get("type") == "retrieve"
    assert scicat_retrieval_job_status.get(
        "statusMessage") == "jobCreated" or scicat_retrieval_job_status.get("statusMessage") == "inProgress"

    time.sleep(10)
    # Verify Prefect Flow
    retrieve_flow_run_id = await find_flow_in_prefect(scicat_retrieval_job_id)
    retrieval_state = await get_flow_result(retrieve_flow_run_id)
    assert retrieval_state is not None

    # Verify Scicat Job status
    scicat_retrieval_job_status = await get_scicat_job(job_id=scicat_retrieval_job_id, token=scicat_token_setup)
    assert scicat_retrieval_job_status is not None
    assert scicat_retrieval_job_status.get("type") == "retrieve"
    assert scicat_retrieval_job_status.get("statusMessage") == "finishedSuccessful"

    # Verify retrieved datablock in MINIO
    retrieved_datablock = minio_client.stat_object(
        bucket_name="retrieval", object_name=f"openem-network/datasets/{dataset_pid}/datablocks/{dataset_pid}_0.tar.gz")
    assert retrieved_datablock is not None

    # Verify Scicat datasetlifecycle
    dataset = await get_scicat_dataset(dataset_pid=dataset_pid, token=scicat_token_setup)
    assert dataset is not None
    dataset_lifecycle: Dict[Any, Any] = dataset.get("datasetlifecycle")
    assert dataset_lifecycle.get("retrieveStatusMessage") == "datasetRetrieved"
    # This is in fact a Scicat issue: fields in the datasetlifecycle are set to the default if not updated
    # https://github.com/SciCatProject/scicat-backend-next/blob/release-jobs/src/datasets/datasets.service.ts#L273
    # assert dataset_lifecycle.get("archiveStatusMessage") == "datasetOnArchiveDisk"
    assert not dataset_lifecycle.get("archivable")
    assert dataset_lifecycle.get("retrievable")
