
from typing import List
from functools import partial
import asyncio

from prefect import flow, task, State, Task, Flow
from prefect.client.schemas.objects import TaskRun, FlowRun
from prefect.concurrency.sync import concurrency
from prefect.deployments.deployments import run_deployment

from .utils import generate_flow_run_name_job_id, generate_task_run_name_dataset_id, generate_flow_run_name_dataset_id
from archiver.scicat.scicat_interface import SciCat
from archiver.scicat.scicat_tasks import update_scicat_job_status, update_scicat_dataset_lifecycle, get_origdatablocks, register_datablocks
from archiver.scicat.scicat_tasks import report_job_failure_system_error, report_dataset_system_error, report_dataset_user_error
from archiver.utils.datablocks import DatasetError
from archiver.utils.model import OrigDataBlock, DataBlock, Job
import archiver.utils.datablocks as datablocks_operations


# utilities
async def wait_for_free_space():
    while True:
        yield True
        await asyncio.sleep(1)
        print("Waiting for LTS...")


def report_dataset_error(dataset_id: int, state: State, task_run: TaskRun):
    try:
        state.result()
    except DatasetError:
        report_dataset_user_error(dataset_id)
    except SystemError:
        report_dataset_system_error(dataset_id)
    except Exception:
        # TODO: add some info about unknown errors
        report_dataset_system_error(dataset_id)


def on_get_origdatablocks_error(dataset_id: int, task: Task, task_run: TaskRun, state: State):
    report_dataset_user_error(dataset_id)


# Tasks
@task(task_run_name=generate_task_run_name_dataset_id)
def create_datablocks(dataset_id: int, origDataBlocks: List[OrigDataBlock]) -> List[DataBlock]:
    return datablocks_operations.create_datablocks(dataset_id, origDataBlocks)


@task(task_run_name=generate_task_run_name_dataset_id)
def move_data_to_LTS(dataset_id: int, datablock: DataBlock) -> str:
    with concurrency("move-datablocks-to-lts", occupy=2):
        return datablocks_operations.move_data_to_LTS(dataset_id, datablock)


@task
def verify_data_in_LTS(dataset_id: int, datablock: DataBlock, checksum: str) -> None:
    with concurrency("verify-datablocks-in-lts", occupy=1):
        datablocks_operations.verify_data_in_LTS(dataset_id, datablock, checksum)


# Flows
@flow(name="move_datablocks_to_lts", log_prints=True, flow_run_name=generate_flow_run_name_dataset_id)
async def move_datablock_to_lts_flow(dataset_id: int, datablock: DataBlock):

    # async for has_space in wait_for_free_space():
    #     if has_space:
    datablock_checksum = move_data_to_LTS.submit(
        dataset_id,
        datablock
    )
    # break

    verify_data_in_LTS.submit(
        dataset_id,
        datablock,
        datablock_checksum
    )


@flow(name="create_datablocks")
async def create_datablocks_flow(dataset_id: int):
    dataset_update = update_scicat_dataset_lifecycle.submit(
        dataset_id,
        SciCat.ARCHIVESTATUSMESSAGE.STARTED
    )

    orig_datablocks = get_origdatablocks.with_options(
        on_failure=[partial(on_get_origdatablocks_error, dataset_id)]
    ).submit(
        dataset_id,
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
    report_dataset_error(dataset_id=flow_run.parameters['dataset_id'], state=state, task_run=None)
    datablocks_operations.cleanup_lts_folder(flow_run.parameters['dataset_id'])
    datablocks_operations.cleanup_scratch(flow_run.parameters['dataset_id'])
    datablocks_operations.cleanup_staging(flow_run.parameters['dataset_id'])


def cleanup_dataset(flow: Flow, flow_run: FlowRun, state: State):
    datablocks_operations.cleanup_landingzone(flow_run.parameters['dataset_id'])
    datablocks_operations.cleanup_staging(flow_run.parameters['dataset_id'])
    datablocks_operations.cleanup_scratch(flow_run.parameters['dataset_id'])


@ flow(
    name="archive_dataset", log_prints=True, flow_run_name=generate_flow_run_name_dataset_id, on_failure=[on_dataset_flow_failure],
    on_completion=[cleanup_dataset])
async def archive_single_dataset_flow(dataset_id: int):

    datablocks = await create_datablocks_flow(dataset_id)

    try:
        await asyncio.gather(*[move_datablock_to_lts_flow(dataset_id=dataset_id, datablock=datablock)
                               for datablock in await datablocks.result(fetch=True)])
    except Exception as e:
        raise e

    update_scicat_dataset_lifecycle.submit(dataset_id=dataset_id,
                                           status=SciCat.ARCHIVESTATUSMESSAGE.DATASETONARCHIVEDISK,
                                           retrievable=True)


def on_job_flow_failure(flow: Flow, flow_run: FlowRun, state: State):
    # TODO: differrentiate user error
    report_job_failure_system_error(job_id=flow_run.parameters['job_id'])


@flow(name="archive_datasetlist", log_prints=True, flow_run_name=generate_flow_run_name_job_id, on_failure=[on_job_flow_failure])
async def archive_datasets_flow(dataset_ids: List[int], job_id: int):
    job_update = update_scicat_job_status.submit(
        job_id, SciCat.JOBSTATUS.IN_PROGRESS)
    job_update.wait()

    try:
        await asyncio.gather(*[archive_single_dataset_flow(id) for id in dataset_ids])
    except Exception as e:
        raise e

    update_scicat_job_status.submit(
        job_id, SciCat.JOBSTATUS.FINISHED_SUCCESSFULLY)


# Deployment function
async def run_archiving_deployment(job: Job):
    await run_deployment("archival/archive_datasetlist", parameters={
        "dataset_ids": [d.pid for d in job.datasetList or []],
        "job_id": job.id
    }, timeout=0)
