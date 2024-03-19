import requests_mock
from unittest.mock import patch
import archiver.tasks as tasks


@patch("archiver.tasks.scicat._ENDPOINT", "mock://scicat.example.com")
def test_scicat_job_status():
    with requests_mock.Mocker() as m:
        adapter = m.put(
            f"mock://scicat.example.com/{tasks.SciCat._API}/Jobs/123", json=None)
        tasks.scicat.update_job_status(
            job_id=123, status=tasks.scicat.JOBSTATUS.IN_PROGRESS)

        assert adapter.called
        assert adapter.last_request.text == "status=inProgress"


class TaskTest():
    pass
