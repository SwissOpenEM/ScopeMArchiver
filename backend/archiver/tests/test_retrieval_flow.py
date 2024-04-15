from unittest.mock import patch
import pytest

from archiver.flows.retrieval_flow import create_retrieval_flow
from archiver.tests.scicat_mock import ScicatMock


@pytest.mark.skip
@pytest.mark.parametrize("job_id,dataset_id", [
    (123, 456),
])
@patch("archiver.tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
def test_scicat_api_retrieval(celery_app, celery_worker, job_id, dataset_id):
    with ScicatMock(job_id=job_id, dataset_id=dataset_id) as m:
        res = create_retrieval_flow(job_id=job_id, dataset_id=dataset_id)()
        res.get()

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 2
