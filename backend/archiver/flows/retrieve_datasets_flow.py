from typing import List
from functools import partial
from uuid import UUID
from pydantic import SecretStr

from prefect import flow, task, State, Task, Flow
from prefect.client.schemas.objects import TaskRun, FlowRun

from archiver.utils.s3_storage_interface import get_s3_client


from .task_utils import generate_flow_name_job_id, generate_task_name_dataset
from .utils import report_retrieval_error
from archiver.scicat.scicat_interface import SciCatClient
from archiver.utils.model import DataBlock, JobResultObject
from archiver.scicat.scicat_tasks import update_scicat_retrieval_job_status, update_scicat_retrieval_dataset_lifecycle, get_scicat_access_token, get_job_datasetlist, create_job_result_object_task
from archiver.scicat.scicat_tasks import report_job_failure_system_error, report_dataset_user_error, get_datablocks
from archiver.config.concurrency_limits import ConcurrencyLimits
import archiver.utils.datablocks as datablocks_operations


def on_get_datablocks_error(dataset_id: str, task: Task, task_run: TaskRun, state: State):
    scicat_token = get_scicat_access_token()
    report_dataset_user_error(dataset_id, token=scicat_token)


@task(task_run_name=generate_task_name_dataset, tags=[ConcurrencyLimits().LTS_TO_RETRIEVAL_TAG])
def copy_datablock_from_LTS_to_S3(dataset_id: str, datablock: DataBlock):
    s3_client = get_s3_client()
    datablocks_operations.copy_from_LTS_to_retrieval(s3_client, dataset_id, datablock)


def on_dataset_flow_failure(flow: Flow, flow_run: FlowRun, state: State):
    datablocks_operations.cleanup_scratch(flow_run.parameters['dataset_id'])
    s3_client = get_s3_client()
    datablocks_operations.cleanup_s3_retrieval(s3_client, flow_run.parameters['dataset_id'])

    scicat_token = get_scicat_access_token()

    report_retrieval_error(
        dataset_id=flow_run.parameters['dataset_id'], state=state, task_run=None, token=scicat_token)


def cleanup_dataset(flow: Flow, flow_run: FlowRun, state: State):
    datablocks_operations.cleanup_scratch(flow_run.parameters['dataset_id'])


@flow(name="retrieve_dataset", log_prints=True, on_failure=[on_dataset_flow_failure], on_completion=[cleanup_dataset])
def retrieve_single_dataset_flow(dataset_id: str, job_id: UUID, scicat_token: SecretStr):
    dataset_update = update_scicat_retrieval_dataset_lifecycle.submit(
        dataset_id=dataset_id,
        status=SciCatClient.RETRIEVESTATUSMESSAGE.STARTED,
        token=scicat_token
    )

    datablocks = get_datablocks.with_options(
        on_failure=[partial(on_get_datablocks_error, dataset_id)]
    ).submit(
        dataset_id=dataset_id,
        token=scicat_token,
        wait_for=[dataset_update]
    )  # type: ignore

    # TODO: check if on retrieval bucket
    datablocks_not_in_retrieval_bucket = datablocks.result()

    # TODO: check if enough space available in bucket
    retrieval_tasks = []
    for d in datablocks_not_in_retrieval_bucket:
        retrieval_tasks.append(copy_datablock_from_LTS_to_S3.submit(dataset_id=dataset_id, datablock=d))

    update_scicat_retrieval_dataset_lifecycle.submit(dataset_id=dataset_id,
                                                     status=SciCatClient.RETRIEVESTATUSMESSAGE.DATASET_RETRIEVED,
                                                     token=scicat_token,
                                                     wait_for=retrieval_tasks).wait()  # type: ignore


def on_job_flow_failure(flow: Flow, flow_run: FlowRun, state: State):
    scicat_token = get_scicat_access_token()
    # TODO: differrentiate user error
    report_job_failure_system_error(job_id=flow_run.parameters['job_id'], type=SciCatClient.JOBTYPE.RETRIEVE, token=scicat_token)


@ flow(name="retrieve_datasetlist", log_prints=True, flow_run_name=generate_flow_name_job_id, on_failure=[on_job_flow_failure])
def retrieve_datasets_flow(job_id: UUID, dataset_ids: List[str] | None = None):
    dataset_ids = dataset_ids or []

    access_token_future = get_scicat_access_token.submit()
    access_token = access_token_future.result()

    job_update = update_scicat_retrieval_job_status.submit(
        job_id=job_id, status=SciCatClient.JOBSTATUS.IN_PROGRESS, jobResultObject=None, token=access_token)
    job_update.result()

    if len(dataset_ids) == 0:
        dataset_ids_future = get_job_datasetlist.submit(job_id=job_id, token=access_token)
        dataset_ids = dataset_ids_future.result()

    try:
        for id in dataset_ids:
            f = retrieve_single_dataset_flow(dataset_id=id, job_id=job_id, scicat_token=access_token)
            print(f)
    except Exception as e:
        raise e

    job_results_future = create_job_result_object_task.submit(
        dataset_ids=dataset_ids)
    job_results = job_results_future.result()
    job_results_object = JobResultObject(result=job_results)

    update_scicat_retrieval_job_status.submit(
        job_id=job_id,
        status=SciCatClient.JOBSTATUS.FINISHED_SUCCESSFULLY,
        jobResultObject=job_results_object,
        token=access_token).result()
