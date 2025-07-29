import math
from pathlib import Path
import time
from typing import List
from functools import partial
import asyncio
from uuid import UUID


from prefect import flow, task, State, Task, Flow
from prefect.client.schemas.objects import TaskRun, FlowRun
from prefect.futures import wait as wait_for_futures
from prefect.states import Failed
from prefect.artifacts import (
    create_progress_artifact,
    update_progress_artifact,
)

from config.variables import Variables
from utils.datablocks import ArchiveInfo

from .flow_utils import StoragePaths, report_archival_error
from .task_utils import (
    generate_task_name_dataset,
    generate_flow_name_job_id,
    generate_subflow_run_name_job_id_dataset_id,
    generate_sleep_for_task_name
)
from scicat.scicat_interface import SciCatClient
from scicat.scicat_tasks import (
    update_scicat_archival_job_status,
    update_scicat_archival_dataset_lifecycle,
    get_origdatablocks,
    register_datablocks,
    get_scicat_access_token,
    get_job_datasetlist,
    reset_dataset
)
from scicat.scicat_tasks import (
    report_job_failure_system_error,
    report_dataset_user_error
)

from utils.datablocks import wait_for_free_space
from utils.model import OrigDataBlock, DataBlock
import utils.datablocks as datablocks_operations
from config.concurrency_limits import ConcurrencyLimits
from utils.s3_storage_interface import Bucket, get_s3_client
from utils.log import getLogger


def on_get_origdatablocks_error(dataset_id: str, task: Task, task_run: TaskRun, state: State):
    """Callback for get_origdatablocks tasks. Reports a user error."""
    scicat_token = get_scicat_access_token()
    report_dataset_user_error(dataset_id, token=scicat_token)


@task(task_run_name=generate_task_name_dataset)
def download_origdatablocks(dataset_id: str, origDataBlocks: List[OrigDataBlock]):

    s3_client = get_s3_client()

    if len(origDataBlocks) == 0:
        return []

    if all(
        False
        for _ in datablocks_operations.list_datablocks(
            s3_client,
            StoragePaths.relative_raw_files_folder(dataset_id),
            Bucket.landingzone_bucket(),
        )
    ):
        raise Exception(
            f"""No objects found in landing zone at {
                StoragePaths.relative_raw_files_folder(dataset_id)
            } for dataset {dataset_id}. Storage endpoint: {s3_client.url}"""
        )

    raw_files_scratch_folder = StoragePaths.scratch_archival_raw_files_folder(dataset_id)
    raw_files_scratch_folder.mkdir(parents=True, exist_ok=True)

    progress_artifact_id = create_progress_artifact(
        progress=0.0,
        description="Download progress",
    )

    total_file_count = 0
    for b in origDataBlocks:
        total_file_count += len(b.dataFileList)

    def update_progress(p):
        update_progress.last_progress = 0
        progress = math.floor(100.0 * p / total_file_count)
        if (progress > update_progress.last_progress):
            update_progress.last_progress = progress
            update_progress_artifact(artifact_id=progress_artifact_id, progress=progress)

    getLogger().info(f"Downloading {total_file_count} objects from bucket {Bucket.landingzone_bucket()}")
    # files with full path are downloaded to scratch root
    file_paths = datablocks_operations.download_objects_from_s3(
        s3_client,
        prefix=StoragePaths.relative_raw_files_folder(dataset_id),
        bucket=Bucket.landingzone_bucket(),
        destination_folder=raw_files_scratch_folder,
        progress_callback=update_progress
    )
    getLogger().info(f"Downloaded {len(file_paths)} objects from {Bucket.landingzone_bucket()}")

    return file_paths


@task(task_run_name=generate_task_name_dataset)
def create_tarfiles(dataset_id: str) -> List[ArchiveInfo]:
    datablocks_scratch_folder = StoragePaths.scratch_archival_datablocks_folder(dataset_id)
    datablocks_scratch_folder.mkdir(parents=True, exist_ok=True)

    GB_TO_B = 1024 * 1024 * 1024

    raw_files_scratch_folder = StoragePaths.scratch_archival_raw_files_folder(dataset_id)
    raw_files_scratch_folder.mkdir(parents=True, exist_ok=True)

    progress_artifact_id = create_progress_artifact(
        progress=0.0,
        description="Creating tar files",
    )

    def update_progress(progress):
        update_progress.last_progress = 0
        progress = math.floor(100.0 * progress)
        if (progress > update_progress.last_progress):
            update_progress.last_progress = progress
            update_progress_artifact(artifact_id=progress_artifact_id, progress=progress)

    return datablocks_operations.create_tarfiles(
        dataset_id=dataset_id,
        src_folder=raw_files_scratch_folder,
        dst_folder=datablocks_scratch_folder,
        target_size=Variables().ARCHIVER_TARGET_SIZE_GB * GB_TO_B,
        progress_callback=update_progress
    )


@task(task_run_name=generate_task_name_dataset)
def create_datablock_entries(dataset_id: str, orig_datablocks: List[OrigDataBlock], tar_files: List[ArchiveInfo]) -> List[DataBlock]:
    datablocks_scratch_folder = StoragePaths.scratch_archival_datablocks_folder(dataset_id)
    progress_artifact_id = create_progress_artifact(
        progress=0.0,
        description="Creating tar files",
    )

    def update_progress(progress):
        update_progress.last_progress = 0
        progress = math.floor(100.0 * progress)
        if (progress > update_progress.last_progress):
            update_progress.last_progress = progress
            update_progress_artifact(artifact_id=progress_artifact_id, progress=progress)

    return datablocks_operations.create_datablock_entries(dataset_id,
                                                          datablocks_scratch_folder,
                                                          orig_datablocks,
                                                          tar_files,
                                                          update_progress)


@task(task_run_name=generate_task_name_dataset)
def upload_datablocks_to_s3(dataset_id: str) -> List[Path]:
    s3_client = get_s3_client()
    prefix = StoragePaths.relative_datablocks_folder(dataset_id)
    datablocks_scratch_folder = StoragePaths.scratch_archival_datablocks_folder(dataset_id)
    progress_artifact_id = create_progress_artifact(
        progress=0.0,
        description="Upload datablocks to s3",
    )

    def update_progress(progress):
        update_progress.last_progress = 0
        progress = math.floor(100.0 * progress)
        if (progress > update_progress.last_progress):
            update_progress.last_progress = progress
            update_progress_artifact(artifact_id=progress_artifact_id, progress=progress)

    return datablocks_operations.upload_objects_to_s3(client=s3_client,
                                                      prefix=prefix,
                                                      bucket=Bucket.staging_bucket(),
                                                      source_folder=datablocks_scratch_folder,
                                                      ext=".gz",
                                                      progress_callback=update_progress)


@task(task_run_name=generate_task_name_dataset)
def verify_objects(dataset_id: str, uploaded_objects: List[Path]) -> List[DataBlock]:
    s3_client = get_s3_client()
    prefix = StoragePaths.relative_datablocks_folder(dataset_id)

    missing_objects = datablocks_operations.verify_objects(
        client=s3_client,
        uploaded_objects=uploaded_objects,
        minio_prefix=prefix,
        bucket=Bucket.staging_bucket(),
    )
    if len(missing_objects) > 0:
        raise SystemError(f"{len(missing_objects)} datablocks missing")


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


@task(task_run_name=generate_task_name_dataset)
def calculate_checksum(dataset_id: str, datablock: DataBlock):
    return datablocks_operations.calculate_checksum(dataset_id, datablock)


@task(task_run_name=generate_task_name_dataset, tags=[ConcurrencyLimits().LTS_WRITE_TAG])
def move_data_to_LTS(dataset_id: str, datablock: DataBlock):
    """Prefect task to move a datablock (.tar.gz file) to the LTS. Concurrency of this task is limited to 2 instances
    at the same time.
    """
    datablocks_operations.move_data_to_LTS(dataset_id, datablock)


@task(task_run_name=generate_task_name_dataset,
      tags=[ConcurrencyLimits().LTS_READ_TAG],
      retries=5,
      retry_delay_seconds=[60, 120, 240, 480, 960])
def copy_datablock_from_LTS(dataset_id: str, datablock: DataBlock):
    """Prefect task to move a datablock (.tar.gz file) to the LTS. Concurrency of this task is limited to 2 instances
    at the same time.
    """
    datablocks_operations.copy_file_from_LTS(dataset_id, datablock)


@task(
    task_run_name=generate_task_name_dataset
)
def verify_checksum(dataset_id: str, datablock: DataBlock, checksum: str) -> None:
    return datablocks_operations.verify_checksum(
        dataset_id=dataset_id, datablock=datablock, expected_checksum=checksum
    )


@task(task_run_name=generate_task_name_dataset)
def verify_datablock_in_verification(dataset_id: str, datablock: DataBlock) -> None:
    """Prefect Task to verify a datablock in the LTS against a checksum. Task of this type run with no concurrency since the LTS
    does only allow limited concurrent access.
    """
    datablocks_operations.verify_datablock_in_verification(dataset_id=dataset_id, datablock=datablock)


# Flows
@flow(
    name="move_datablocks_to_lts",
    log_prints=True,
    flow_run_name=generate_subflow_run_name_job_id_dataset_id,
)
def move_datablocks_to_lts_flow(dataset_id: str, datablocks: List[DataBlock]):
    """Prefect (sub-)flow to move a datablock to the LTS. Implements the copying of data and verification via checksum.

    Args:
        dataset_id (str): _description_
        datablock (DataBlock): _description_
    """
    tasks = []
    all_tasks = []

    for datablock in datablocks:

        checksum = calculate_checksum.submit(dataset_id=dataset_id, datablock=datablock)
        free_space = check_free_space_in_LTS.submit(wait_for=[checksum])

        move = move_data_to_LTS.submit(dataset_id=dataset_id, datablock=datablock, wait_for=[free_space])  # type: ignore

        getLogger().info(f"Wait {Variables().ARCHIVER_LTS_WAIT_BEFORE_VERIFY_S}s before verifying datablock")
        sleep = sleep_for.submit(Variables().ARCHIVER_LTS_WAIT_BEFORE_VERIFY_S, wait_for=[move])

        copy = copy_datablock_from_LTS.submit(dataset_id=dataset_id, datablock=datablock, wait_for=[sleep])

        checksum_verification = verify_checksum.submit(
            dataset_id=dataset_id, datablock=datablock, checksum=checksum, wait_for=[copy]
        )

        w = verify_datablock_in_verification.submit(
            dataset_id=dataset_id, datablock=datablock, wait_for=[checksum_verification]
        )  # type: ignore
        tasks.append(w)

        all_tasks.append(free_space)
        all_tasks.append(checksum)
        all_tasks.append(move)
        all_tasks.append(sleep)
        all_tasks.append(copy)
        all_tasks.append(checksum_verification)
        all_tasks.append(w)

    wait_for_futures(tasks)

    # this is necessary to propagate the errors of the tasks
    for t in all_tasks:
        t.result()


@flow(name="create_datablocks", flow_run_name=generate_subflow_run_name_job_id_dataset_id)
def create_datablocks_flow(dataset_id: str) -> List[DataBlock]:
    """Prefect (sub-)flow to create datablocks (.tar.gz files) for files of a dataset and register them in Scicat.

    Args:
        dataset_id (str): Dataset id

    Returns:
        List[DataBlock]: List of created and registered datablocks
    """

    scicat_token = get_scicat_access_token.submit()

    dataset_update = update_scicat_archival_dataset_lifecycle.submit(
        dataset_id=dataset_id,
        status=SciCatClient.ARCHIVESTATUSMESSAGE.STARTED,
        token=scicat_token,
    )

    orig_datablocks = get_origdatablocks.with_options(
        on_failure=[partial(on_get_origdatablocks_error, dataset_id)]
    ).submit(dataset_id=dataset_id, token=scicat_token, wait_for=[dataset_update])  # type: ignore

    files = download_origdatablocks.submit(dataset_id=dataset_id, origDataBlocks=orig_datablocks)

    tarfiles_future = create_tarfiles.submit(dataset_id, wait_for=[files])
    datablocks_future = create_datablock_entries.submit(dataset_id, orig_datablocks, tarfiles_future)

    # Prefect issue: https://github.com/PrefectHQ/prefect/issues/12028
    # Exceptions are not propagated correctly
    files.result()
    tarfiles_future.result()
    datablocks_future.result()

    scicat_token = get_scicat_access_token.submit(wait_for=[datablocks_future])

    register_future = register_datablocks.submit(
        datablocks=datablocks_future,  # type: ignore
        dataset_id=dataset_id,
        token=scicat_token,
    )

    register_future.result()

    return datablocks_future


def on_dataset_flow_failure(flow: Flow, flow_run: FlowRun, state: State):
    scicat_token = get_scicat_access_token()
    report_archival_error(
        dataset_id=flow_run.parameters["dataset_id"],
        state=state,
        task_run=None,
        token=scicat_token,
    )
    try:
        reset_dataset(
            dataset_id=flow_run.parameters["dataset_id"],
            token=scicat_token
        )
    except Exception as e:
        getLogger().error(f"failed to reset datablocks {e}")
    datablocks_operations.cleanup_lts_folder(flow_run.parameters["dataset_id"])
    datablocks_operations.cleanup_scratch(flow_run.parameters["dataset_id"])
    try:
        s3_client = get_s3_client()
        datablocks_operations.cleanup_s3_staging(s3_client, flow_run.parameters["dataset_id"])
    except Exception as e:
        getLogger().error(f"failed to cleanup staging {e}")


def cleanup_dataset(flow: Flow, flow_run: FlowRun, state: State):
    try:
        s3_client = get_s3_client()
        datablocks_operations.cleanup_s3_landingzone(s3_client, flow_run.parameters["dataset_id"])
        datablocks_operations.cleanup_s3_staging(s3_client, flow_run.parameters["dataset_id"])
    except Exception as e:
        getLogger().error(f"failed to cleanup staging or landingzone {e}")
    datablocks_operations.cleanup_scratch(flow_run.parameters["dataset_id"])


@flow(
    name="archive_dataset",
    log_prints=True,
    flow_run_name=generate_subflow_run_name_job_id_dataset_id,
    on_failure=[on_dataset_flow_failure],
    on_completion=[cleanup_dataset],
    on_cancellation=[on_dataset_flow_failure],
)
def archive_single_dataset_flow(dataset_id: str):

    datablocks = create_datablocks_flow(dataset_id)

    move_datablocks_to_lts_flow(dataset_id=dataset_id, datablocks=datablocks)

    access_token = get_scicat_access_token.submit()
    update_scicat_archival_dataset_lifecycle.submit(
        dataset_id=dataset_id,
        status=SciCatClient.ARCHIVESTATUSMESSAGE.DATASET_ON_ARCHIVEDISK,
        archivable=False,
        retrievable=True,
        token=access_token
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
    access_token = get_scicat_access_token.submit()

    job_update = update_scicat_archival_job_status.submit(
        job_id=job_id,
        status_code=SciCatClient.JOBSTATUSCODE.IN_PROGRESS,
        status_message=SciCatClient.JOBSTATUSMESSAGE.JOB_IN_PROGRESS,
        token=access_token,
    )
    job_update.result()

    dataset_ids_future = get_job_datasetlist.submit(job_id=job_id, token=access_token)
    dataset_ids = dataset_ids_future.result()

    for id in dataset_ids:
        archive_single_dataset_flow(dataset_id=id)

    access_token = get_scicat_access_token.submit()

    update_scicat_archival_job_status.submit(
        job_id=job_id,
        status_code=SciCatClient.JOBSTATUSCODE.FINISHED_SUCCESSFULLY,
        status_message=SciCatClient.JOBSTATUSMESSAGE.JOB_FINISHED,
        token=access_token,
    ).result()
