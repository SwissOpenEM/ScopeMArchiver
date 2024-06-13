from unittest.mock import patch
import archiver.scicat.scicat_tasks as tasks
import pytest
from archiver.tests.scicat_unittest_mock import ScicatMock


@pytest.mark.skip
@pytest.mark.parametrize("job_id,job_status", [
    (123, tasks.scicat.JOBSTATUS.FINISHED_SUCCESSFULLY),
    (456, tasks.scicat.JOBSTATUS.FINISHED_UNSUCCESSFULLY),
])
@ patch("archiver.scicat_tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
def test_scicat_job_status(job_id, job_status):
    with ScicatMock(job_id=job_id, dataset_id=None) as m:
        tasks.scicat.update_job_status(job_id=job_id, status=job_status)

        assert m.jobs_matcher.called
        assert m.jobs_matcher.last_request.json() == {'status': str(job_status)}


@pytest.mark.skip
@pytest.mark.parametrize("dataset_id,dataset_status", [
    (123, tasks.scicat.ARCHIVESTATUSMESSAGE.STARTED),
    (456, tasks.scicat.ARCHIVESTATUSMESSAGE.DATASETONARCHIVEDISK),
])
@ patch("archiver.scicat_tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
def test_scicat_dataset_lifecycle(dataset_id, dataset_status):
    with ScicatMock(job_id=None, dataset_id=dataset_id) as m:

        tasks.scicat.update_dataset_lifecycle(
            dataset_id=dataset_id, status=dataset_status)

        match dataset_status:
            case tasks.SciCat.ARCHIVESTATUSMESSAGE.ARCHIVABLE:
                expected_json = {"datasetlifecyle": {"archivable": "True", "retrievable": "False",
                                                     "archiveStatusMessage": "started"}}
            case tasks.SciCat.ARCHIVESTATUSMESSAGE.RETRIEVABLE:
                expected_json = {"datasetlifecyle": {"archivable": "false", "retrievable": "True",
                                                     "archiveStatusMessage": "dataOnArchiveDisk"}}

        assert m.datasets_matcher.called
        assert m.datasets_matcher.last_request.json() == expected_json
