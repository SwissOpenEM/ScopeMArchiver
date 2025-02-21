from unittest.mock import patch, MagicMock, call
import pytest
from uuid import UUID, uuid4

from prefect.testing.utilities import prefect_test_harness

from archiver.flows.retrieve_datasets_flow import retrieve_datasets_flow
from archiver.flows.tests.scicat_unittest_mock import ScicatMock, mock_scicat_client
from archiver.flows.tests.helpers import (
    create_datablocks,
    create_orig_datablocks,
    mock_s3client,
)
from archiver.flows.tests.helpers import (
    expected_retrieval_dataset_lifecycle,
    expected_job_status,
    expected_jobresultsobject,
)
from archiver.scicat.scicat_interface import SciCatClient
from archiver.flows.utils import StoragePaths
from archiver.utils.model import DataBlock
from archiver.config.variables import Variables


def mock_get_datablock_path_in_LTS(datablock: DataBlock):
    return Variables().LTS_STORAGE_ROOT / datablock.archiveId


def mock_create_presigned_url(*args, **kwargs) -> str:
    return ""


def mock_raise_system_error(*args, **kwargs):
    raise SystemError("mock system error")


def mock_scicat_get_token() -> str:
    return "secret-test-string"


async def mock_wait_for_file_accessible(file, timeout_s=360) -> bool:
    return True


@pytest.mark.parametrize(
    "job_id,dataset_id",
    [
        (uuid4(), "somePrefix/456"),
    ],
)
@patch("archiver.scicat.scicat_tasks.scicat_client", mock_scicat_client)
@patch(
    "archiver.utils.datablocks.get_datablock_path_in_LTS",
    mock_get_datablock_path_in_LTS,
)
@patch("archiver.utils.datablocks.wait_for_file_accessible", mock_wait_for_file_accessible)
@patch("archiver.utils.datablocks.copy_file_to_folder")
@patch("archiver.scicat.scicat_tasks.create_presigned_url", mock_create_presigned_url)
@patch("archiver.utils.datablocks.upload_datablock")
@patch("archiver.utils.datablocks.cleanup_lts_folder")
@patch("archiver.utils.datablocks.cleanup_scratch")
@patch("archiver.utils.datablocks.cleanup_s3_staging")
@patch("archiver.utils.datablocks.cleanup_s3_landingzone")
@patch("archiver.utils.datablocks.cleanup_s3_retrieval")
def test_scicat_api_retrieval(
    mock_cleanup_s3_retrieval: MagicMock,
    mock_cleanup_s3_landingzone: MagicMock,
    mock_cleanup_s3_staging: MagicMock,
    mock_cleanup_scratch: MagicMock,
    mock_cleanup_lts: MagicMock,
    mock_upload_datablock: MagicMock,
    mock_copy_file_to_folder: MagicMock,
    job_id: UUID,
    dataset_id: str,
    mocked_s3,
):
    # data in LTS
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
        try:
            retrieve_datasets_flow(job_id=job_id, dataset_ids=[dataset_id])
        except Exception:
            pass

        assert m.jobs_matcher.call_count == 2
        assert m.jobs_matcher.request_history[0].json() == expected_job_status(
            SciCatClient.JOBTYPE.RETRIEVE, SciCatClient.JOBSTATUS.IN_PROGRESS
        )

        expected_job = expected_job_status(
            SciCatClient.JOBTYPE.RETRIEVE, SciCatClient.JOBSTATUS.FINISHED_SUCCESSFULLY
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

        mock_upload_datablock.assert_called()
        mock_cleanup_s3_staging.assert_not_called()
        mock_cleanup_s3_retrieval.assert_not_called()
        mock_cleanup_s3_landingzone.assert_not_called()
        mock_cleanup_s3_staging.assert_not_called()
        mock_cleanup_scratch.assert_called_once_with(dataset_id)
        mock_cleanup_lts.assert_not_called()

        dst_folder = StoragePaths.scratch_archival_datablocks_folder(dataset_id)
        calls = [
            call(
                src_file=Variables().LTS_STORAGE_ROOT / d.archiveId,
                dst_folder=dst_folder,
            )
            for d in datablocks
        ]

        mock_copy_file_to_folder.assert_has_calls(calls, any_order=True)


@pytest.mark.parametrize(
    "job_id,dataset_id",
    [
        (uuid4(), "somePrefix/456"),
    ],
)
@patch("archiver.scicat.scicat_tasks.scicat_client", mock_scicat_client)
@patch("archiver.utils.datablocks.get_datablock_path_in_LTS", mock_raise_system_error)
@patch("archiver.utils.datablocks.wait_for_file_accessible", mock_wait_for_file_accessible)
@patch("archiver.utils.datablocks.copy_file_to_folder")
@patch("archiver.scicat.scicat_tasks.create_presigned_url", mock_create_presigned_url)
@patch("archiver.utils.datablocks.upload_datablock")
@patch("archiver.utils.datablocks.cleanup_lts_folder")
@patch("archiver.utils.datablocks.cleanup_scratch")
@patch("archiver.utils.datablocks.cleanup_s3_staging")
@patch("archiver.utils.datablocks.cleanup_s3_landingzone")
@patch("archiver.utils.datablocks.cleanup_s3_retrieval")
def test_datablock_not_found(
    mock_cleanup_s3_retrieval: MagicMock,
    mock_cleanup_s3_landingzone: MagicMock,
    mock_cleanup_s3_staging: MagicMock,
    mock_cleanup_scratch: MagicMock,
    mock_cleanup_lts: MagicMock,
    mock_upload_datablock: MagicMock,
    mock_copy_file_to_folder: MagicMock,
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
            retrieve_datasets_flow(job_id=job_id, dataset_ids=[dataset_id])
        except Exception:
            pass

        assert m.jobs_matcher.call_count == 2
        assert m.jobs_matcher.request_history[0].json() == expected_job_status(
            SciCatClient.JOBTYPE.RETRIEVE, SciCatClient.JOBSTATUS.IN_PROGRESS
        )

        assert m.jobs_matcher.request_history[1].json() == expected_job_status(
            SciCatClient.JOBTYPE.RETRIEVE,
            SciCatClient.JOBSTATUS.FINISHED_UNSUCCESSFULLY,
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
        mock_cleanup_s3_retrieval.assert_called_once_with(expected_s3_client, dataset_id)
        mock_cleanup_s3_landingzone.assert_not_called()
        mock_cleanup_s3_staging.assert_not_called()
        mock_cleanup_scratch.assert_called_once_with(dataset_id)
        mock_cleanup_lts.assert_not_called()
        mock_copy_file_to_folder.assert_not_called()
