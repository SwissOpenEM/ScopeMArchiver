from celery import Celery, chain, shared_task


import os
from working_storage_interface import minioClient
import logging
import requests
import time
from typing import List

from enum import Enum


_LOGGER = logging.getLogger("Jobs")

celery_app = Celery('tasks',
                    broker=os.environ.get('CELERY_BROKER_URL'),
                    backend=os.environ.get('CELERY_RESULT_BACKEND'))

_SCRATCH_FOLDER = os.environ.get('ARCHIVER_SCRATCH_FOLDER', "/tmp/scratch")


class SciCat():
    class JOBSTATUS(Enum):
        IN_PROGRESS = 0
        FINISHED_SUCCESSFULLY = 1
        FINISHED_UNSUCCESSFULLY = 2
        FINISHED_WITHDATASET_ERRORS = 3

    class DATASETSTATUS(Enum):
        ARCHIVABLE = 0
        RETRIEVABLE = 1

    _ENDPOINT = "scicat.psi.ch"

    def __init__(self, endpoint: str):
        self._ENDPOINT = endpoint

    @shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5})
    def update_job_status(result, job_id: int, status: JOBSTATUS):
        time.sleep(1)
        _LOGGER.info(
            f"Update lifecyle job status to {status} for job {job_id}")

    @shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5})
    def update_dataset_lifecycle(result, dataset_id: int, status: DATASETSTATUS):
        time.sleep(1)
        _LOGGER.info(
            f"Update dataset lifecycle  to {status} for dataset {dataset_id}")


scicat = SciCat(endpoint="scicat.psi.ch")


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5})
def update_lifecycle(archive_jobs_result):
    # result ttl vs retries?
    time.sleep(10)
    _LOGGER.info(f"Updating lifecyle: {archive_jobs_result}")


@shared_task
def archive_job(result, job_id: int, filename: str, destination_folder: os.PathLike) -> List[os.PathLike]:
    _LOGGER.info("Archive job started")

    scratch_folder = os.join(_SCRATCH_FOLDER, str(job_id))
    if not os.path.exists(scratch_folder):
        os.makedirs(scratch_folder)

    local_filename = download_object(filename, scratch_folder)
    files = create_tarballs(scratch_folder)
    _LOGGER.info("Archive job ended")
    return files


def create_tarballs(dataset_id: int, folder:  os.PathLike) -> List[os.PathLike]:
    import tarfile

    TARGET_SIZE = 100 * 1024*1024
    tarballs = []

    filename = f"{dataset_id}_{len(tarballs)}.tar"
    filepath = os.path.join(folder, filename)

    tar = tarfile.open(filepath, 'w')

    for f in os.listdir(folder):
        tar.add(f)

        if os.path.getsize(filepath) >= TARGET_SIZE:
            tar.close()
            tarballs.append(filename)
            filename = f"{dataset_id}_{len(tarballs)}.tar"
            filepath = os.path.join(folder, filename)
            tar = tarfile.open(filepath, 'w')

    tar.close()
    tarballs.append(filename)

    return tarballs


@shared_task
def download_object(filename: str, destination_folder: os.PathLike):

    if not os.path.exists(destination_folder):
        print("Destination not reachable")
        return

    presigned_url = minioClient.get_presigned_url(
        filename=filename, bucket=minioClient.ARCHIVAL_BUCKET)
    stat = minioClient.stat_object(
        filename=filename, bucket=minioClient.ARCHIVAL_BUCKET)
    local_filename = os.path.join(
        destination_folder, filename)

    with requests.get(presigned_url, stream=True) as r:
        r.raise_for_status()
        chunk_size = 8192
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                f.write(chunk)
    return local_filename


def create_archiving_pipeline(filename: str):
    """Archiving Workflow

    Returns:
        Pipeline: steps to be executed to archive
d
      # register job, dataset
      # verify data
      # create tarballs
      # store results
      # star
    """
    import random
    job_id = random.randint(1, 100)
    dataset_id = random.randint(1, 100)

    return chain(

        scicat.update_job_status.s(
            None, job_id=job_id, status=scicat.JOBSTATUS.IN_PROGRESS),
        archive_job.s(job_id=job_id, filename=filename,
                      destination_folder="/tmp/archiving"),
        scicat.update_dataset_lifecycle.s(
            dataset_id=dataset_id, status=scicat.DATASETSTATUS.RETRIEVABLE)
    )
