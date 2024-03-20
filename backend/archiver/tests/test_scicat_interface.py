import requests_mock
from unittest.mock import patch
import archiver.tasks as tasks
import pytest


@patch("archiver.tasks.scicat._ENDPOINT", "mock://scicat.example.com")
def test_scicat_job_status():
    with requests_mock.Mocker() as m:
        adapter = m.put(
            f"mock://scicat.example.com/{tasks.SciCat._API}/Jobs/123", json=None)
        tasks.scicat.update_job_status(
            job_id=123, status=tasks.scicat.JOBSTATUS.IN_PROGRESS)

        assert adapter.called
        assert adapter.last_request.json() == {'status': "inProgress"}


@pytest.mark.parametrize("dataset_id,dataset_status", [
    (123, tasks.scicat.DATASETSTATUS.ARCHIVABLE),
    (456, tasks.scicat.DATASETSTATUS.RETRIEVABLE),
])
@patch("archiver.tasks.scicat._ENDPOINT", "mock://scicat.example.com")
def test_scicat_dataset_lifecycle(dataset_id, dataset_status):
    with requests_mock.Mocker() as m:
        adapter = m.post(
            f"mock://scicat.example.com/{tasks.SciCat._API}/Datasets/{dataset_id}", json=None)

        tasks.scicat.update_dataset_lifecycle(
            dataset_id=dataset_id, status=dataset_status)

        match dataset_status:
            case tasks.SciCat.DATASETSTATUS.ARCHIVABLE:
                expected_json = {"datasetlifecyle": {"archivable": "True", "retrievable": "False",
                                                     "archiveStatusMessage": "started"}}
            case tasks.SciCat.DATASETSTATUS.RETRIEVABLE:
                expected_json = {"datasetlifecyle": {"archivable": "false", "retrievable": "True",
                                                     "archiveStatusMessage": "dataOnArchiveDisk"}}

        assert adapter.called
        assert adapter.last_request.json() == expected_json
