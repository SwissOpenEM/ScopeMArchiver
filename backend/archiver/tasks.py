from celery import Celery, chain, shared_task, group

import os
import logging
import time
import inspect
from uuid import uuid4
from typing import List

from kombu.utils.json import register_type

from archiver.scicat_interface import SciCat
import archiver.model as models
from archiver.model import OrigDataBlock, BaseModel, DataBlock
import archiver.datablocks

_LOGGER = logging.getLogger("Jobs")


scicat = SciCat(endpoint=os.environ.get('SCICAT_ENDPOINT', 'http://scicat.psi.ch'), prefix="")


def register_pydantic_with_celery():
    for cls_name, cls_obj in [(cls_name, cls_obj) for cls_name, cls_obj in inspect.getmembers(models)
                              if inspect.isclass(cls_obj) and cls_obj is not BaseModel and issubclass(cls_obj, BaseModel)]:

        register_type(
            cls_obj,
            cls_name,
            lambda o: o.model_dump_json(),
            lambda o, c=cls_obj: c.model_validate_json(o)
        )


celery_app = Celery('tasks',
                    broker=os.environ.get('CELERY_BROKER_URL'),
                    backend=os.environ.get('CELERY_RESULT_BACKEND'))


register_pydantic_with_celery()

_ARCHIVER_FOLDER = os.environ.get('LTS_FOLDER', "/data")


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5})
def update_scicat_job_status(result, job_id: int, status: SciCat.JOBSTATUS):
    scicat.update_job_status(job_id, status)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5})
def update_lifecycle(archive_jobs_result):
    # result ttl vs retries?
    time.sleep(10)
    _LOGGER.info(f"Updating lifecyle: {archive_jobs_result}")


@shared_task
def archive_job(result, job_id: int, filename: str, destination_folder: os.PathLike) -> List[os.PathLike]:
    return [""]
    _LOGGER.info("Archive job started")

    scratch_folder = os.join(_SCRATCH_FOLDER, str(job_id))
    if not os.path.exists(scratch_folder):
        os.makedirs(scratch_folder)

    _LOGGER.info("Archive job ended")


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5})
def update_scicat_dataset_lifecycle(
        result, dataset_id: int, status: SciCat.ARCHIVESTATUSMESSAGE, archivable=None, retrievable=None) -> None:

    scicat.update_dataset_lifecycle(dataset_id, status, archivable=archivable, retrievable=retrievable)


@shared_task
def create_datablocks(result, dataset_id: int, origDataBlocks: List[OrigDataBlock]) -> List[DataBlock]:
    return archiver.datablocks.create_datablocks(dataset_id, origDataBlocks)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5})
def register_datablocks(datablocks: List[DataBlock], dataset_id: int) -> None:
    scicat.register_datablocks(dataset_id, datablocks)


@shared_task
def move_data_to_staging(datablocks: List[DataBlock]) -> List[DataBlock]:
    return [""]


@shared_task
def move_data_to_LTS(result) -> None:
    pass


@shared_task
def validate_data_in_LTS(result) -> None:
    pass


@shared_task
def on_pipeline_error(request, exc, traceback):
    _LOGGER.error(f"Pipeline failed: {exc}")
    _LOGGER.error(f"Traceback: {traceback}")
    _LOGGER.error(f"Initial request: {request}")


@shared_task
def report_error(dataset_id: int, job_id: int):
    scicat.update_job_status(job_id=job_id, status=SciCat.JOBSTATUS.FINISHED_UNSUCCESSFULLY)
    scicat.update_dataset_lifecycle(dataset_id=dataset_id, status=SciCat.ARCHIVESTATUSMESSAGE.SCHEDULE_ARCHIVE_JOB_FAILED,
                                    archivable=None, retrievable=None)


@shared_task
def on_validation_in_LTS_error(request, exc, traceback, job_id, dataset_id):
    # TODO: make async and add retries
    report_error(dataset_id, job_id)
    # TODO: cleanup files


@shared_task
def on_move_data_to_LTS_error(request, exc, traceback, job_id, dataset_id):
    # TODO: make async and add retries
    report_error(dataset_id, job_id)
    # TODO: cleanup files


@shared_task
def on_move_data_to_staging(request, exc, traceback, job_id, dataset_id):
    # TODO: make async and add retries
    report_error(dataset_id, job_id)
    # TODO: cleanup files


@shared_task
def on_register_datablocks_error(request, exc, traceback, job_id, dataset_id):
    # TODO: make async and add retries
    report_error(dataset_id, job_id)
    # TODO: cleanup files


@shared_task
def on_create_datablocks_error(request, exc, traceback, job_id, dataset_id):
    # TODO: make async and add retries
    report_error(dataset_id, job_id)
    # TODO: cleanup files


def create_archiving_pipeline(dataset_id: int, job_id: int, orig_data_blocks: List[OrigDataBlock]) -> chain:
    return chain(
        update_scicat_job_status.s(None, job_id, SciCat.JOBSTATUS.IN_PROGRESS),
        update_scicat_dataset_lifecycle.s(dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED),

        create_datablocks.s(dataset_id, orig_data_blocks).on_error(
            on_create_datablocks_error.s(job_id=job_id, dataset_id=dataset_id)),
        move_data_to_staging.s().on_error(
            on_move_data_to_staging.s(job_id=job_id, dataset_id=dataset_id)),
        register_datablocks.s(dataset_id).on_error(
            on_register_datablocks_error.s(job_id=job_id, dataset_id=dataset_id)),
        move_data_to_LTS.s().on_error(
            on_move_data_to_LTS_error.s(job_id=job_id, dataset_id=dataset_id)),
        validate_data_in_LTS.s().on_error(
            on_validation_in_LTS_error.s(job_id=job_id, dataset_id=dataset_id)),

        update_scicat_dataset_lifecycle.s(
            dataset_id=dataset_id, status=SciCat.ARCHIVESTATUSMESSAGE.DATASETONARCHIVEDISK, retrievable=True),
        update_scicat_job_status.s(job_id, SciCat.JOBSTATUS.FINISHED_SUCCESSFULLY)
    ).on_error(on_pipeline_error.s())


def create_retrieval_pipeline(dataset_id: int, job_id: int):
    pass
