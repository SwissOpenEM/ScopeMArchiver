from enum import StrEnum
import requests
from requests.adapters import HTTPAdapter, Retry
from typing import List
from uuid import UUID
from pydantic import SecretStr

import urllib.parse

from utils.model import (
    Job,
    JobResultObject,
    DataBlock,
    Dataset,
    DatasetLifecycle,
    OrigDataBlock,
)
from utils.log import log
from config.blocks import Blocks


class SciCatClient:
    class STATUSMESSAGE(StrEnum):
        """ These are the /api/v3 values for the job status. 
        """
        IN_PROGRESS = "inProgress"
        FINISHED_SUCCESSFULLY = "finishedSuccessful"
        FINISHED_UNSUCCESSFULLY = "finishedUnsuccessful"
        FINISHED_WITHDATASET_ERRORS = "finishedWithDatasetErrors"

    class JOBSTATUSMESSAGE(StrEnum):
        """Human readible job status

        Newly added property in Scicat /api/v4 allowing for more elaborate messages.
        """

        JOB_IN_PROGRESS = "jobStarted"
        JOB_UPDATED = "jobUpdated"
        JOB_FINISHED = "jobFinished"

    class JOBSTATUSCODE(StrEnum):
        """Job status code in Scicat /api/v4.

        This was previously statusmessage in /api/v3. Values are not restricted but follow the convention of PSI's archiver.

        """

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

    def __init__(
        self,
        endpoint: str = "http://scicat.example.com",
        datasets_api_prefix: str = "",
        api_prefix: str = "",
        jobs_api_prefix: str = "",
    ):
        self._ENDPOINT = endpoint
        self._API_PREFIX = api_prefix
        self._DATASETS_API_PREFIX = datasets_api_prefix
        self._JOBS_API_PREFIX = jobs_api_prefix

        self._session = requests.Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
        self._session.mount("https://", HTTPAdapter(max_retries=retries))

    def _headers(self, token: SecretStr):
        return {
            "Authorization": f"Bearer {token.get_secret_value()}",
            "Content-Type": "application/json",
        }

    def _safe_dataset_id(self, dataset_id: str):
        return urllib.parse.quote(dataset_id, safe="", encoding=None, errors=None)

    def get_token(self) -> str:
        user = Blocks().SCICAT_USER
        password = Blocks().SCICAT_PASSWORD

        resp = self._session.post(
            url=f"{self._ENDPOINT}{self._API_PREFIX}/auth/login",
            data={"username": user, "password": password.get_secret_value()},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    @property
    def API(self):
        return self._API_PREFIX

    @property
    def JOBS_API_PREFIX(self):
        return self._JOBS_API_PREFIX

    @property
    def DATASETS_API_PREFIX(self):
        return self._DATASETS_API_PREFIX

    @log
    def update_job_status_v3(
        self,
        job_id: UUID,
        job_status_message: STATUSMESSAGE,
        job_result_object: JobResultObject | None,
        token: SecretStr,
    ) -> None:
        job = Job(jobStatusMessage=str(job_status_message), jobResultObject=job_result_object)

        headers = self._headers(token)

        result = self._session.patch(
            f"{self._ENDPOINT}{self.JOBS_API_PREFIX}/jobs/{job_id}",
            data=job.model_dump_json(exclude_none=True),
            headers=headers,
        )

        # returns none if status_code is 200
        result.raise_for_status()

    @log
    def update_job_status_v4(
        self,
        job_id: UUID,
        status_code: JOBSTATUSCODE,
        status_message: JOBSTATUSMESSAGE,
        job_result_object: JobResultObject | None,
        token: SecretStr,
    ) -> None:
        job = Job(statusCode=str(status_code), statusMessage=str(status_message), jobResultObject=job_result_object)

        headers = self._headers(token)

        result = self._session.patch(
            f"{self._ENDPOINT}{self.JOBS_API_PREFIX}/jobs/{job_id}",
            data=job.model_dump_json(exclude_none=True),
            headers=headers,
        )

        # returns none if status_code is 200
        result.raise_for_status()

    @log
    def update_archival_dataset_lifecycle(
        self,
        dataset_id: str,
        status: ARCHIVESTATUSMESSAGE,
        token: SecretStr,
        archivable: bool | None = None,
        retrievable: bool | None = None,
    ) -> None:
        dataset = Dataset(
            datasetlifecycle=DatasetLifecycle(
                archiveStatusMessage=str(status),
                archivable=archivable,
                retrievable=retrievable,
            )
        )

        headers = self._headers(token)
        safe_dataset_id = self._safe_dataset_id(dataset_id)
        result = self._session.patch(
            f"{self._ENDPOINT}{self.DATASETS_API_PREFIX}/datasets/{safe_dataset_id}",
            data=dataset.model_dump_json(exclude_none=True),
            headers=headers,
        )
        # returns none if status_code is 200
        result.raise_for_status()

    @log
    def update_retrieval_dataset_lifecycle(
        self,
        dataset_id: str,
        status: RETRIEVESTATUSMESSAGE,
        token: SecretStr,
        archivable: bool | None = None,
        retrievable: bool | None = None,
    ) -> None:
        dataset = Dataset(
            datasetlifecycle=DatasetLifecycle(
                retrieveStatusMessage=str(status),
                archivable=archivable,
                retrievable=retrievable,
            )
        )
        headers = self._headers(token)
        safe_dataset_id = self._safe_dataset_id(dataset_id)
        result = self._session.patch(
            f"{self._ENDPOINT}{self.DATASETS_API_PREFIX}/datasets/{safe_dataset_id}",
            data=dataset.model_dump_json(exclude_none=True),
            headers=headers,
        )
        # returns none if status_code is 200
        result.raise_for_status()

    @log
    def register_datablocks(self, dataset_id: str, data_blocks: List[DataBlock], token: SecretStr) -> None:
        headers = self._headers(token)
        safe_dataset_id = self._safe_dataset_id(dataset_id)
        for d in data_blocks:
            result = self._session.post(
                f"{self._ENDPOINT}{self.DATASETS_API_PREFIX}/datasets/{safe_dataset_id}/datablocks",
                data=d.model_dump_json(exclude_none=True),
                headers=headers,
            )
            # returns none if status_code is 200
            result.raise_for_status()

    @log
    def delete_datablocks(self, dataset_id: str, data_blocks: List[DataBlock], token: SecretStr) -> None:
        headers = self._headers(token)
        safe_dataset_id = self._safe_dataset_id(dataset_id)
        for d in data_blocks:
            result = self._session.delete(
                f"{self._ENDPOINT}{self.DATASETS_API_PREFIX}/datasets/{safe_dataset_id}/datablocks/{d.id}",
                headers=headers,
            )
            # returns none if status_code is 200
            result.raise_for_status()

    @log
    def get_origdatablocks(self, dataset_id: str, token: SecretStr) -> List[OrigDataBlock]:
        headers = self._headers(token)
        safe_dataset_id = self._safe_dataset_id(dataset_id)
        result = self._session.get(
            f"{self._ENDPOINT}{self.DATASETS_API_PREFIX}/datasets/{safe_dataset_id}/origdatablocks",
            headers=headers,
        )
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
    def get_job_datasetlist(self, job_id: UUID, token: SecretStr) -> List[str]:
        headers = self._headers(token)
        result = self._session.get(f"{self._ENDPOINT}{self.JOBS_API_PREFIX}/jobs/{job_id}", headers=headers)
        # returns none if status_code is 200
        result.raise_for_status()
        # v3
        datasets = result.json().get("datasetList", [])
        if not datasets:
            # #v4
            datasets = result.json().get("jobParams")["datasetList"]
        final_list = [d["pid"] for d in datasets]
        return final_list

    @log
    def get_datablocks(self, dataset_id: str, token: SecretStr) -> List[DataBlock]:
        headers = self._headers(token)
        safe_dataset_id = self._safe_dataset_id(dataset_id)
        result = self._session.get(
            f"{self._ENDPOINT}{self.DATASETS_API_PREFIX}/datasets/{safe_dataset_id}/datablocks",
            headers=headers,
        )
        # returns none if status_code is 200
        result.raise_for_status()

        datablocks: List[DataBlock] = []
        for r in result.json():
            try:
                datablocks.append(DataBlock.model_validate(r))
            except:
                datablocks.append(DataBlock.model_validate_json(r))
        return datablocks
