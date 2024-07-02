from enum import StrEnum
import logging
import requests
from typing import List
from archiver.utils.model import Job, DataBlock, Dataset, DatasetLifecycle, OrigDataBlock

_LOGGER = logging.getLogger("Jobs")


class SciCat():
    class JOBSTATUS(StrEnum):
        IN_PROGRESS = "inProgress"
        FINISHED_SUCCESSFULLY = "finishedSuccessful"
        FINISHED_UNSUCCESSFULLY = "finishedUnsuccessful"
        FINISHED_WITHDATASET_ERRORS = "finishedWithDatasetErrors"

    class ARCHIVESTATUSMESSAGE(StrEnum):
        STARTED = "started"
        IS_ON_CENTRAL_DISK = "isOnCentralDisk"
        DATASET_ON_ARCHIVEDISK = "datasetOnArchiveDisk"
        SCHEDULE_ARCHIVE_JOB_FAILED = "scheduleArchiveJobFailed"
        MISSING_FILES = "missingFilesError"

    class RETRIEVESTATUSMESSAGE(StrEnum):
        STARTED = "started"
        DATASET_RETRIEVED = "datasetRetrieved"
        DATASET_RETRIEVAL_FAILED = "datasetRetrievalFailed"

    class JOBTYPE(StrEnum):
        ARCHIVE = "archive"
        RETRIEVE = "retrieve"

    def __init__(self, endpoint: str = "http://scicat.example.com", prefix: str = None):
        self._ENDPOINT = endpoint
        self._API = prefix or "/"

    @property
    def API(self):
        return self._API

    def update_job_status(self, job_id: int, type: JOBTYPE, status: JOBSTATUS) -> None:
        job = Job(id=str(job_id), type=str(type), jobStatusMessage=str(status))

        result = requests.patch(
            f"{self._ENDPOINT}{self.API}Jobs/{job_id}", data=job.model_dump_json(exclude_none=True))

        # returns none if status_code is 200
        result.raise_for_status()

    def update_archival_dataset_lifecycle(self, dataset_id: int, status: ARCHIVESTATUSMESSAGE, archivable: bool | None = None,
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

    def update_retrieval_dataset_lifecycle(self, dataset_id: int, status: RETRIEVESTATUSMESSAGE) -> None:
        dataset = Dataset(datasetlifecycle=DatasetLifecycle(
            retrieveStatusMessage=str(status),
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
            try:
                origdatablocks.append(OrigDataBlock.model_validate(r))
            except:
                origdatablocks.append(OrigDataBlock.model_validate_json(r))
        return origdatablocks

    def get_datablocks(self, dataset_id: int) -> List[DataBlock]:
        result = requests.get(
            f"{self._ENDPOINT}{self.API}Datasets/{dataset_id}/datablocks")
        # returns none if status_code is 200
        result.raise_for_status()

        datablocks: List[DataBlock] = []
        for r in result.json():
            try:
                datablocks.append(DataBlock.model_validate(r))
            except:
                datablocks.append(DataBlock.model_validate_json(r))
        return datablocks
