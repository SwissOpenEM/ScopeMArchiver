from celery import Celery, chain, shared_task

import os
import logging
import requests
import time
import inspect
from typing import List
from kombu.utils.json import register_type

from .working_storage_interface import minioClient, Bucket
from archiver.scicat_interface import SciCat
import archiver.model as models
from archiver.model import OrigDataBlock, BaseModel, DataBlock

_LOGGER = logging.getLogger("Jobs")


def register_pydantic_with_celery():
    for cls_name, cls_obj in [(cls_name, cls_obj) for cls_name, cls_obj in inspect.getmembers(models) if inspect.isclass(cls_obj) and cls_obj is not BaseModel and issubclass(cls_obj, BaseModel)]:

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

_SCRATCH_FOLDER = os.environ.get('ARCHIVER_SCRATCH_FOLDER', "/tmp/scratch")
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


def upload_objects(minio_prefix: str, bucket: Bucket, source_folder: os.PathLike):
    for filename in os.listdir(source_folder):
        minioClient.put_object(filename, os.path.join(
            minio_prefix, filename), bucket)


@shared_task
def download_objects(minio_prefix: str, bucket: Bucket, destination_folder: os.PathLike):

    if not os.path.exists(destination_folder):
        print("Destination not reachable")
        return

    for filename in minioClient.get_objects(minio_prefix, bucket):
        presigned_url = minioClient.get_presigned_url(
            filename=filename, bucket=bucket)
        stat = minioClient.stat_object(
            filename=filename, bucket=bucket)
        local_filename = os.path.join(
            destination_folder, filename)

        with requests.get(presigned_url, stream=True) as r:
            r.raise_for_status()
            chunk_size = 8192
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    f.write(chunk)


scicat = SciCat(endpoint="scicat.psi.ch")


def create_tarballs(dataset_id: int, folder: os.PathLike,
                    target_size: int = 100 * (1024**3)) -> List[os.PathLike]:
    import tarfile

    tarballs = []

    filename = f"{dataset_id}_{len(tarballs)}.tar.gz"
    filepath = os.path.join(folder, filename)

    tar = tarfile.open(filepath, 'x:gz')

    for f in os.listdir(folder):
        file = os.path.join(folder, f)
        if file.endswith(".tar.gz"):
            continue
        tar.add(file, recursive=False)

        if os.path.getsize(filepath) >= target_size:
            tar.close()
            tarballs.append(filename)
            filename = f"{dataset_id}_{len(tarballs)}.tar.gz"
            filepath = os.path.join(folder, filename)
            tar = tarfile.open(filepath, 'w')

    tar.close()
    tarballs.append(filename)

    return tarballs


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5})
def update_scicat_dataset_lifecycle(result, dataset_id: int, status: SciCat.ARCHIVESTATUSMESSAGE, archivable=None, retrievable=None) -> None:

    scicat.update_dataset_lifecycle(dataset_id, status, archivable=archivable, retrievable=retrievable)


@shared_task
def create_datablocks(result, dataset_id: int, origDataBlocks: List[OrigDataBlock]) -> List[DataBlock]:
    return [""]

    # get files from landing zone to scratch folder
    # create tarball
    # upload to archivable
    # scratch_folder = os.path.join(_SCRATCH_FOLDER, str(dataset_id))
    # if not os.path.exists(scratch_folder):
    #     os.makedirs(scratch_folder)

    # download_objects(prefix=dataset_id, bucket=minioClient.LANDINGZONE_BUCKET,
    #                  destination_folder=scratch_folder)

    # tarballs = create_tarballs(dataset_id=dataset_id, folder=scratch_folder)

    # upload_objects(prefix=dataset_id, buket=minioClient.ARCHIVAL_BUCKET,
    #                source_folder=scratch_folder)

    # return tarballs


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5})
def register_datablocks(datablocks: List[DataBlock], dataset_id: int) -> None:
    scicat.register_datablocks(dataset_id, datablocks)


@shared_task
def move_data_to_archiveable_storage(datablocks: List[DataBlock]) -> List[DataBlock]:
    return [""]


@shared_task
def move_data_to_LTS(result) -> None:
    pass


@shared_task
def validate_data_in_LTS(result) -> None:
    pass


@shared_task
def log_error(request, exc, traceback):
    with open(os.path.join('/var/errors', request.id), 'a') as fh:
        print('--\n\n{0} {1} {2}'.format(
            request.id, exc, traceback), file=fh)


@shared_task
def report_error():
    pass


@shared_task
def on_validation_in_LTS_error(request, exc, traceback):
    pass


@shared_task
def on_move_data_to_LTS_error(request, exc, traceback):
    pass


@shared_task
def on_move_data_to_archiveable_storage(request, exc, traceback):
    pass


@shared_task
def on_register_datablocks_error(request, exc, traceback):
    pass


@shared_task
def on_create_datablocks_error(request, exc, traceback):
    pass
    # with open(os.path.join('/var/errors', request.id), 'a') as fh:
    #     print('--\n\n{0} {1} {2}'.format(
    #         request.id, exc, traceback), file=fh)


def create_archiving_pipeline(dataset_id: int, job_id: int, orig_data_blocks: List[OrigDataBlock]) -> chain:
    return chain(
        update_scicat_job_status.s(None, job_id, SciCat.JOBSTATUS.IN_PROGRESS),
        update_scicat_dataset_lifecycle.s(dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED),
        create_datablocks.s(dataset_id, orig_data_blocks).on_error(on_create_datablocks_error.s()),
        move_data_to_archiveable_storage.s().on_error(on_move_data_to_archiveable_storage.s()),
        register_datablocks.s(dataset_id).on_error(on_register_datablocks_error.s()),
        move_data_to_LTS.s().on_error(on_move_data_to_LTS_error.s()),
        validate_data_in_LTS.s().on_error(on_validation_in_LTS_error.s()),
        update_scicat_dataset_lifecycle.s(
            dataset_id=dataset_id, status=SciCat.ARCHIVESTATUSMESSAGE.DATASETONARCHIVEDISK, retrievable=True),
        update_scicat_job_status.s(job_id, SciCat.JOBSTATUS.FINISHED_SUCCESSFULLY)
    )


def create_retrieval_pipeline(dataset_id: int, job_id: int):
    pass
