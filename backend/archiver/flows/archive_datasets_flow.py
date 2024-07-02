
from typing import List
from functools import partial
import asyncio

from prefect import flow, task, State, Task, Flow
from prefect.client.schemas.objects import TaskRun, FlowRun
from prefect.concurrency.sync import concurrency
from prefect.deployments.deployments import run_deployment

from .utils import report_archival_error
from .task_utils import generate_task_name_dataset, generate_flow_name_job_id, generate_subflow_run_name_job_id_dataset_id
from archiver.scicat.scicat_interface import SciCat
from archiver.scicat.scicat_tasks import update_scicat_archival_job_status, update_scicat_archival_dataset_lifecycle, get_origdatablocks, register_datablocks
from archiver.scicat.scicat_tasks import report_job_failure_system_error, report_dataset_user_error
from archiver.utils.datablocks import wait_for_free_space
from archiver.utils.model import OrigDataBlock, DataBlock, Job
import archiver.utils.datablocks as datablocks_operations


def on_get_origdatablocks_error(dataset_id: int, task: Task, task_run: TaskRun, state: State):
    """Callback for get_origdatablocks tasks. Reports a user error.
    """
    report_dataset_user_error(dataset_id)


# Tasks
@task(task_run_name=generate_task_name_dataset)
def create_datablocks(dataset_id: int, origDataBlocks: List[OrigDataBlock]) -> List[DataBlock]:
    """Prefect task to create datablocks. 

    Args:
        dataset_id (int): dataset id
        origDataBlocks (List[OrigDataBlock]): List of OrigDataBlocks (Pydantic Model)

    Returns:
        List[DataBlock]: List of DataBlocks (Pydantic Model)
    """
    return datablocks_operations.create_datablocks(dataset_id, origDataBlocks)


@task
def check_free_space_in_LTS():
    """ Prefect task to wait for free space in the LTS. Checks periodically if the condition for enough
    free space is fulfilled. Only one of these task runs at time; the others are only scheduled once this task
    has finished, i.e. there is enough space.
    """
    with concurrency("wait-for-free-space-in-lts", occupy=1):
        asyncio.run(wait_for_free_space())


@task(task_run_name=generate_task_name_dataset)
def move_data_to_LTS(dataset_id: int, datablock: DataBlock) -> str:
    """ Prefect task to move a datablock (.tar.gz file) to the LTS. Concurrency of this task is limited to 2 instances
    at the same time.
    """
    with concurrency("move-datablocks-to-lts", occupy=2):
        return datablocks_operations.move_data_to_LTS(dataset_id, datablock)


@task(task_run_name=generate_task_name_dataset)
def verify_data_in_LTS(dataset_id: int, datablock: DataBlock, checksum: str) -> None:
    """ Prefect Task to verify a datablock in the LTS against a checksum. Task of this type run with no concurrency since the LTS
    does only allow limited concurrent access.
    """
    with concurrency("verify-datablocks-in-lts", occupy=1):
        datablocks_operations.verify_data_in_LTS(
            dataset_id, datablock, checksum)


# Flows
@flow(name="move_datablocks_to_lts", log_prints=True, flow_run_name=generate_subflow_run_name_job_id_dataset_id)
async def move_datablock_to_lts_flow(dataset_id: int, datablock: DataBlock):
    """Prefect (sub-)flow to move a datablock to the LTS. Implements the copying of data and verification via checksum.

    Args:
        dataset_id (int): _description_
        datablock (DataBlock): _description_
    """

    wait = check_free_space_in_LTS.submit()

    datablock_checksum = move_data_to_LTS.submit(
        dataset_id=dataset_id,
        datablock=datablock,
        wait_for=[wait]
    )

    verify_data_in_LTS.submit(
        dataset_id=dataset_id,
        datablock=datablock,
        checksum=datablock_checksum
    )


@flow(name="create_datablocks", flow_run_name=generate_subflow_run_name_job_id_dataset_id)
async def create_datablocks_flow(dataset_id: int) -> List[DataBlock]:
    """Prefect (sub-)flow to create datablocks (.tar.gz files) for files of a dataset and register them in Scicat.

    Args:
        dataset_id (int): Dataset id

    Returns:
        List[DataBlock]: List of created and registered datablocks
    """
    dataset_update = update_scicat_archival_dataset_lifecycle.submit(
        dataset_id=dataset_id,
        status=SciCat.ARCHIVESTATUSMESSAGE.STARTED
    )

    orig_datablocks = get_origdatablocks.with_options(
        on_failure=[partial(on_get_origdatablocks_error, dataset_id)]
    ).submit(
        dataset_id=dataset_id,
        wait_for=[dataset_update]
    )

    datablocks = create_datablocks.submit(
        dataset_id=dataset_id,
        origDataBlocks=orig_datablocks
    )

    register_datablocks.submit(
        datablocks=datablocks,
        dataset_id=dataset_id
    )

    return datablocks


def on_dataset_flow_failure(flow: Flow, flow_run: FlowRun, state: State):
    report_archival_error(
        dataset_id=flow_run.parameters['dataset_id'], state=state, task_run=None)
    datablocks_operations.cleanup_lts_folder(flow_run.parameters['dataset_id'])
    datablocks_operations.cleanup_scratch(flow_run.parameters['dataset_id'])
    datablocks_operations.cleanup_s3_staging(flow_run.parameters['dataset_id'])


def cleanup_dataset(flow: Flow, flow_run: FlowRun, state: State):
    datablocks_operations.cleanup_s3_landingzone(
        flow_run.parameters['dataset_id'])
    datablocks_operations.cleanup_s3_staging(flow_run.parameters['dataset_id'])
    datablocks_operations.cleanup_scratch(flow_run.parameters['dataset_id'])


@flow(name="archive_dataset", log_prints=True, flow_run_name=generate_subflow_run_name_job_id_dataset_id,
      on_failure=[on_dataset_flow_failure],
      on_completion=[cleanup_dataset])
async def archive_single_dataset_flow(dataset_id: int):

    try:
        datablocks = await create_datablocks_flow(dataset_id)
    except Exception as e:
        raise e

    try:
        for datablock in await datablocks.result(fetch=True):
            await move_datablock_to_lts_flow(dataset_id=dataset_id, datablock=datablock)
    except Exception as e:
        raise e

    update_scicat_archival_dataset_lifecycle.submit(dataset_id=dataset_id,
                                                    status=SciCat.ARCHIVESTATUSMESSAGE.DATASET_ON_ARCHIVEDISK,
                                                    retrievable=True)


def on_job_flow_failure(flow: Flow, flow_run: FlowRun, state: State):
    # TODO: differrentiate user error
    report_job_failure_system_error(job_id=flow_run.parameters['job_id'], type=SciCat.JOBTYPE.ARCHIVE)


@flow(name="archive_datasetlist", log_prints=True, flow_run_name=generate_flow_name_job_id, on_failure=[on_job_flow_failure])
async def archive_datasets_flow(dataset_ids: List[int], job_id: int):
    """Prefect flow to archive a list of datasets. Corresponds to a "Job" in Scicat. Runs the individual archivals of the single datasets as subflows and reports
    the overall job status to Scicat.

    Args:
        dataset_ids (List[int]): _description_
        job_id (int): _description_

    Raises:
        e: _description_
    """
    job_update = update_scicat_archival_job_status.submit(
        job_id=job_id, status=SciCat.JOBSTATUS.IN_PROGRESS)
    job_update.wait()

    try:
        for id in dataset_ids:
            await archive_single_dataset_flow(dataset_id=id)
    except Exception as e:
        raise e

    update_scicat_archival_job_status.submit(
        job_id=job_id, status=SciCat.JOBSTATUS.FINISHED_SUCCESSFULLY)


# Deployment function
async def run_archiving_deployment(job: Job):
    a = await asyncio.create_task(run_deployment("archive_datasetlist/datasets_archival", parameters={
        "dataset_ids": [d.pid for d in job.datasetList or []],
        "job_id": job.id
    }, timeout=0))
    return a
