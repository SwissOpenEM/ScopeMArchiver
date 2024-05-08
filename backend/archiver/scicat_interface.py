from enum import StrEnum
import logging
import requests
from typing import List
from .model import Job, DataBlock, Dataset, DatasetLifecycle, OrigDataBlock

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
        SCHEDULE_ARCHIVE_JOB_FAILED = "scheduleArchiveJobFailed"

    class RETRIEVESTATUSMESSAGE(StrEnum):
        DATASETRETRIEVED = "datasetRetrieved"

    def __init__(self, endpoint: str = "http://scicat.example.com", prefix: str = None):
        self._ENDPOINT = endpoint
        self._API = prefix or ""

    @property
    def API(self):
        return self._API

    def update_job_status(self, job_id: int, status: JOBSTATUS) -> None:
        job = Job(id=str(job_id), type="archive", jobStatusMessage=str(status))

        result = requests.patch(
            f"{self._ENDPOINT}{self.API}Jobs/{job_id}", data=job.model_dump_json(exclude_none=True))

        # returns none if status_code is 200
        result.raise_for_status()

    def update_dataset_lifecycle(self, dataset_id: int, status: ARCHIVESTATUSMESSAGE, archivable: bool | None = None,
                                 retrievable: bool | None = None) -> None:
        dataset = Dataset(datasetlifecycle=DatasetLifecycle(
            archiveStatusMessage=str(status),
            archivable=archivable,
            retrievable=retrievable
        ))
        result = requests.post(f"{self._ENDPOINT}{self.API}Datasets/{dataset_id}",
                               data=dataset.model_dump_json(exclude_none=True))
        # returns none if status_code is 200
        result.raise_for_status()

    def register_datablocks(self, dataset_id: int, data_blocks: List[DataBlock]) -> None:

        for d in data_blocks:
            result = requests.post(
                f"{self._ENDPOINT}{self.API}Datablocks/", data=d.model_dump_json(exclude_none=True))
            # returns none if status_code is 200
            result.raise_for_status()

    def get_origdatablocks(self, dataset_id: int) -> List[OrigDataBlock]:
        result = requests.get(
            f"{self._ENDPOINT}{self.API}Datasets/{dataset_id}/origdatablocks")
        # returns none if status_code is 200
        result.raise_for_status()

        origdatablocks: List[OrigDataBlock] = []
        for r in result.json():
            origdatablocks.append(OrigDataBlock.model_validate(r))
        return origdatablocks
