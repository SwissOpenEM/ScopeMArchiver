from typing import List
from prefect import task

from .scicat_interface import SciCat
from .model import DataBlock, OrigDataBlock
from .config import Variables


scicat = SciCat(endpoint=Variables().SCICAT_ENDPOINT,
                prefix=Variables().SCICAT_API_PREFIX)


@task
def update_scicat_job_status(job_id: int, status: SciCat.JOBSTATUS) -> None:
    scicat.update_job_status(job_id, status)


@task
def update_scicat_dataset_lifecycle(
        dataset_id: int, status: SciCat.ARCHIVESTATUSMESSAGE, archivable: bool | None = None, retrievable: bool | None = None) -> None:

    scicat.update_dataset_lifecycle(
        dataset_id, status, archivable=archivable, retrievable=retrievable)


@task
def get_origdatablocks(dataset_id: int) -> List[OrigDataBlock]:
    return scicat.get_origdatablocks(dataset_id)


@task
def register_datablocks(datablocks: List[DataBlock], dataset_id: int) -> None:
    scicat.register_datablocks(dataset_id, datablocks)


@task
def report_error(dataset_id: int, job_id: int, message: str | None = None):
    scicat.update_job_status(
        job_id=job_id, status=SciCat.JOBSTATUS.FINISHED_UNSUCCESSFULLY)
    scicat.update_dataset_lifecycle(dataset_id=dataset_id, status=SciCat.ARCHIVESTATUSMESSAGE.SCHEDULE_ARCHIVE_JOB_FAILED,
                                    archivable=None, retrievable=None)
