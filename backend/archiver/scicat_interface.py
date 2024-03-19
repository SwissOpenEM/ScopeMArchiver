from enum import Enum
import logging
import requests
import time
from typing import List

_LOGGER = logging.getLogger("Jobs")


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

    _API = "api/v3"

    def __init__(self, endpoint: str):
        self._ENDPOINT = endpoint

    def update_job_status(self, job_id: int, status: JOBSTATUS):
        time.sleep(1)
        requests.put(f"{self._ENDPOINT}/{SciCat._API}/Jobs/{job_id}", data={
            "status": "inProgress"
        })

    def update_dataset_lifecycle(self, dataset_id: int, status: DATASETSTATUS):
        time.sleep(1)
        requests.put(f"{self._ENDPOINT}/{SciCat._API}/Datasets/{dataset_id}", data={
            "datasetlifecyle": {"archivable": "false", "retrievable": "False",
                                "archiveStatusMessage": "started"
                                }
        })
        _LOGGER.info(
            f"Update dataset lifecycle  to {status} for dataset {dataset_id}")

    def update_datablocks(self, dataset_id: int, datablocks: List):
        pass
