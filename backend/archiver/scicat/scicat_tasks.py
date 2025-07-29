from typing import List
from prefect import task
from uuid import UUID
from pydantic import SecretStr
from datetime import timedelta
from pathlib import Path

from archiver.scicat.scicat_interface import SciCatClient
from archiver.config.variables import Variables
from archiver.utils.model import (
    DataBlock,
    OrigDataBlock,
    JobResultEntry,
    JobResultObject,
)
from archiver.utils.log import log
from archiver.flows.task_utils import generate_task_name_dataset, generate_task_name_job
from archiver.utils.s3_storage_interface import Bucket, S3Storage, get_s3_client


from prefect.artifacts import create_link_artifact

scicat_instance: SciCatClient | None = None


def scicat_client() -> SciCatClient:
    global scicat_instance
    if scicat_instance is None:  # type: ignore
        scicat_instance = SciCatClient(
            endpoint=Variables().SCICAT_ENDPOINT,
            api_prefix=Variables().SCICAT_API_PREFIX,
            jobs_api_prefix=Variables().SCICAT_JOBS_API_PREFIX,
        )
    return scicat_instance


@task(cache_result_in_memory=True, cache_expiration=timedelta(seconds=3600))
def get_scicat_access_token() -> SecretStr:
    token = scicat_client().get_token()
    return SecretStr(token)


@task(task_run_name=generate_task_name_job)
def update_scicat_archival_job_status(
    job_id: UUID,
    status_code: SciCatClient.JOBSTATUSCODE,
    status_message: SciCatClient.JOBSTATUSMESSAGE,
    token: SecretStr,
) -> None:
    scicat_client().update_job_status(
        job_id=job_id,
        status_code=status_code,
        status_message=status_message,
        job_result_object=None,
        token=token,
    )


@task(task_run_name=generate_task_name_job)
def update_scicat_retrieval_job_status(
    job_id: UUID,
    status_code: SciCatClient.JOBSTATUSCODE,
    status_message: SciCatClient.JOBSTATUSMESSAGE,
    jobResultObject: JobResultObject | None,
    token: SecretStr,
) -> None:
    scicat_client().update_job_status(
        job_id=job_id,
        status_code=status_code,
        status_message=status_message,
        job_result_object=jobResultObject,
        token=token,
    )


@task(task_run_name=generate_task_name_dataset)
def update_scicat_archival_dataset_lifecycle(
    dataset_id: str,
    status: SciCatClient.ARCHIVESTATUSMESSAGE,
    token: SecretStr,
    archivable: bool | None = None,
    retrievable: bool | None = None,
) -> None:
    scicat_client().update_archival_dataset_lifecycle(
        dataset_id=dataset_id,
        status=status,
        archivable=archivable,
        retrievable=retrievable,
        token=token,
    )


@task(task_run_name=generate_task_name_dataset)
def update_scicat_retrieval_dataset_lifecycle(
    dataset_id: str, status: SciCatClient.RETRIEVESTATUSMESSAGE, token: SecretStr
) -> None:
    # Due to a bug in Scicat, archivable and retrievable need to passed as well to the patch request
    scicat_client().update_retrieval_dataset_lifecycle(
        dataset_id=dataset_id,
        status=status,
        token=token,
        archivable=False,
        retrievable=True,
    )


@task
def get_origdatablocks(dataset_id: str, token: SecretStr) -> List[OrigDataBlock]:
    return scicat_client().get_origdatablocks(dataset_id=dataset_id, token=token)


@task
def get_job_datasetlist(job_id: UUID, token: SecretStr) -> List[str]:
    return scicat_client().get_job_datasetlist(job_id=job_id, token=token)


@task(task_run_name=generate_task_name_dataset)
def register_datablocks(datablocks: List[DataBlock], dataset_id: str, token: SecretStr) -> None:
    scicat_client().register_datablocks(dataset_id=dataset_id, data_blocks=datablocks, token=token)


@task
def get_datablocks(dataset_id: str, token: SecretStr) -> List[DataBlock]:
    datablocks = scicat_client().get_datablocks(dataset_id=dataset_id, token=token)
    if len(datablocks) == 0:
        raise SystemError(f"Found no datablocks for {dataset_id}")
    return datablocks


def report_dataset_system_error(dataset_id: str, token: SecretStr, message: str | None = None):
    scicat_client().update_archival_dataset_lifecycle(
        dataset_id=dataset_id,
        status=SciCatClient.ARCHIVESTATUSMESSAGE.SCHEDULE_ARCHIVE_JOB_FAILED,
        archivable=None,
        retrievable=None,
        token=token,
    )


def report_dataset_user_error(dataset_id: str, token: SecretStr, message: str | None = None):
    scicat_client().update_archival_dataset_lifecycle(
        dataset_id=dataset_id,
        status=SciCatClient.ARCHIVESTATUSMESSAGE.MISSING_FILES,
        archivable=None,
        retrievable=None,
        token=token,
    )


def report_dataset_retrieval_error(
    dataset_id: str,
    token: SecretStr,
    message: str | None = None,
):
    # TODO: correct error message
    scicat_client().update_retrieval_dataset_lifecycle(
        dataset_id=dataset_id,
        status=SciCatClient.RETRIEVESTATUSMESSAGE.DATASET_RETRIEVAL_FAILED,
        token=token,
        archivable=False,
        retrievable=True,
    )


def report_job_failure_user_error(
    job_id: UUID,
    token: SecretStr,
    message: str | None = None,
):
    scicat_client().update_job_status(
        job_id=job_id,
        status_code=SciCatClient.JOBSTATUSCODE.FINISHED_WITHDATASET_ERRORS,
        status_message=SciCatClient.JOBSTATUSMESSAGE.JOB_FINISHED,
        job_result_object=None,
        token=token,
    )


def report_job_failure_system_error(
    job_id: UUID,
    token: SecretStr,
    message: str | None = None,
):
    scicat_client().update_job_status(
        job_id=job_id,
        status_code=SciCatClient.JOBSTATUSCODE.FINISHED_UNSUCCESSFULLY,
        status_message=SciCatClient.JOBSTATUSMESSAGE.JOB_FINISHED,
        job_result_object=None,
        token=token,
    )


def reset_dataset(
    dataset_id: str,
    token: SecretStr
):
    data_blocks = scicat_client().get_datablocks(dataset_id=dataset_id, token=token)
    scicat_client().delete_datablocks(dataset_id=dataset_id, data_blocks=data_blocks, token=token)


@task
def create_job_result_object_task(dataset_ids: List[str]) -> List[JobResultEntry]:
    access_token = get_scicat_access_token.submit()
    access_token.wait()

    job_results: List[JobResultEntry] = []

    for dataset_id in dataset_ids:
        datablocks_future = get_datablocks.submit(dataset_id=dataset_id, token=access_token.result())

        datablocks_future.wait()
        datablocks = datablocks_future.result()

        dataset_job_results = create_job_result_object(dataset_id, datablocks)
        job_results = job_results + dataset_job_results

    return job_results


def create_presigned_url(client: S3Storage, datablock: DataBlock):
    url = client.get_presigned_url(Bucket.retrieval_bucket(), datablock.archiveId)
    return url


@log
def create_job_result_object(dataset_id: str, datablocks: List[DataBlock]) -> List[JobResultEntry]:
    s3_client = get_s3_client()
    job_result_entries: List[JobResultEntry] = []
    for datablock in datablocks:
        url = create_presigned_url(s3_client, datablock)

        invalid_chars = ["/", ".", "_"]
        sanitized_name = str(Path(datablock.archiveId).name)
        for c in invalid_chars:
            sanitized_name = sanitized_name.replace(c, "-")
        create_link_artifact(
            key=sanitized_name,
            link=url,
            description=f"Link to a datablock {sanitized_name}",
        )

        job_result_entries.append(
            JobResultEntry(
                datasetId=dataset_id,
                name=Path(datablock.archiveId).name,
                size=datablock.size,
                archiveId=datablock.archiveId,
                url=url,
            )
        )

    return job_result_entries
