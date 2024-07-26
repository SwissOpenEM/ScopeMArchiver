import logging
import pytest
import requests
import prefect
from typing import Any
from uuid import UUID
from archiver.utils.model import Job, DatasetListEntry
from pydantic import SecretStr


from prefect.client.schemas.filters import (
    DeploymentFilter, FlowRunFilter
)
from prefect.client.schemas.objects import FlowRun
from prefect.client.schemas.sorting import FlowRunSort
from prefect.states import Scheduled
from prefect.blocks.system import Secret
from prefect.client.orchestration import PrefectClient

from prefect.flow_runs import wait_for_flow_run

EXTERNAL_BACKEND_SERVER_URL = "scopem-openem.ethz.ch"
BACKEND_API_PREFIX = "/api/v1"

SCICAT_BACKEND_ENDPOINT = "scopem-openem.ethz.ch:89"
SCICAT_BACKEND_API_PREFIX = "/api/v3"

PREFECT_SERVER_URL = "http://scopem-openem.ethz.ch/api"


CREATE_DATASET_PATH = "/new_dataset/"
JOB_PATH = "/jobs"

LTS_ROOT_PATH = "/tmp/LTS"

LOGGER = logging.getLogger(__name__)


def get_scicat_token(user: str = "ingestor", pw: str = "aman") -> SecretStr:

    resp = requests.post(url=f"http://{SCICAT_BACKEND_ENDPOINT}{SCICAT_BACKEND_API_PREFIX}/auth/login", json={
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
        url=f"http://{EXTERNAL_BACKEND_SERVER_URL}{BACKEND_API_PREFIX}{CREATE_DATASET_PATH}",
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
    dataset = await get_flow_result(new_dataset_flow_id)
    # assert dataset.state == COMPLETED
    return new_dataset_id


async def scicat_create_retrieve_job(dataset: str, token: SecretStr) -> UUID:
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
    response = requests.post(url=f"http://{SCICAT_BACKEND_ENDPOINT}{SCICAT_BACKEND_API_PREFIX}{JOB_PATH}",
                             data=job.model_dump_json(exclude_none=True),
                             headers=headers(token))
    response.raise_for_status()
    job_uuid: UUID = UUID(response.json()["id"])
    return job_uuid


async def scicat_create_archive_job(dataset: str, token: SecretStr) -> UUID:
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
    response = requests.post(url=f"http://{SCICAT_BACKEND_ENDPOINT}{SCICAT_BACKEND_API_PREFIX}{JOB_PATH}",
                             data=j,
                             headers=headers(token))
    response.raise_for_status()
    archive_job_uuid: UUID = UUID(response.json()["id"])
    return archive_job_uuid


async def get_flow_result(flow_run_id: UUID) -> Any:
    async with PrefectClient(api=PREFECT_SERVER_URL) as client:
        flow_run: FlowRun = await wait_for_flow_run(flow_run_id=flow_run_id, client=client)
        state = await client.read_flow_run(flow_run.id)
        return state.state


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
    # Making the POST request
    response = requests.post(url, json=payload, headers=headers)

    assert response.status_code == 200
    flow_run_ids = response.json()
    assert len(flow_run_ids) == 1
    return flow_run_ids[0]['id']


@pytest.mark.asyncio
async def test_end_to_end(scicat_token_setup, set_env):

    # Create and register dataset -> dataset pid
    dataset_pid = await create_dataset()
    # TODO: verify dataset in scicat
    # TODO: verify minio

    # trigger archive job in scicat
    scicat_job_id = await scicat_create_archive_job(dataset=dataset_pid, token=scicat_token_setup)
    # TODO: verify job in scicat

    import time
    time.sleep(10)
    archive_flow_run_id = await find_flow_in_prefect(scicat_job_id)

    # when done
    state = await get_flow_result(flow_run_id=archive_flow_run_id)
    LOGGER.info(f"archiving result {state}")

    # TODO: verify job in scicat
    # TODO: verify dataset in scicat
    # TODO: verify LTS? minio?

    # trigger retrieval job in scicat
    scicat_job_id = await scicat_create_retrieve_job(dataset=dataset_pid, token=scicat_token_setup)

    time.sleep(10)
    retrieve_flow_run_id = await find_flow_in_prefect(scicat_job_id)

    retrieve_state = await get_flow_result(retrieve_flow_run_id)
    LOGGER.info(f"archiving result {retrieve_state}")
    # TODO: verify job in scicat

    # when done
    # TODO: verify job in scicat
    # TODO: verify dataset in scicat (download urls)
    # TODO: verify data in minio

    # # TODO: get flow uuid
    # async with prefect.get_client() as client:
    #     resp = await client.hello()
    #     print(resp.json())

    #     new_dataset_deployment_name = ""

    #     # TODO: find flow by uuid
    #     flow_run = await client.read_flow_runs(
    #         flow_run_filter=FlowRunFilter(
    #             # state=dict(name=dict(any_=states)),
    #             # expected_start_time=dict(
    #             #     before_=datetime.now(timezone.utc)
    #             # ),
    #         ),

    #         deployment_filter=DeploymentFilter(
    #             name={'like_': new_dataset_deployment_name}
    #         ),
    #     )

    # TODO: verify minio

    # # trigger archiving flow
    # job = Job(
    #     jobParams={"username": "ingestor"},
    #     emailJobInitiator="testuser@testfacility.com",
    #     datasetList=[DatasetListEntry(pid=str(dataset_id), files=[])],
    #     type="archive",
    #     ownerGroup="ingestor",
    #     accessGroups=["ingestor"]
    # )
    # # TODO: this entry point needs alignment with SciCat
    # response = requests.post(url=f"http://{EXTERNAL_BACKEND_SERVER_URL}{API_PREFIX}{JOB_PATH}", json=job.model_dump_json(exclude_none=True))
    # response.raise_for_status()
    # archive_job_uuid: UUID = UUID(response.json()["uuid"])

    # archive_flow_run_id = await wait_for_flow_run(flow_run_id=archive_job_uuid)

    # job = Job(
    #     id=str(1234),
    #     type="retrieve",
    #     datasetList=[DatasetListEntry(pid=str(dataset_id), files=[""])]
    # )

    # response = requests.post(url=f"http://{EXTERNAL_BACKEND_SERVER_URL}{API_PREFIX}{JOB_PATH}", json=job.model_dump_json(exclude_none=True))
    # response.raise_for_status()
    # retrieve_job_uuid: UUID = UUID(response.json()["uuid"])
    # retrieve_flow_run = await wait_for_flow_run(flow_run_id=retrieve_job_uuid)

    # TODO: verify Scicat status

    # check archiving result
