
from typing import List
from functools import partial
import asyncio
from uuid import UUID
from pydantic import SecretStr


from prefect import flow, task, State, Task, Flow
from prefect.futures import PrefectFuture
from prefect.utilities.asyncutils import Async
from prefect.client.schemas.objects import TaskRun, FlowRun

from .utils import report_archival_error
from .task_utils import generate_task_name_dataset, generate_flow_name_job_id, generate_subflow_run_name_job_id_dataset_id
from archiver.scicat.scicat_interface import SciCatClient
from archiver.scicat.scicat_tasks import update_scicat_archival_job_status, update_scicat_archival_dataset_lifecycle, get_origdatablocks, register_datablocks, get_scicat_access_token, get_job_datasetlist
from archiver.scicat.scicat_tasks import report_job_failure_system_error, report_dataset_user_error
from archiver.utils.datablocks import wait_for_free_space
from archiver.utils.model import OrigDataBlock, DataBlock
import archiver.utils.datablocks as datablocks_operations
from archiver.config.concurrency_limits import ConcurrencyLimits


def on_get_origdatablocks_error(dataset_id: str, task: Task, task_run: TaskRun, state: State):
    """Callback for get_origdatablocks tasks. Reports a user error.
    """
    scicat_token = get_scicat_access_token()
    report_dataset_user_error(dataset_id, token=scicat_token)


# Tasks
@task(task_run_name=generate_task_name_dataset)
def create_datablocks(dataset_id: str, origDataBlocks: List[OrigDataBlock]) -> List[DataBlock]:
    """Prefect task to create datablocks.

    Args:
        dataset_id (str): dataset id
        origDataBlocks (List[OrigDataBlock]): List of OrigDataBlocks (Pydantic Model)

    Returns:
        List[DataBlock]: List of DataBlocks (Pydantic Model)
    """
    return datablocks_operations.create_datablocks(dataset_id, origDataBlocks)


@task(tags=[ConcurrencyLimits().LTS_FREE_TAG])
def check_free_space_in_LTS():
    """ Prefect task to wait for free space in the LTS. Checks periodically if the condition for enough
    free space is fulfilled. Only one of these task runs at time; the others are only scheduled once this task
    has finished, i.e. there is enough space.
    """
    asyncio.run(wait_for_free_space())


@task(task_run_name=generate_task_name_dataset, tags=[ConcurrencyLimits().MOVE_TO_LTS_TAG])
def move_data_to_LTS(dataset_id: str, datablock: DataBlock):
    """ Prefect task to move a datablock (.tar.gz file) to the LTS. Concurrency of this task is limited to 2 instances
    at the same time.
    """
    return datablocks_operations.move_data_to_LTS(dataset_id, datablock)


@task(task_run_name=generate_task_name_dataset, tags=[ConcurrencyLimits().VERIFY_LTS_TAG])
def verify_data_in_LTS(dataset_id: str, datablock: DataBlock) -> None:
    """ Prefect Task to verify a datablock in the LTS against a checksum. Task of this type run with no concurrency since the LTS
    does only allow limited concurrent access.
    """
    datablocks_operations.verify_data_in_LTS(
        dataset_id, datablock)


# Flows
@flow(name="move_datablocks_to_lts", log_prints=True, flow_run_name=generate_subflow_run_name_job_id_dataset_id)
async def move_datablock_to_lts_flow(dataset_id: str, datablock: DataBlock):
    """Prefect (sub-)flow to move a datablock to the LTS. Implements the copying of data and verification via checksum.

    Args:
        dataset_id (str): _description_
        datablock (DataBlock): _description_
    """

    wait = check_free_space_in_LTS.submit()

    move_data = move_data_to_LTS.submit(
        dataset_id=dataset_id,
        datablock=datablock,
        wait_for=[wait]
    )

    verify_data_in_LTS.submit(
        dataset_id=dataset_id,
        datablock=datablock,
        wait_for=[move_data]
    ).result()


@flow(name="create_datablocks", flow_run_name=generate_subflow_run_name_job_id_dataset_id)
async def create_datablocks_flow(dataset_id: str, scicat_token: SecretStr) -> List[DataBlock]:
    """Prefect (sub-)flow to create datablocks (.tar.gz files) for files of a dataset and register them in Scicat.

    Args:
        dataset_id (str): Dataset id

    Returns:
        List[DataBlock]: List of created and registered datablocks
    """

    dataset_update = update_scicat_archival_dataset_lifecycle.submit(
        dataset_id=dataset_id,
        status=SciCatClient.ARCHIVESTATUSMESSAGE.STARTED,
        token=scicat_token
    )
    # dataset_update.result()

    orig_datablocks = get_origdatablocks.with_options(
        on_failure=[partial(on_get_origdatablocks_error, dataset_id)]
    ).submit(
        dataset_id=dataset_id,
        token=scicat_token,
        wait_for=[dataset_update]
    )

    datablocks_future = create_datablocks.submit(
        dataset_id=dataset_id,
        origDataBlocks=orig_datablocks
    )

    register_datablocks.submit(
        datablocks=datablocks_future,
        dataset_id=dataset_id,
        token=scicat_token
    ).wait()

    return datablocks_future.result()


def on_dataset_flow_failure(flow: Flow, flow_run: FlowRun, state: State):
    scicat_token = get_scicat_access_token()
    report_archival_error(
        dataset_id=flow_run.parameters['dataset_id'], state=state, task_run=None, token=scicat_token)
    datablocks_operations.cleanup_lts_folder(flow_run.parameters['dataset_id'])
    datablocks_operations.cleanup_scratch(flow_run.parameters['dataset_id'])
    datablocks_operations.cleanup_s3_staging(flow_run.parameters['dataset_id'])


def cleanup_dataset(flow: Flow, flow_run: FlowRun, state: State):
    datablocks_operations.cleanup_s3_landingzone(
        flow_run.parameters['dataset_id'])
    datablocks_operations.cleanup_s3_staging(flow_run.parameters['dataset_id'])
    datablocks_operations.cleanup_scratch(flow_run.parameters['dataset_id'])


@ flow(name="archive_dataset", log_prints=True, flow_run_name=generate_subflow_run_name_job_id_dataset_id,
       on_failure=[on_dataset_flow_failure],
       on_completion=[cleanup_dataset],
       on_cancellation=[on_dataset_flow_failure]
       )
async def archive_single_dataset_flow(dataset_id: str, scicat_token: SecretStr):

    try:
        datablocks = await create_datablocks_flow(dataset_id, scicat_token=scicat_token)
    except Exception as e:
        raise e

    try:
        for datablock in datablocks:
            await move_datablock_to_lts_flow(dataset_id=dataset_id, datablock=datablock)
    except Exception as e:
        raise e

    update_scicat_archival_dataset_lifecycle.submit(dataset_id=dataset_id,
                                                    status=SciCatClient.ARCHIVESTATUSMESSAGE.DATASET_ON_ARCHIVEDISK,
                                                    archivable=False,
                                                    retrievable=True,
                                                    token=scicat_token).result()


def on_job_flow_failure(flow: Flow, flow_run: FlowRun, state: State):
    # Getting the token here should just fetch it from the cache
    token = get_scicat_access_token()
    # TODO: differrentiate user error
    report_job_failure_system_error(job_id=flow_run.parameters['job_id'], type=SciCatClient.JOBTYPE.ARCHIVE, token=token)


def on_job_flow_cancellation(flow: Flow, flow_run: FlowRun, state: State):

    dataset_ids = flow_run.parameters['dataset_ids']

    for dataset_id in dataset_ids:
        datablocks_operations.cleanup_lts_folder(dataset_id)
        datablocks_operations.cleanup_scratch(dataset_id)
        datablocks_operations.cleanup_s3_staging(dataset_id)

    # Getting the token here should just fetch it from the cache
    token = get_scicat_access_token()

    report_job_failure_system_error(job_id=flow_run.parameters['job_id'], type=SciCatClient.JOBTYPE.ARCHIVE, token=token)


@flow(
    name="archive_datasetlist", log_prints=True,
    flow_run_name=generate_flow_name_job_id,
    on_failure=[on_job_flow_failure],
    on_cancellation=[on_job_flow_cancellation])
async def archive_datasets_flow(job_id: UUID, dataset_ids: List[str] | None = None):
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
        job_id=job_id, status=SciCatClient.JOBSTATUS.IN_PROGRESS, token=access_token)
    job_update.result()

    if len(dataset_ids) == 0:
        dataset_ids_future = get_job_datasetlist.submit(job_id=job_id, token=access_token)
        dataset_ids = dataset_ids_future.result()

    try:
        for id in dataset_ids:
            await archive_single_dataset_flow(dataset_id=id, scicat_token=access_token)
    except Exception as e:
        raise e

    update_scicat_archival_job_status.submit(
        job_id=job_id, status=SciCatClient.JOBSTATUS.FINISHED_SUCCESSFULLY, token=access_token).result()
