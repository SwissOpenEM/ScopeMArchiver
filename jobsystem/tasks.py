from celery import Celery, chain, shared_task


import os
from working_storage_interface import minioClient
import logging
import requests
import time


_LOGGER = logging.getLogger("Jobs")

celery = Celery('tasks',
                broker=os.environ.get('CELERY_BROKER_URL'),
                backend=os.environ.get('CELERY_RESULT_BACKEND'))


@shared_task
def download_all():
    download_object.delay(
        "b8a8bb8c-aff2-4225-8bcd-99f38536cbd4-1GB.bin", "./downloads")
    download_object.delay(
        "2f70a446-05dd-4f51-9510-c5f5697c5e05-file3_100MB.img", "./downloads")


class SciCat():

    @staticmethod
    def update_job_status():
        _LOGGER.info(f"Register job status with Scicat")


# @dramatiq.actor(min_backoff=2000)
@shared_task
def update_job_status():
    time.sleep(10)
    SciCat.update_job_status()


# @dramatiq.actor(max_retries=0)
@shared_task
def archive_job(result, filename: str, destination_folder: str):
    _LOGGER.info("Archive job started")
    local_filename = download_object(filename, destination_folder)
    _LOGGER.info("Archive job ended")
    return local_filename


# @dramatiq.actor(min_backoff=2000)
@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5})
def update_lifecycle(archive_jobs_result):
    # result ttl vs retries?
    time.sleep(10)
    _LOGGER.info(f"Updating lifecyle: {archive_jobs_result}")


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

    return chain(
        update_job_status.s(),
        archive_job.s(filename=filename, destination_folder="/tmp/archiving"),
        update_lifecycle.s()
    )


@shared_task
def download_object(filename: str, destination_folder: str):

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
                # If you have chunk encoded response uncomment if
                # and set chunk_size parameter to None.
                # if chunk:
                f.write(chunk)
                # bar()
    return local_filename
