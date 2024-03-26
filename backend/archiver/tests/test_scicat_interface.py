import requests_mock
from unittest.mock import patch
import archiver.tasks as tasks
import pytest
from archiver.tests.scicat_mock import ScicatMock


@pytest.mark.parametrize("job_id,job_status", [
    (123, tasks.scicat.JOBSTATUS.FINISHED_SUCCESSFULLY),
    (456, tasks.scicat.JOBSTATUS.FINISHED_UNSUCCESSFULLY),
])
@patch("archiver.tasks.scicat._ENDPOINT", "mock://scicat.example.com")
def test_scicat_job_status(job_id, job_status):
    with ScicatMock(job_id=job_id, dataset_id=None) as m:
        tasks.scicat.update_job_status(
            job_id=job_id, status=job_status)

        assert m.jobs_matcher.called
        assert m.jobs_matcher.last_request.json() == {'status': "inProgress"}


@pytest.mark.parametrize("dataset_id,dataset_status", [
    (123, tasks.scicat.DATASETSTATUS.ARCHIVABLE),
    (456, tasks.scicat.DATASETSTATUS.RETRIEVABLE),
])
@patch("archiver.tasks.scicat._ENDPOINT", "mock://scicat.example.com")
def test_scicat_dataset_lifecycle(dataset_id, dataset_status):
    with ScicatMock(job_id=None, dataset_id=dataset_id) as m:

        tasks.scicat.update_dataset_lifecycle(
            dataset_id=dataset_id, status=dataset_status)

        match dataset_status:
            case tasks.SciCat.DATASETSTATUS.ARCHIVABLE:
                expected_json = {"datasetlifecyle": {"archivable": "True", "retrievable": "False",
                                                     "archiveStatusMessage": "started"}}
            case tasks.SciCat.DATASETSTATUS.RETRIEVABLE:
                expected_json = {"datasetlifecyle": {"archivable": "false", "retrievable": "True",
                                                     "archiveStatusMessage": "dataOnArchiveDisk"}}

        assert m.datasets_matcher.called
        assert m.datasets_matcher.last_request.json() == expected_json
