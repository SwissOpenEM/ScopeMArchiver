from celery import Celery, chain, shared_task


import os
from .working_storage_interface import minioClient, Bucket
import logging
import requests
import time
from typing import List
from archiver.scicat_interface import SciCat


_LOGGER = logging.getLogger("Jobs")

celery_app = Celery('tasks',
                    broker=os.environ.get('CELERY_BROKER_URL'),
                    backend=os.environ.get('CELERY_RESULT_BACKEND'))

_SCRATCH_FOLDER = os.environ.get('ARCHIVER_SCRATCH_FOLDER', "/tmp/scratch")
_ARCHIVER_FOLDER = os.environ.get('LTS_FOLDER', "/data")


scicat = SciCat(endpoint="scicat.psi.ch")


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5})
def update_scicat_dataset_lifecycle(result, dataset_id: int, status: SciCat.DATASETSTATUS):
    scicat.update_dataset_lifecycle(dataset_id, status)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5})
def update_scicat_job_status(result, job_id: int, status: SciCat.JOBSTATUS):
    scicat.update_job_status(job_id, status)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5})
def update_scicat_datablocks(self, dataset_id: int, datablocks: List):
    scicat.update_datablocks(dataset_id, SciCat.DATASETSTATUS)


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

    _LOGGER.info("Archive job ended")


@shared_task
def create_datablocks(dataset_id: int, folder: os.PathLike):

    # get files from landing zone to scratch folder
    # create tarball
    # upload to archivable
    scratch_folder = os.join(_SCRATCH_FOLDER, str(dataset_id))
    if not os.path.exists(scratch_folder):
        os.makedirs(scratch_folder)

    download_objects(prefix=dataset_id, bucket=minioClient.LANDINGZONE_BUCKET,
                     destination_folder=scratch_folder)

    tarballs = create_tarballs(dataset_id=dataset_id, folder=scratch_folder)

    upload_objects(prefix=dataset_id, buket=minioClient.ARCHIVAL_BUCKET,
                   source_folder=scratch_folder)

    scicat.update_datablocks.delay(dataset_id, tarballs)


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
