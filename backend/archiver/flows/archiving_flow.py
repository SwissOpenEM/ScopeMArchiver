from prefect import flow, task, State, Task, Flow
from prefect.client.schemas.objects import TaskRun, FlowRun
from prefect.concurrency.sync import concurrency

from prefect.deployments.deployments import run_deployment
from functools import partial
from typing import List


from archiver.model import OrigDataBlock, DataBlock, Job
import archiver.datablocks as datablocks_operations
from archiver.scicat_tasks import update_scicat_dataset_lifecycle, update_scicat_job_status, register_datablocks, report_error, get_origdatablocks
from archiver.scicat_interface import SciCat


@task
def create_datablocks(dataset_id: int, origDataBlocks: List[OrigDataBlock]) -> List[DataBlock]:
    return datablocks_operations.create_datablocks(dataset_id, origDataBlocks)


@task
def move_data_to_LTS(dataset_id: int, datablocks: List[DataBlock]) -> None:
    with concurrency("archiving-lts", occupy=1):
        datablocks_operations.move_data_to_LTS(dataset_id, datablocks)


@task
def validate_data_in_LTS(datablocks: List[DataBlock]) -> None:
    datablocks_operations.validate_data_in_LTS(datablocks)


def on_create_datablocks_error(dataset_id: int, job_id: int, task: Task, task_run: TaskRun, state: State):
    # report error
    report_error(job_id=job_id, dataset_id=dataset_id)

    # cleanup files
    try:
        datablocks_operations.cleanup_scratch(dataset_id, "archival")
    except Exception as e:
        report_error(job_id=job_id, dataset_id=dataset_id, message=str(e))
    finally:
        datablocks_operations.cleanup_staging(dataset_id)


def on_validation_in_LTS_error(dataset_id: int, job_id: int, task: Task, task_run: TaskRun, state: State):
    # TODO: make async and add retries
    report_error(dataset_id, job_id)
    datablocks_operations.cleanup_lts_folder(dataset_id)


def on_move_data_to_LTS_error(dataset_id: int, job_id: int, task: Task, task_run: TaskRun, state: State):
    # TODO: make async and add retries
    report_error(dataset_id, job_id)
    datablocks_operations.cleanup_lts_folder(dataset_id)


def on_register_datablocks_error(dataset_id: int, job_id: int, task: Task, task_run: TaskRun, state: State):
    # TODO: make async and add retries
    report_error(dataset_id, job_id)
    # TODO: cleanup files


def on_flow_failure(flow: Flow, flow_run: FlowRun, state: State):
    pass
    # report_error(job_id=flow_run.parameters['job_id'], dataset_id=flow_run.parameters['dataset_id'])


@flow(name="move_datablocks_to_lts", log_prints=True, on_failure=[on_flow_failure])
def move_datablocks_to_lts(dataset_id: int, job_id: int, datablocks: List[DataBlock]):
    move_to_lts_result = move_data_to_LTS.with_options(
        on_failure=[partial(on_move_data_to_LTS_error, dataset_id, job_id)]).submit(
        dataset_id, datablocks=datablocks)

    validate_result = validate_data_in_LTS.with_options(
        on_failure=[partial(on_validation_in_LTS_error, dataset_id, job_id)]).submit(
        datablocks, wait_for=[move_to_lts_result])

    update_scicat_dataset_lifecycle(dataset_id=dataset_id, status=SciCat.ARCHIVESTATUSMESSAGE.DATASETONARCHIVEDISK,
                                    retrievable=True, wait_for=[validate_result])
    update_scicat_job_status(
        job_id, SciCat.JOBSTATUS.FINISHED_SUCCESSFULLY, wait_for=[validate_result])


@flow(name="archiving_flow", log_prints=True, on_failure=[on_flow_failure])
def archiving_flow(dataset_id: int, job_id: int):

    job_update = update_scicat_job_status.submit(
        job_id, SciCat.JOBSTATUS.IN_PROGRESS)
    dataset_update = update_scicat_dataset_lifecycle.submit(
        dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED)

    orig_datablocks = get_origdatablocks.submit(dataset_id, wait_for=[dataset_update, job_update])

    datablocks = create_datablocks.with_options(
        on_failure=[partial(on_create_datablocks_error, dataset_id, job_id)]).submit(
            dataset_id=dataset_id, origDataBlocks=orig_datablocks, wait_for=[job_update, dataset_update])

    register_result = register_datablocks.submit(datablocks, dataset_id)

    # run as subflow so this flow can be run separately as well
    move_datablocks_to_lts(dataset_id=dataset_id, job_id=job_id,
                           datablocks=datablocks, wait_for=[register_result])


def run_archiving_deployment(job: Job):
    run_deployment("archiving_flow/archival", parameters={
        "job_id": job.id,
        "dataset_id": job.datasetList[0].pid,
    }, timeout=0)
