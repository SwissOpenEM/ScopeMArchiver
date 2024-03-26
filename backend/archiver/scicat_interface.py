from enum import StrEnum
import logging
import requests
from typing import List
from archiver.model import Job, DataBlocks

_LOGGER = logging.getLogger("Jobs")


class SciCat():
    class JOBSTATUS(StrEnum):
        IN_PROGRESS = "inProgress"
        FINISHED_SUCCESSFULLY = "finishedSuccessful"
        FINISHED_UNSUCCESSFULLY = "finishedUnsuccessful"
        FINISHED_WITHDATASET_ERRORS = "finishedWithDatasetErrors"

    class DATASETSTATUS(StrEnum):
        ARCHIVABLE = "archivable"
        RETRIEVABLE = "retrievable"
        FAILED = "failed"

    def __init__(self, endpoint: str = "scicat.example.com", prefix: str = "api/v3"):
        self._ENDPOINT = endpoint
        self._API = prefix

    @property
    def API(self):
        return self._API

    def update_job_status(self, job_id: int, status: JOBSTATUS):
        job = Job(id=str(job_id), type="archive", jobStatusMessage=str(status))

        requests.patch(f"{self._ENDPOINT}/{self.API}/Jobs/{job_id}", json=job.model_dump_json())

    def update_dataset_lifecycle(self, dataset_id: int, status: DATASETSTATUS):
        requests.post(f"{self._ENDPOINT}/{self.API}/Datasets/{dataset_id}", json={
            "datasetlifecyle": {"archivable": "false", "retrievable": "False",
                                "archiveStatusMessage": "started"
                                }
        })
        _LOGGER.info(
            f"Update dataset lifecycle  to {status} for dataset {dataset_id}")

    def register_datablocks(self, dataset_id: int, dataFileList: List[DataBlocks]):
        pass
