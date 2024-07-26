from enum import StrEnum
import requests
from typing import List
from uuid import UUID
from pydantic import SecretStr

from archiver.utils.model import Job, DataBlock, Dataset, DatasetLifecycle, OrigDataBlock
from archiver.utils.log import log
from archiver.config.blocks import Blocks


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

    def __init__(self, endpoint: str = "http://scicat.example.com", prefix: str = "/"):
        self._ENDPOINT = endpoint
        if not prefix.endswith('/'):
            raise ValueError("Api prefix needs to end with '/'")
        self._API = prefix

    def _headers(self, token: SecretStr):
        return {"Authorization": f"Bearer {token.get_secret_value()}", "Content-Type": "application/json"}

    def get_token(self) -> str:

        user = Blocks().SCICAT_USER
        password = Blocks().SCICAT_PASSWORD

        resp = requests.post(url=f"{self._ENDPOINT}{self._API}auth/login", data={
            "username": user,
            "password": password.get_secret_value()
        })
        resp.raise_for_status()
        return resp.json()["access_token"]

    @ property
    def API(self):
        return self._API

    @ log
    def update_job_status(self, job_id: UUID, type: JOBTYPE, status: JOBSTATUS, token: SecretStr) -> None:
        job = Job(statusCode="1", statusMessage=str(status))

        headers = self._headers(token)

        result = requests.patch(
            f"{self._ENDPOINT}{self.API}jobs/{job_id}", data=job.model_dump_json(exclude_none=True), headers=headers)

        # returns none if status_code is 200
        result.raise_for_status()

    @ log
    def update_archival_dataset_lifecycle(
            self, dataset_id: int, status: ARCHIVESTATUSMESSAGE, token: SecretStr, archivable: bool | None = None, retrievable: bool |
            None = None) -> None:
        dataset = Dataset(datasetlifecycle=DatasetLifecycle(
            archiveStatusMessage=str(status),
            archivable=archivable,
            retrievable=retrievable
        ))

        headers = self._headers(token)
        result = requests.patch(f"{self._ENDPOINT}{self.API}datasets/{dataset_id}",
                                data=dataset.model_dump_json(exclude_none=True), headers=headers)
        # returns none if status_code is 200
        result.raise_for_status()

    @log
    def update_retrieval_dataset_lifecycle(self, dataset_id: int, status: RETRIEVESTATUSMESSAGE, token: SecretStr) -> None:
        dataset = Dataset(datasetlifecycle=DatasetLifecycle(
            retrieveStatusMessage=str(status),
        ))
        headers = self._headers(token)
        result = requests.patch(f"{self._ENDPOINT}{self.API}datasets/{dataset_id}",
                                data=dataset.model_dump_json(exclude_none=True), headers=headers)
        # returns none if status_code is 200
        result.raise_for_status()

    @log
    def register_datablocks(self, dataset_id: int, data_blocks: List[DataBlock], token: SecretStr) -> None:

        headers = self._headers(token)
        for d in data_blocks:
            result = requests.post(f"{self._ENDPOINT}{self.API}datasets/{dataset_id}/datablocks",
                                   data=d.model_dump_json(exclude_none=True), headers=headers)
            # returns none if status_code is 200
            result.raise_for_status()

    @log
    def get_origdatablocks(self, dataset_id: int, token: SecretStr) -> List[OrigDataBlock]:
        headers = self._headers(token)
        result = requests.get(
            f"{self._ENDPOINT}{self.API}datasets/{dataset_id}/origdatablocks", headers=headers)
        # returns none if status_code is 200
        result.raise_for_status()

        origdatablocks: List[OrigDataBlock] = []
        for r in result.json():
            try:
                origdatablocks.append(OrigDataBlock.model_validate(r))
            except:
                origdatablocks.append(OrigDataBlock.model_validate_json(r))
        return origdatablocks

    @log
    def get_job_datasetlist(self, job_id: UUID, token: SecretStr) -> List[int]:
        headers = self._headers(token)
        result = requests.get(
            f"{self._ENDPOINT}{self.API}jobs/{job_id}", headers=headers)
        # returns none if status_code is 200
        result.raise_for_status()
        datasets = result.json()["jobParams"]["datasetList"]
        final_list: List[int] = []
        for d in datasets:
            final_list.append(int(d['pid']))
        return final_list

    @log
    def get_datablocks(self, dataset_id: int, token: SecretStr) -> List[DataBlock]:
        headers = self._headers(token)
        result = requests.get(
            f"{self._ENDPOINT}{self.API}datasets/{dataset_id}/datablocks", headers=headers)
        # returns none if status_code is 200
        result.raise_for_status()

        datablocks: List[DataBlock] = []
        for r in result.json():
            try:
                datablocks.append(DataBlock.model_validate(r))
            except:
                datablocks.append(DataBlock.model_validate_json(r))
        return datablocks
