import time
from typing import List
from functools import partial
import asyncio
from uuid import UUID
from pydantic import SecretStr


from prefect import flow, task, State, Task, Flow
from prefect.client.schemas.objects import TaskRun, FlowRun

from archiver.config.variables import Variables

from .utils import report_archival_error
from .task_utils import (
    generate_task_name_dataset,
    generate_flow_name_job_id,
    generate_subflow_run_name_job_id_dataset_id,
    generate_sleep_for_task_name
)
from archiver.scicat.scicat_interface import SciCatClient
from archiver.scicat.scicat_tasks import (
    update_scicat_archival_job_status,
    update_scicat_archival_dataset_lifecycle,
    get_origdatablocks,
    register_datablocks,
    get_scicat_access_token,
    get_job_datasetlist,
)
from archiver.scicat.scicat_tasks import (
    report_job_failure_system_error,
    report_dataset_user_error,
)
from archiver.utils.datablocks import wait_for_free_space
from archiver.utils.model import OrigDataBlock, DataBlock
import archiver.utils.datablocks as datablocks_operations
from archiver.config.concurrency_limits import ConcurrencyLimits
from archiver.utils.s3_storage_interface import get_s3_client
from archiver.utils.log import getLogger

def on_get_origdatablocks_error(dataset_id: str, task: Task, task_run: TaskRun, state: State):
    """Callback for get_origdatablocks tasks. Reports a user error."""
    scicat_token = get_scicat_access_token()
    report_dataset_user_error(dataset_id, token=scicat_token)


@task(task_run_name=generate_task_name_dataset)
def create_datablocks(dataset_id: str, origDataBlocks: List[OrigDataBlock]) -> List[DataBlock]:
    """Prefect task to create datablocks.

    Args:
        dataset_id (str): dataset id
        origDataBlocks (List[OrigDataBlock]): List of OrigDataBlocks (Pydantic Model)

    Returns:
        List[DataBlock]: List of DataBlocks (Pydantic Model)
    """

    s3_client = get_s3_client()
    return datablocks_operations.create_datablocks(s3_client, dataset_id, origDataBlocks)


@task(task_run_name=generate_sleep_for_task_name)
def sleep_for(time_in_seconds: int):
    """ Sleeps for a given amount of time. Required to wait for the LTS to update its internal state.
        Needs to be blocking as it should prevent the following task to run.
    """
    time.sleep(time_in_seconds)


@task(tags=[ConcurrencyLimits().LTS_FREE_TAG])
def check_free_space_in_LTS():
    """Prefect task to wait for free space in the LTS. Checks periodically if the condition for enough
    free space is fulfilled. Only one of these task runs at time; the others are only scheduled once this task
    has finished, i.e. there is enough space.
    """
    asyncio.run(wait_for_free_space())


@task(task_run_name=generate_task_name_dataset, tags=[ConcurrencyLimits().MOVE_TO_LTS_TAG])
def move_data_to_LTS(dataset_id: str, datablock: DataBlock):
    """Prefect task to move a datablock (.tar.gz file) to the LTS. Concurrency of this task is limited to 2 instances
    at the same time.
    """
    s3_client = get_s3_client()
    return datablocks_operations.move_data_to_LTS(s3_client, dataset_id, datablock)


@task(
    task_run_name=generate_task_name_dataset,
    tags=[ConcurrencyLimits().MOVE_TO_LTS_TAG],
    retries=5,
    retry_delay_seconds=[60, 120, 240, 480, 960],
)
def verify_checksum(dataset_id: str, datablock: DataBlock, checksum: str) -> None:
    """Prefect task to move a datablock (.tar.gz file) to the LTS. Concurrency of this task is limited to 2 instances
    at the same time.

    Exponential backoff for retries is implemented:  1*60s, 2*60s, 4*60s, 8*60s
    """
    return datablocks_operations.verify_checksum(
        dataset_id=dataset_id, datablock=datablock, expected_checksum=checksum
    )


@task(task_run_name=generate_task_name_dataset, tags=[ConcurrencyLimits().VERIFY_LTS_TAG])
def verify_data_in_LTS(dataset_id: str, datablock: DataBlock) -> None:
    """Prefect Task to verify a datablock in the LTS against a checksum. Task of this type run with no concurrency since the LTS
    does only allow limited concurrent access.
    """
    datablocks_operations.verify_data_in_LTS(dataset_id, datablock)


# Flows
@flow(
    name="move_datablocks_to_lts",
    log_prints=True,
    flow_run_name=generate_subflow_run_name_job_id_dataset_id,
)
def move_datablock_to_lts_flow(dataset_id: str, datablock: DataBlock):
    """Prefect (sub-)flow to move a datablock to the LTS. Implements the copying of data and verification via checksum.

    Args:
        dataset_id (str): _description_
        datablock (DataBlock): _description_
    """

    wait = check_free_space_in_LTS.submit()

    checksum = move_data_to_LTS.submit(dataset_id=dataset_id, datablock=datablock, wait_for=[wait])  # type: ignore
 
    getLogger().info(f"Wait {Variables().ARCHIVER_LTS_WAIT_BEFORE_VERIFY_S}s before verifying datablock")
    sleep = sleep_for.submit(Variables().ARCHIVER_LTS_WAIT_BEFORE_VERIFY_S, wait_for=[checksum])

    checksum_verification = verify_checksum.submit(
        dataset_id=dataset_id, datablock=datablock, checksum=checksum, wait_for=[sleep]
    )

    verify_data_in_LTS.submit(
        dataset_id=dataset_id, datablock=datablock, wait_for=[checksum_verification]
    ).result()  # type: ignore


@flow(name="create_datablocks", flow_run_name=generate_subflow_run_name_job_id_dataset_id)
def create_datablocks_flow(dataset_id: str, scicat_token: SecretStr) -> List[DataBlock]:
    """Prefect (sub-)flow to create datablocks (.tar.gz files) for files of a dataset and register them in Scicat.

    Args:
        dataset_id (str): Dataset id

    Returns:
        List[DataBlock]: List of created and registered datablocks
    """

    dataset_update = update_scicat_archival_dataset_lifecycle.submit(
        dataset_id=dataset_id,
        status=SciCatClient.ARCHIVESTATUSMESSAGE.STARTED,
        token=scicat_token,
    )

    orig_datablocks = get_origdatablocks.with_options(
        on_failure=[partial(on_get_origdatablocks_error, dataset_id)]
    ).submit(dataset_id=dataset_id, token=scicat_token, wait_for=[dataset_update])  # type: ignore

    datablocks_future = create_datablocks.submit(dataset_id=dataset_id, origDataBlocks=orig_datablocks)  # type: ignore

    register_datablocks.submit(
        datablocks=datablocks_future,  # type: ignore
        dataset_id=dataset_id,
        token=scicat_token,
    ).wait()

    return datablocks_future.result()


def on_dataset_flow_failure(flow: Flow, flow_run: FlowRun, state: State):
    scicat_token = get_scicat_access_token()
    report_archival_error(
        dataset_id=flow_run.parameters["dataset_id"],
        state=state,
        task_run=None,
        token=scicat_token,
    )
    datablocks_operations.cleanup_lts_folder(flow_run.parameters["dataset_id"])
    datablocks_operations.cleanup_scratch(flow_run.parameters["dataset_id"])
    try:
        s3_client = get_s3_client()
        datablocks_operations.cleanup_s3_staging(s3_client, flow_run.parameters["dataset_id"])
    except:
        pass


def cleanup_dataset(flow: Flow, flow_run: FlowRun, state: State):
    try:
        s3_client = get_s3_client()
        datablocks_operations.cleanup_s3_landingzone(s3_client, flow_run.parameters["dataset_id"])
        datablocks_operations.cleanup_s3_staging(s3_client, flow_run.parameters["dataset_id"])
    except:
        pass
    datablocks_operations.cleanup_scratch(flow_run.parameters["dataset_id"])


@flow(
    name="archive_dataset",
    log_prints=True,
    flow_run_name=generate_subflow_run_name_job_id_dataset_id,
    on_failure=[on_dataset_flow_failure],
    on_completion=[cleanup_dataset],
    on_cancellation=[on_dataset_flow_failure],
)
def archive_single_dataset_flow(dataset_id: str, scicat_token: SecretStr):
    try:
        datablocks = create_datablocks_flow(dataset_id, scicat_token=scicat_token)
    except Exception as e:
        raise e

    tasks = []

    for datablock in datablocks:
        wait = check_free_space_in_LTS.submit()

        checksum = move_data_to_LTS.submit(dataset_id=dataset_id, datablock=datablock, wait_for=[wait])  # type: ignore
    
        getLogger().info(f"Wait {Variables().ARCHIVER_LTS_WAIT_BEFORE_VERIFY_S}s before verifying datablock")
        sleep = sleep_for.submit(Variables().ARCHIVER_LTS_WAIT_BEFORE_VERIFY_S, wait_for=[checksum])

        checksum_verification = verify_checksum.submit(
            dataset_id=dataset_id, datablock=datablock, checksum=checksum, wait_for=[sleep]
        )

        w = verify_data_in_LTS.submit(
            dataset_id=dataset_id, datablock=datablock, wait_for=[checksum_verification]
        )  # type: ignore
        tasks.append(w)

    update_scicat_archival_dataset_lifecycle.submit(
        dataset_id=dataset_id,
        status=SciCatClient.ARCHIVESTATUSMESSAGE.DATASET_ON_ARCHIVEDISK,
        archivable=False,
        retrievable=True,
        token=scicat_token,
        wait_for=tasks
    ).result()


def on_job_flow_failure(flow: Flow, flow_run: FlowRun, state: State):
    token = get_scicat_access_token()
    # TODO: differrentiate user error
    report_job_failure_system_error(
        job_id=flow_run.parameters["job_id"],
        token=token,
    )


def on_job_flow_cancellation(flow: Flow, flow_run: FlowRun, state: State):
    dataset_ids = flow_run.parameters["dataset_ids"]

    try:
        s3_client = get_s3_client()
        for dataset_id in dataset_ids:
            datablocks_operations.cleanup_s3_staging(s3_client, dataset_id)
    except:
        pass

    for dataset_id in dataset_ids:
        datablocks_operations.cleanup_lts_folder(dataset_id)
        datablocks_operations.cleanup_scratch(dataset_id)

    token = get_scicat_access_token()

    report_job_failure_system_error(
        job_id=flow_run.parameters["job_id"],
        token=token,
    )


@flow(
    name="archive_datasetlist",
    log_prints=True,
    flow_run_name=generate_flow_name_job_id,
    on_failure=[on_job_flow_failure],
    on_cancellation=[on_job_flow_cancellation],
)
def archive_datasets_flow(job_id: UUID, dataset_ids: List[str] | None = None):
    """Prefect flow to archive a list of datasets. Corresponds to a "Job" in Scicat. Runs the individual archivals of the single datasets as subflows and reports
    the overall job status to Scicat.

    Args:
        dataset_ids (List[str]): _description_
        job_id (UUID): _description_

    Raises:
        e: _description_
    """
    dataset_ids: List[str] = dataset_ids or []
    access_token = get_scicat_access_token()

    job_update = update_scicat_archival_job_status.submit(
        job_id=job_id,
        status_code=SciCatClient.JOBSTATUSCODE.IN_PROGRESS,
        status_message=SciCatClient.JOBSTATUSMESSAGE.JOB_IN_PROGRESS,
        token=access_token,
    )
    job_update.result()

    if len(dataset_ids) == 0:
        dataset_ids_future = get_job_datasetlist.submit(job_id=job_id, token=access_token)
        dataset_ids = dataset_ids_future.result()

    try:
        for id in dataset_ids:
            archive_single_dataset_flow(dataset_id=id, scicat_token=access_token)
    except Exception as e:
        raise e

    update_scicat_archival_job_status.submit(
        job_id=job_id,
        status_code=SciCatClient.JOBSTATUSCODE.FINISHED_SUCCESSFULLY,
        status_message=SciCatClient.JOBSTATUSMESSAGE.JOB_FINISHED,
        token=access_token,
    ).result()
