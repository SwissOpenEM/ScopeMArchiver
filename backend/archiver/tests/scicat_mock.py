import requests_mock
import archiver.tasks as tasks


class ScicatMock(requests_mock.Mocker):
    ENDPOINT = "mock://scicat.example.com"

    def __init__(self, job_id: int, dataset_id: int):
        super().__init__()
        self.matchers: dict[str, requests_mock.Request.matcher] = {}

        self.matchers["jobs"] = self.patch(
            f"{self.ENDPOINT}{tasks.scicat.API}/Jobs/{job_id}", json=None)

        self.matchers["datasets"] = self.post(
            f"{self.ENDPOINT}{tasks.scicat.API}/Datasets/{dataset_id}", json=None)

        self.matchers["datablocks"] = self.post(
            f"{self.ENDPOINT}{tasks.scicat.API}/Datablocks/", json=None)

    @property
    def jobs_matcher(self):
        return self.matchers["jobs"]

    @property
    def datasets_matcher(self):
        return self.matchers["datasets"]

    @property
    def datablocks_matcher(self):
        return self.matchers["datablocks"]
