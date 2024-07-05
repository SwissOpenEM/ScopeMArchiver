from typing import List
from functools import partial
import asyncio

from prefect import flow, task, State, Task, Flow
from prefect.client.schemas.objects import TaskRun, FlowRun
from prefect.deployments.deployments import run_deployment
from prefect.concurrency.sync import concurrency

from .task_utils import generate_flow_name_job_id, generate_task_name_dataset
from .utils import report_retrieval_error
from archiver.scicat.scicat_interface import SciCat
from archiver.utils.model import Job, DataBlock
from archiver.scicat.scicat_tasks import update_scicat_retrieval_job_status, update_scicat_retrieval_dataset_lifecycle
from archiver.scicat.scicat_tasks import report_job_failure_system_error, report_dataset_user_error, get_datablocks
import archiver.utils.datablocks as datablocks_operations


def on_get_datablocks_error(dataset_id: int, task: Task, task_run: TaskRun, state: State):
    report_dataset_user_error(dataset_id)


@task
def report_retrieved_datablocks(datablocks: List[DataBlock]):

    urls = datablocks_operations.create_presigned_urls(datablocks)
    for u in urls:
        print(u)


@task(task_run_name=generate_task_name_dataset, tags=["copy-from-LTS-to-retrieval"])
def copy_datablock_from_LTS_to_S3(dataset_id: int, datablock: DataBlock) -> str:
    datablocks_operations.copy_from_LTS_to_retrieval(dataset_id, datablock)


def on_dataset_flow_failure(flow: Flow, flow_run: FlowRun, state: State):

    report_retrieval_error(
        dataset_id=flow_run.parameters['dataset_id'], state=state, task_run=None)

    datablocks_operations.cleanup_scratch(flow_run.parameters['dataset_id'])
    datablocks_operations.cleanup_s3_retrieval(flow_run.parameters['dataset_id'])


def cleanup_dataset(flow: Flow, flow_run: FlowRun, state: State):
    datablocks_operations.cleanup_scratch(flow_run.parameters['dataset_id'])


@flow(name="retrieve_dataset", log_prints=True, on_failure=[on_dataset_flow_failure], on_completion=[cleanup_dataset])
async def retrieve_single_dataset_flow(dataset_id: int):
    dataset_update = update_scicat_retrieval_dataset_lifecycle.submit(
        dataset_id,
        SciCat.RETRIEVESTATUSMESSAGE.STARTED
    )

    datablocks = get_datablocks.with_options(
        on_failure=[partial(on_get_datablocks_error, dataset_id)]
    ).submit(
        dataset_id,
        wait_for=[dataset_update]
    )

    datablocks.wait()

    # check if on retrieval bucket
    datablocks_not_in_retrieval_bucket = datablocks.result()

    # check if enough space available in bucket
    retrieval_tasks = []
    for d in datablocks_not_in_retrieval_bucket:
        retrieval_tasks.append(move_datablock_from_LTS_to_S3.submit(dataset_id=dataset_id, datablock=d))

    report_task = report_retrieved_datablocks.submit(datablocks, wait_for=[retrieval_tasks])

    update_scicat_retrieval_dataset_lifecycle.submit(dataset_id=dataset_id,
                                                     status=SciCat.RETRIEVESTATUSMESSAGE.DATASET_RETRIEVED,
                                                     wait_for=report_task)


def on_job_flow_failure(flow: Flow, flow_run: FlowRun, state: State):
    # TODO: differrentiate user error
    report_job_failure_system_error(job_id=flow_run.parameters['job_id'], type=SciCat.JOBTYPE.RETRIEVE)


@ flow(name="retrieve_datasetlist", log_prints=True, flow_run_name=generate_flow_name_job_id, on_failure=[on_job_flow_failure])
async def retrieve_datasets_flow(dataset_ids: List[int], job_id: int):
    job_update = update_scicat_retrieval_job_status.submit(job_id, SciCat.JOBSTATUS.IN_PROGRESS)
    job_update.wait()

    try:
        for id in dataset_ids:
            await retrieve_single_dataset_flow(id)
    except Exception as e:
        raise e

    update_scicat_retrieval_job_status.submit(
        job_id, SciCat.JOBSTATUS.FINISHED_SUCCESSFULLY)


async def run_retrieval_deployment(job: Job):
    a = await asyncio.create_task(run_deployment("retrieve_datasetlist/dataset_retrieval", parameters={
        "dataset_ids": [d.pid for d in job.datasetList or []],
        "job_id": job.id
    }, timeout=0))
    return a
