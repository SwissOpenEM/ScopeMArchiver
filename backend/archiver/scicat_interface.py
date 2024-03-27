from enum import StrEnum
import logging
import requests
from typing import List
from archiver.model import Job, DataBlock, Dataset, DatasetLifecycle

_LOGGER = logging.getLogger("Jobs")


class SciCat():
    class JOBSTATUS(StrEnum):
        IN_PROGRESS = "inProgress"
        FINISHED_SUCCESSFULLY = "finishedSuccessful"
        FINISHED_UNSUCCESSFULLY = "finishedUnsuccessful"
        FINISHED_WITHDATASET_ERRORS = "finishedWithDatasetErrors"

    class ARCHIVESTATUSMESSAGE(StrEnum):
        STARTED = "started"
        ISONCENTRALDISK = "isOnCentralDisk"
        DATASETONARCHIVEDISK = "datasetOnArchiveDisk"

    class RETRIEVESTATUSMESSAGE(StrEnum):
        DATASETRETRIEVED = "datasetRetrieved"

    def __init__(self, endpoint: str = "scicat.example.com", prefix: str = "api/v3"):
        self._ENDPOINT = endpoint
        self._API = prefix

    @property
    def API(self):
        return self._API

    def update_job_status(self, job_id: int, status: JOBSTATUS):
        job = Job(id=str(job_id), type="archive", jobStatusMessage=str(status))

        requests.patch(
            f"{self._ENDPOINT}/{self.API}/Jobs/{job_id}", json=job.model_dump_json())

    def update_dataset_lifecycle(self, dataset_id: int, status: ARCHIVESTATUSMESSAGE, archivable=None, retrievable=None):
        dataset = Dataset(datasetlifecycle=DatasetLifecycle(
            archiveStatusMessage=str(status),
            archivable=archivable,
            retrievable=retrievable
        ))
        requests.post(f"{self._ENDPOINT}/{self.API}/Datasets/{dataset_id}",
                      json=dataset.model_dump_json())

    def register_datablocks(self, dataset_id: int, data_blocks: List[DataBlock]):
        for d in data_blocks:
            requests.post(
                f"{self._ENDPOINT}/{self.API}/Datablocks/", json=d.model_dump_json())
