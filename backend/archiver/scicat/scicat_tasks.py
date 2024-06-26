from typing import List
from prefect import task

from archiver.scicat.scicat_interface import SciCat
from archiver.utils.model import DataBlock, OrigDataBlock
from archiver.config.variables import Variables
from archiver.flows.utils import generate_task_name_dataset, generate_task_name_job


scicat = SciCat(endpoint=Variables().SCICAT_ENDPOINT,
                prefix=Variables().SCICAT_API_PREFIX)


@task(task_run_name=generate_task_name_job)
def update_scicat_job_status(job_id: int, status: SciCat.JOBSTATUS) -> None:
    scicat.update_job_status(job_id, status)


@task(task_run_name=generate_task_name_dataset)
def update_scicat_dataset_lifecycle(
        dataset_id: int, status: SciCat.ARCHIVESTATUSMESSAGE, archivable: bool | None = None, retrievable: bool | None = None) -> None:

    scicat.update_dataset_lifecycle(
        dataset_id, status, archivable=archivable, retrievable=retrievable)


@task(task_run_name=generate_task_name_dataset)
def get_origdatablocks(dataset_id: int) -> List[OrigDataBlock]:
    return scicat.get_origdatablocks(dataset_id)


@task(task_run_name=generate_task_name_dataset)
def register_datablocks(datablocks: List[DataBlock], dataset_id: int) -> None:
    scicat.register_datablocks(dataset_id, datablocks)


def report_dataset_system_error(dataset_id: int, message: str | None = None):
    scicat.update_dataset_lifecycle(dataset_id=dataset_id, status=SciCat.ARCHIVESTATUSMESSAGE.SCHEDULE_ARCHIVE_JOB_FAILED,
                                    archivable=None, retrievable=None)


def report_dataset_user_error(dataset_id: int, message: str | None = None):
    scicat.update_dataset_lifecycle(dataset_id=dataset_id, status=SciCat.ARCHIVESTATUSMESSAGE.MISSINGFILES,
                                    archivable=None, retrievable=None)


def report_job_failure_user_error(job_id: int, message: str | None = None):
    scicat.update_job_status(
        job_id=job_id, status=SciCat.JOBSTATUS.FINISHED_WITHDATASET_ERRORS)


def report_job_failure_system_error(job_id: int, message: str | None = None):
    scicat.update_job_status(
        job_id=job_id, status=SciCat.JOBSTATUS.FINISHED_UNSUCCESSFULLY)
