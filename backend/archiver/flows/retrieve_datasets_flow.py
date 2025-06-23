from typing import List
from functools import partial
from uuid import UUID
import uuid
from pydantic import SecretStr

from prefect import flow, get_client, task, State, Task, Flow
from prefect.client.schemas.objects import TaskRun, FlowRun
from prefect.client.schemas.sorting import FlowRunSort
from prefect.client.schemas.filters import FlowRunFilter
from prefect.flow_runs import wait_for_flow_run
from prefect.context import get_run_context
from archiver.utils.s3_storage_interface import get_s3_client
from archiver.utils.s3_storage_interface import Bucket


from .task_utils import generate_flow_name_dataset, generate_flow_name_job_id, generate_task_name_dataset
from .utils import report_retrieval_error
from archiver.scicat.scicat_interface import SciCatClient
from archiver.utils.model import DataBlock, JobResultObject
from archiver.scicat.scicat_tasks import (
    update_scicat_retrieval_job_status,
    update_scicat_retrieval_dataset_lifecycle,
    get_scicat_access_token,
    get_job_datasetlist,
    create_job_result_object_task,
)
from archiver.scicat.scicat_tasks import (
    report_job_failure_system_error,
    report_dataset_user_error,
    get_datablocks,
)
from archiver.config.concurrency_limits import ConcurrencyLimits
import archiver.utils.datablocks as datablocks_operations


def on_get_datablocks_error(dataset_id: str, task: Task, task_run: TaskRun, state: State):
    scicat_token = get_scicat_access_token()
    report_dataset_user_error(dataset_id, token=scicat_token)


@task(
    task_run_name=generate_task_name_dataset,
    tags=[ConcurrencyLimits().LTS_READ_TAG],
)
def copy_datablock_from_LTS_to_scratch(dataset_id: str, datablock: DataBlock):
    datablocks_operations.copy_from_LTS_to_scratch_retrieval(dataset_id, datablock)


@task(
    task_run_name=generate_task_name_dataset,
)
def verify_data_on_scratch(dataset_id: str, datablock: DataBlock):
    datablocks_operations.verify_datablock_on_scratch(dataset_id, datablock)


@task(
    task_run_name=generate_task_name_dataset,
)
def upload_data_to_s3(dataset_id: str, datablock: DataBlock):
    s3_client = get_s3_client()
    datablocks_operations.upload_data_to_retrieval_bucket(s3_client, dataset_id, datablock)


def on_dataset_flow_failure(flow: Flow, flow_run: FlowRun, state: State):
    datablocks_operations.cleanup_scratch(flow_run.parameters["dataset_id"])
    s3_client = get_s3_client()
    datablocks_operations.cleanup_s3_retrieval(s3_client, flow_run.parameters["dataset_id"])

    scicat_token = get_scicat_access_token()

    report_retrieval_error(
        dataset_id=flow_run.parameters["dataset_id"],
        state=state,
        task_run=None,
        token=scicat_token,
    )


def cleanup_dataset(flow: Flow, flow_run: FlowRun, state: State):
    datablocks_operations.cleanup_scratch(flow_run.parameters["dataset_id"])


@task()
def find_missing_datablocks_in_s3(datablocks: List[DataBlock], bucket=Bucket("retrieval")) -> List[DataBlock]:
    s3_client = get_s3_client()
    return datablocks_operations.find_missing_datablocks_in_s3(client=s3_client, datablocks=datablocks, bucket=bucket)


@task()
def reset_expiry_date(all_datablocks: List[DataBlock], missing_datablocks: List[DataBlock], bucket=Bucket("retrieval")):
    s3_client = get_s3_client()
    filenames = list(set(d.archiveId for d in all_datablocks) - set(d.archiveId for d in missing_datablocks))

    datablocks_operations.reset_expiry_date(client=s3_client, filenames=filenames, bucket=bucket)


@flow(
    name="retrieve_dataset",
    flow_run_name=generate_flow_name_dataset,
    log_prints=True,
    on_failure=[on_dataset_flow_failure],
    on_completion=[cleanup_dataset],
)
def retrieve_single_dataset_flow(dataset_id: str, job_id: UUID):
    scicat_token = get_scicat_access_token.submit()

    dataset_update = update_scicat_retrieval_dataset_lifecycle.submit(
        dataset_id=dataset_id,
        status=SciCatClient.RETRIEVESTATUSMESSAGE.STARTED,
        token=scicat_token,
    )

    datablocks = get_datablocks.with_options(
        on_failure=[partial(on_get_datablocks_error, dataset_id)]
    ).submit(dataset_id=dataset_id, token=scicat_token, wait_for=[dataset_update])  # type: ignore

    missing_datablocks = find_missing_datablocks_in_s3.submit(datablocks=datablocks)

    retrieval_tasks = []
    retrieval_tasks.append(reset_expiry_date.submit(all_datablocks=datablocks, missing_datablocks=missing_datablocks))

    # TODO: check if enough space available in bucket
    # https://github.com/SwissOpenEM/ScopeMArchiver/issues/169

    # The error does not propagate correctly through the dependent tasks
    # https://github.com/PrefectHQ/prefect/issues/12028
    for datablock in missing_datablocks.result():
        copy_to_scratch = copy_datablock_from_LTS_to_scratch.submit(dataset_id=dataset_id, datablock=datablock)

        verify_datablock = verify_data_on_scratch.submit(
            dataset_id=dataset_id, datablock=datablock, wait_for=[copy_to_scratch]
        )
        upload_data = upload_data_to_s3.submit(
            dataset_id=dataset_id, datablock=datablock, wait_for=[verify_datablock]
        )
        retrieval_tasks.append(upload_data)

    scicat_token = get_scicat_access_token.submit(wait_for=retrieval_tasks)

    update_scicat_retrieval_dataset_lifecycle.submit(
        dataset_id=dataset_id,
        status=SciCatClient.RETRIEVESTATUSMESSAGE.DATASET_RETRIEVED,
        token=scicat_token,
        wait_for=retrieval_tasks
    ).result()  # type: ignore


def on_job_flow_failure(flow: Flow, flow_run: FlowRun, state: State):
    scicat_token = get_scicat_access_token()
    # TODO: differrentiate user error
    report_job_failure_system_error(
        job_id=flow_run.parameters["job_id"],
        token=scicat_token,
    )


def find_oldest_dataset_flow(dataset_id: str, prefix: str = "retrieve_dataset", state: str = "Running") -> List[FlowRun]:
    this_run_id = get_run_context().flow_run.id
    with get_client(sync_client=True) as client:
        flow_runs = client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                id={'not_any_': [this_run_id]},
                name={'like_': f"{prefix}-dataset_id-{dataset_id}"},
                state=dict(name=dict(any_=[state, "Scheduled"])),
            ),
            sort=FlowRunSort.START_TIME_DESC
        )
        return flow_runs[0].id if len(flow_runs) > 0 else None
    return None


@flow(
    name="wait_for_retrieval_flow",
    log_prints=True,
    on_failure=[on_job_flow_failure],
)
async def wait_for_retrieval_flow(flow_run_id: uuid.UUID):
    flow_run: FlowRun = await wait_for_flow_run(flow_run_id, log_states=True)
    flow_run.state.result()


@flow(
    name="retrieve_datasetlist",
    log_prints=True,
    flow_run_name=generate_flow_name_job_id,
    on_failure=[on_job_flow_failure],
)
async def retrieve_datasets_flow(job_id: UUID):

    access_token = get_scicat_access_token.submit()

    job_update = update_scicat_retrieval_job_status.submit(
        job_id=job_id,
        status_code=SciCatClient.JOBSTATUSCODE.IN_PROGRESS,
        status_message=SciCatClient.JOBSTATUSMESSAGE.JOB_IN_PROGRESS,
        jobResultObject=None,
        token=access_token,
    )

    dataset_ids_future = get_job_datasetlist.submit(job_id=job_id, token=access_token, wait_for=[job_update])
    dataset_ids = dataset_ids_future.result()

    for id in dataset_ids:
        existing_run_id = find_oldest_dataset_flow(dataset_id=id)
        if existing_run_id is None:
            retrieve_single_dataset_flow(dataset_id=id, job_id=job_id)
        else:
            await wait_for_retrieval_flow(existing_run_id)

    job_results_future = create_job_result_object_task.submit(dataset_ids=dataset_ids)
    job_results = job_results_future.result()
    job_results_object = JobResultObject(result=job_results)

    access_token = get_scicat_access_token.submit(wait_for=[job_results_future])

    update_scicat_retrieval_job_status.submit(
        job_id=job_id,
        status_code=SciCatClient.JOBSTATUSCODE.FINISHED_SUCCESSFULLY,
        status_message=SciCatClient.JOBSTATUSMESSAGE.JOB_FINISHED,
        jobResultObject=job_results_object,
        token=access_token,
    ).wait()
