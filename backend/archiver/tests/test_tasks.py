
from unittest.mock import patch
import pytest
from celery import shared_task, exceptions

from archiver.tasks import create_archiving_pipeline
from archiver.scicat_interface import SciCat
from archiver.tests.scicat_mock import ScicatMock
from archiver.model import Job


def job_status_json(job_id: int, job_type: str, status: SciCat.JOBSTATUS):
    match status:
        case SciCat.JOBSTATUS.IN_PROGRESS:
            return Job(id=str(job_id), type=job_type, jobStatusMessage="inProgress").model_dump_json()
        case SciCat.JOBSTATUS.FINISHED_SUCCESSFULLY:
            return Job(id=str(job_id), type=job_type, jobStatusMessage="finishedSuccessful").model_dump_json()
        case SciCat.JOBSTATUS.FINISHED_UNSUCCESSFULLY:
            return Job(id=str(job_id), type=job_type, jobStatusMessage="finishedUnsuccessful").model_dump_json()
        case SciCat.JOBSTATUS.FINISHED_WITHDATASET_ERRORS:
            return Job(id=str(job_id), type=job_type, jobStatusMessage="finishedWithDatasetErrors").model_dump_json()


@pytest.mark.parametrize("job_id,dataset_id", [
    (123, 456),
])
@patch("archiver.tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
def test_archiving_flow(celery_worker, job_id, dataset_id):
    with ScicatMock(job_id=job_id, dataset_id=dataset_id) as m:
        res = create_archiving_pipeline(job_id=job_id, dataset_id=dataset_id, origDataBlocks=["", ""])()
        res.get()

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 3

        # 3: Update job status
        assert m.jobs_matcher.request_history[0].json() == job_status_json(
            job_id, "archive", SciCat.JOBSTATUS.IN_PROGRESS)

        # 4: Update datablock lifelcycle
        assert m.datasets_matcher.called is True

        # 5: Create datablocks TODO: mock of landingzone needed

        # 11: Register Datablocks

        # 12: Update datablock lifecycle

        # 13: Move datablocks TODO: LTS mock

        # 13: Validate datablocks TODO: Validation mock

        # 19: Update job status
        assert m.jobs_matcher.request_history[1].json() == job_status_json(
            job_id, "archive", SciCat.JOBSTATUS.FINISHED_SUCCESSFULLY)

        # 20: Update datablock lifelcycle
        assert m.datasets_matcher.called is True


@shared_task
def raise_expection_task(result=None, **args):
    raise Exception("Mock Exception")


@shared_task
def on_error(request, exc, traceback):
    pass


@patch("archiver.tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
@patch("archiver.tasks.create_datablocks", raise_expection_task)
def test_datablock_failure(celery_app, celery_worker):

    with ScicatMock(job_id=1, dataset_id=2) as m:
        res = create_archiving_pipeline(1, 2)()
        res.get()

        # 3:
        assert m.adapters["jobs"].called is True
