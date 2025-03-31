from typing import List
import requests_mock
from uuid import UUID
import urllib.parse

from archiver.scicat.scicat_interface import SciCatClient
from archiver.utils.model import OrigDataBlock, DataBlock


def mock_scicat_get_token() -> str:
    return "secret-test-string"


def mock_scicat_client() -> SciCatClient:
    scicat_instance = SciCatClient(
        endpoint=ScicatMock.ENDPOINT,
        api_prefix=ScicatMock.API_PREFIX,
        jobs_api_prefix=ScicatMock.JOBS_API_PREFIX,
    )
    setattr(scicat_instance, "get_token", mock_scicat_get_token)
    return scicat_instance


class ScicatMock(requests_mock.Mocker):
    ENDPOINT = "mock://scicat.example.com"
    API_PREFIX = "/api/v1"
    JOBS_API_PREFIX = "/api/v4"

    def __init__(
        self,
        job_id: UUID,
        dataset_id: str,
        origDataBlocks: List[OrigDataBlock],
        datablocks: List[DataBlock],
    ):
        super().__init__()

        safe_dataset_url = urllib.parse.quote(dataset_id, safe="", encoding=None, errors=None)

        self.matchers: dict[str, requests_mock.Request.matcher] = {}

        self.matchers["jobs"] = self.patch(f"{self.ENDPOINT}{self.JOBS_API_PREFIX}/jobs/{job_id}", json=None)

        self.matchers["datasets"] = self.patch(
            f"{self.ENDPOINT}{self.API_PREFIX}/datasets/{safe_dataset_url}", json=None
        )

        self.matchers["post_datablocks"] = self.post(
            f"{self.ENDPOINT}{self.API_PREFIX}/datasets/{safe_dataset_url}/datablocks",
            json=None,
        )

        json_list = []
        for o in origDataBlocks:
            json_list.append(o.model_dump_json())

        self.matchers["origdatablocks"] = self.get(
            f"{self.ENDPOINT}{self.API_PREFIX}/datasets/{safe_dataset_url}/origdatablocks",
            json=json_list,
        )

        json_list = []
        for o in datablocks:
            json_list.append(o.model_dump_json())

        self.matchers["get_datablocks"] = self.get(
            f"{self.ENDPOINT}{self.API_PREFIX}/datasets/{safe_dataset_url}/datablocks",
            json=json_list,
        )

    @property
    def jobs_matcher(self):
        return self.matchers["jobs"]

    @property
    def datasets_matcher(self):
        return self.matchers["datasets"]

    @property
    def datablocks_post_matcher(self):
        return self.matchers["post_datablocks"]

    @property
    def datablocks_get_matcher(self):
        return self.matchers["get_datablocks"]

    @property
    def origdatablocks_matcher(self):
        return self.matchers["origdatablocks"]
