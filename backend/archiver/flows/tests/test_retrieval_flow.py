from unittest.mock import patch, MagicMock
import pytest
from uuid import UUID, uuid4

from prefect.testing.utilities import prefect_test_harness
from prefect.exceptions import UnfinishedRun

# fmt: off
from flows.retrieve_datasets_flow import retrieve_datasets_flow
from flows.tests.scicat_unittest_mock import ScicatMock, mock_scicat_client
from flows.tests.helpers import (
    create_datablocks,
    create_orig_datablocks,
    mock_s3client,
)
from flows.tests.helpers import (
    expected_retrieval_dataset_lifecycle,
    expected_job_status,
    expected_jobresultsobject,
)
from scicat.scicat_interface import SciCatClient
# fmt: on


def mock_create_presigned_url(*args, **kwargs) -> str:
    return ""


def mock_raise_system_error(*args, **kwargs):
    raise SystemError("mock system error")


def mock_scicat_get_token() -> str:
    return "secret-test-string"


def mock_restore_datablock(*args, **kwargs):
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "job_id,dataset_id",
    [
        (uuid4(), "somePrefix/456"),
    ],
)
@patch("scicat.scicat_tasks.scicat_client", mock_scicat_client)
@patch("scicat.scicat_tasks.create_presigned_url", mock_create_presigned_url)
@patch("utils.datablocks.restore_datablock", mock_restore_datablock)
@patch("utils.datablocks.cleanup_scratch")
@patch("utils.datablocks.cleanup_s3_landingzone")
async def test_scicat_api_retrieval(
    mock_cleanup_s3_landingzone: MagicMock,
    mock_cleanup_scratch: MagicMock,
    job_id: UUID,
    dataset_id: str,
    mocked_s3,
):
    # datablock in SciCat mock
    num_orig_datablocks = 10
    num_datablocks = 10
    num_files_per_block = 10
    origDataBlocks = create_orig_datablocks(
        num_blocks=num_orig_datablocks, num_files_per_block=num_files_per_block
    )
    datablocks = create_datablocks(num_blocks=num_datablocks, num_files_per_block=num_files_per_block)

    with (
        ScicatMock(
            job_id=job_id,
            dataset_id=dataset_id,
            origDataBlocks=origDataBlocks,
            datablocks=datablocks,
        ) as m,
        prefect_test_harness(),
    ):
        await retrieve_datasets_flow(job_id=job_id)

        assert m.jobs_matcher.call_count == 2
        assert m.jobs_matcher.request_history[0].json() == expected_job_status(
            SciCatClient.JOBTYPE.RETRIEVE, SciCatClient.STATUSMESSAGE.IN_PROGRESS
        )

        expected_job = expected_job_status(
            SciCatClient.JOBTYPE.RETRIEVE, SciCatClient.STATUSMESSAGE.FINISHED_SUCCESSFULLY
        )

        expected_job["jobResultObject"] = expected_jobresultsobject(
            dataset_id=dataset_id, datablocks=datablocks
        )

        assert m.jobs_matcher.request_history[1].json() == expected_job

        assert m.datasets_matcher.call_count == 2

        assert m.datasets_matcher.request_history[0].json() == expected_retrieval_dataset_lifecycle(
            status=SciCatClient.RETRIEVESTATUSMESSAGE.STARTED,
            archivable=False,
            retrievable=True,
        )

        assert m.datasets_matcher.request_history[1].json() == expected_retrieval_dataset_lifecycle(
            status=SciCatClient.RETRIEVESTATUSMESSAGE.DATASET_RETRIEVED,
            archivable=False,
            retrievable=True,
        )

        mock_cleanup_s3_landingzone.assert_not_called()
        mock_cleanup_scratch.assert_called_once_with(dataset_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "job_id,dataset_id",
    [
        (uuid4(), "somePrefix/456"),
    ],
)
@patch("scicat.scicat_tasks.scicat_client", mock_scicat_client)
@patch("scicat.scicat_tasks.create_presigned_url", mock_create_presigned_url)
@patch("scicat.scicat_tasks.create_presigned_url", mock_create_presigned_url)
@patch("utils.datablocks.restore_datablock", mock_raise_system_error)
@patch("utils.datablocks.upload_datablock")
@patch("utils.datablocks.cleanup_scratch")
@patch("utils.datablocks.cleanup_s3_landingzone")
async def test_datablock_not_found(
    mock_cleanup_s3_landingzone: MagicMock,
    mock_cleanup_scratch: MagicMock,
    mock_upload_datablock: MagicMock,
    job_id,
    dataset_id,
    mocked_s3,
):
    num_orig_datablocks = 10
    num_datablocks = 10
    num_files_per_block = 1
    origDataBlocks = create_orig_datablocks(
        num_blocks=num_orig_datablocks, num_files_per_block=num_files_per_block
    )
    datablocks = create_datablocks(num_blocks=num_datablocks, num_files_per_block=num_files_per_block)
    expected_s3_client = mock_s3client()

    with (
        ScicatMock(
            job_id=job_id,
            dataset_id=dataset_id,
            origDataBlocks=origDataBlocks,
            datablocks=datablocks,
        ) as m,
        prefect_test_harness(),
    ):
        try:
            await retrieve_datasets_flow(job_id=job_id)
        except UnfinishedRun:
            # https://github.com/PrefectHQ/prefect/issues/12028
            pass
        except Exception as e:
            raise e

        assert m.jobs_matcher.call_count == 2
        assert m.jobs_matcher.request_history[0].json() == expected_job_status(
            SciCatClient.JOBTYPE.RETRIEVE, SciCatClient.STATUSMESSAGE.IN_PROGRESS
        )

        assert m.jobs_matcher.request_history[1].json() == expected_job_status(
            SciCatClient.JOBTYPE.RETRIEVE,
            SciCatClient.STATUSMESSAGE.FINISHED_UNSUCCESSFULLY,
        )

        assert m.datasets_matcher.call_count == 2
        assert m.datasets_matcher.request_history[0].json() == expected_retrieval_dataset_lifecycle(
            status=SciCatClient.RETRIEVESTATUSMESSAGE.STARTED,
            archivable=False,
            retrievable=True,
        )

        assert m.datasets_matcher.request_history[1].json() == expected_retrieval_dataset_lifecycle(
            status=SciCatClient.RETRIEVESTATUSMESSAGE.DATASET_RETRIEVAL_FAILED,
            archivable=False,
            retrievable=True,
        )

        mock_upload_datablock.assert_not_called()
        mock_cleanup_s3_landingzone.assert_not_called()
        mock_cleanup_scratch.assert_called_once_with(dataset_id)
