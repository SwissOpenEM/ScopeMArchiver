from typing import List
import requests_mock
import archiver.scicat_tasks as tasks
from archiver.model import DataFile, OrigDataBlock


class ScicatMock(requests_mock.Mocker):
    ENDPOINT = "mock://scicat.example.com"

    def create_orig_datablocks(self, num_blocks: int = 10, num_files_per_block: int = 10) -> List[OrigDataBlock]:
        size_per_file = 1024 * 1024 * 100
        blocks: List[OrigDataBlock] = []
        for k in range(num_blocks):
            b = OrigDataBlock(
                id=f"Block_{k}",
                size=size_per_file * num_files_per_block,
                ownerGroup="me",
                dataFileList=[]
            )
            for i in range(num_files_per_block):
                d = DataFile(
                    path=f"/some/path/file_{i}.png",
                    size=size_per_file
                )
                b.dataFileList.append(d)
            blocks.append(b)
        return blocks

    def __init__(self, job_id: int, dataset_id: int, num_blocks: int = 10, num_files_per_block: int = 10):
        super().__init__()

        self.matchers: dict[str, requests_mock.Request.matcher] = {}

        self.matchers["jobs"] = self.patch(
            f"{self.ENDPOINT}{tasks.scicat.API}/Jobs/{job_id}", json=None)

        self.matchers["datasets"] = self.post(
            f"{self.ENDPOINT}{tasks.scicat.API}/Datasets/{dataset_id}", json=None)

        self.matchers["datablocks"] = self.post(
            f"{self.ENDPOINT}{tasks.scicat.API}/Datablocks/", json=None)

        origdatablocks = self.create_orig_datablocks(
            num_blocks, num_files_per_block)
        json_list = []
        for o in origdatablocks:
            json_list.append(o.model_dump_json())

        self.matchers["origdatablocks"] = self.get(
            f"{self.ENDPOINT}{tasks.scicat.API}/Datasets/{dataset_id}/origdatablocks", json=json_list)

    @property
    def jobs_matcher(self):
        return self.matchers["jobs"]

    @property
    def datasets_matcher(self):
        return self.matchers["datasets"]

    @property
    def datablocks_matcher(self):
        return self.matchers["datablocks"]

    @property
    def origdatablocks_matcher(self):
        return self.matchers["origdatablocks"]
