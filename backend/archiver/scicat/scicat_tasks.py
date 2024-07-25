from typing import List
from prefect import task
from uuid import UUID
from pydantic import SecretStr
from datetime import timedelta

from archiver.scicat.scicat_interface import SciCat
from archiver.config.variables import Variables
from archiver.utils.model import DataBlock, OrigDataBlock
from archiver.flows.task_utils import generate_task_name_dataset, generate_task_name_job

scicat = SciCat(endpoint=Variables().SCICAT_ENDPOINT,
                prefix=Variables().SCICAT_API_PREFIX)


@task(cache_result_in_memory=True, cache_expiration=timedelta(seconds=3600))
def get_scicat_access_token() -> SecretStr:
    token = scicat.get_token()
    return SecretStr(token)


@task(task_run_name=generate_task_name_job)
def update_scicat_archival_job_status(job_id: UUID, status: SciCat.JOBSTATUS, token: SecretStr) -> None:
    scicat.update_job_status(job_id, SciCat.JOBTYPE.ARCHIVE, status, token)


@task(task_run_name=generate_task_name_job)
def update_scicat_retrieval_job_status(job_id: UUID, status: SciCat.JOBSTATUS, token: SecretStr) -> None:
    scicat.update_job_status(job_id, SciCat.JOBTYPE.RETRIEVE, status, token=token)


@task(task_run_name=generate_task_name_dataset)
def update_scicat_archival_dataset_lifecycle(
        dataset_id: int, status: SciCat.ARCHIVESTATUSMESSAGE, token: SecretStr,
        archivable: bool | None = None,
        retrievable: bool | None = None) -> None:

    scicat.update_archival_dataset_lifecycle(
        dataset_id, status, archivable=archivable, retrievable=retrievable, token=token)


@task(task_run_name=generate_task_name_dataset)
def update_scicat_retrieval_dataset_lifecycle(
        dataset_id: int, status: SciCat.RETRIEVESTATUSMESSAGE, token: SecretStr) -> None:

    scicat.update_retrieval_dataset_lifecycle(
        dataset_id, status, token)


@task
def get_origdatablocks(dataset_id: int, token: SecretStr) -> List[OrigDataBlock]:
    return scicat.get_origdatablocks(dataset_id, token)


@task
def get_job_datasetlist(job_id: UUID, token: SecretStr) -> List[int]:
    return scicat.get_job_datasetlist(job_id=job_id, token=token)


@task(task_run_name=generate_task_name_dataset)
def register_datablocks(datablocks: List[DataBlock], dataset_id: int, token: SecretStr) -> None:
    scicat.register_datablocks(dataset_id, datablocks, token)


@task
def get_datablocks(dataset_id: int, token: SecretStr) -> List[DataBlock]:
    return scicat.get_datablocks(dataset_id=dataset_id, token=token)


def report_dataset_system_error(dataset_id: int, token: SecretStr, message: str | None = None):
    scicat.update_archival_dataset_lifecycle(dataset_id=dataset_id, status=SciCat.ARCHIVESTATUSMESSAGE.SCHEDULE_ARCHIVE_JOB_FAILED,
                                             archivable=None, retrievable=None, token=token)


def report_dataset_user_error(dataset_id: int, token: SecretStr, message: str | None = None):
    scicat.update_archival_dataset_lifecycle(dataset_id=dataset_id, status=SciCat.ARCHIVESTATUSMESSAGE.MISSING_FILES,
                                             archivable=None, retrievable=None, token=token)


def report_dataset_retrieval_error(dataset_id: int, token: SecretStr, message: str | None = None,):
    # TODO: correct error message
    scicat.update_retrieval_dataset_lifecycle(
        dataset_id=dataset_id, status=SciCat.RETRIEVESTATUSMESSAGE.DATASET_RETRIEVAL_FAILED, token=token)


def report_job_failure_user_error(job_id: UUID, type: SciCat.JOBTYPE, token: SecretStr, message: str | None = None):
    scicat.update_job_status(
        job_id=job_id, type=type, status=SciCat.JOBSTATUS.FINISHED_WITHDATASET_ERRORS, token=token)


def report_job_failure_system_error(job_id: UUID, type: SciCat.JOBTYPE, token: SecretStr, message: str | None = None):
    scicat.update_job_status(
        job_id=job_id, type=type, status=SciCat.JOBSTATUS.FINISHED_UNSUCCESSFULLY, token=token)
