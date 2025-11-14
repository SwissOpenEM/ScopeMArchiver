from pathlib import Path
from unittest.mock import patch, MagicMock
from uuid import UUID, uuid4


import pytest
from prefect.testing.utilities import prefect_test_harness

from flows.archive_datasets_flow import archive_datasets_flow
from scicat.scicat_interface import SciCatClient
from flows.tests.scicat_unittest_mock import ScicatMock, mock_scicat_client
from flows.flow_utils import DatasetError, SystemError
from flows.tests.helpers import (
    mock_s3client,
    create_datablocks,
    create_orig_datablocks,
    mock_create_datablock_entries,
    expected_datablocks,
    expected_archival_dataset_lifecycle,
    expected_job_status,
)


def raise_user_error(*args, **kwargs):
    raise DatasetError("Mock Dataset Error")


def raise_system_error(*args, **kwargs):
    raise SystemError("Mock System Error")


def mock_void_function(*args, **kwargs):
    pass


def mock_empty_list(*args, **kwargs):
    return []


def mock_list(*args, **kwargs):
    return [1]


def mock_archive_datablock(*args, **kwargs):
    pass


def mock_archive_file(file: Path):
    pass


@pytest.mark.parametrize(
    "job_id,dataset_id",
    [
        (uuid4(), "somePrefix/456"),
    ],
)
@patch("scicat.scicat_tasks.scicat_client", mock_scicat_client)
@patch("utils.datablocks.list_datablocks", mock_list)
@patch("utils.datablocks.download_objects_from_s3", mock_list)
@patch("utils.datablocks.create_tarfiles", mock_void_function)
@patch("utils.datablocks.create_datablock_entries", mock_create_datablock_entries)
@patch("utils.datablocks.upload_objects_to_s3", mock_void_function)
@patch("utils.datablocks.verify_objects", mock_empty_list)
@patch("utils.datablocks.calculate_checksum", mock_empty_list)
@patch("utils.datablocks.verify_checksum", mock_void_function)
@patch("utils.datablocks.verify_datablock_content", mock_void_function)
@patch("utils.datablocks.archive_datablock", mock_archive_datablock)
@patch("utils.datablocks.cleanup_scratch")
@patch("utils.datablocks.cleanup_s3_staging")
@patch("utils.datablocks.cleanup_s3_landingzone")
@patch("utils.datablocks.cleanup_s3_retrieval")
def test_scicat_api_archiving(
    mock_cleanup_s3_retrieval: MagicMock,
    mock_cleanup_s3_landingzone: MagicMock,
    mock_cleanup_s3_staging: MagicMock,
    mock_cleanup_scratch: MagicMock,
    job_id: UUID,
    dataset_id: str,
    mocked_s3,
):
    num_orig_datablocks = 10
    num_files_per_block = 10
    num_datablocks = 10
    num_expected_datablocks = num_orig_datablocks

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
            archive_datasets_flow(job_id=job_id, dataset_ids=[dataset_id])
        except Exception:
            pass

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 2
        assert m.datablocks_post_matcher.call_count == num_expected_datablocks
        assert all([d.call_count == 0 for d in m.datablocks_delete_matcher])

        assert m.jobs_matcher.request_history[0].json() == expected_job_status(
            "archive", SciCatClient.STATUSMESSAGE.IN_PROGRESS
        )

        assert m.datasets_matcher.request_history[0].json() == expected_archival_dataset_lifecycle(
            SciCatClient.ARCHIVESTATUSMESSAGE.STARTED
        )

        for i in range(num_expected_datablocks):
            assert m.datablocks_post_matcher.request_history[i].json() == expected_datablocks(dataset_id, i)

        assert m.datasets_matcher.request_history[1].json() == expected_archival_dataset_lifecycle(
            SciCatClient.ARCHIVESTATUSMESSAGE.DATASET_ON_ARCHIVEDISK,
            archivable=False,
            retrievable=True,
        )

        assert m.jobs_matcher.request_history[1].json() == expected_job_status(
            "archive", SciCatClient.STATUSMESSAGE.FINISHED_SUCCESSFULLY
        )

        mock_cleanup_s3_retrieval.assert_not_called()
        mock_cleanup_s3_landingzone.assert_called_once_with(expected_s3_client, dataset_id)
        mock_cleanup_s3_staging.assert_called_once_with(expected_s3_client, dataset_id)
        mock_cleanup_scratch.assert_called_once_with(dataset_id)


@pytest.mark.parametrize(
    "job_id,dataset_id",
    [
        (uuid4(), "somePrefix/456"),
    ],
)
@patch("scicat.scicat_tasks.scicat_client", mock_scicat_client)
@patch("utils.datablocks.list_datablocks", raise_user_error)
@patch("utils.datablocks.download_objects_from_s3", mock_list)
@patch("utils.datablocks.create_tarfiles", mock_void_function)
@patch("utils.datablocks.create_datablock_entries", mock_create_datablock_entries)
@patch("utils.datablocks.upload_objects_to_s3", mock_void_function)
@patch("utils.datablocks.verify_objects", mock_empty_list)
@patch("utils.datablocks.cleanup_scratch")
@patch("utils.datablocks.cleanup_s3_staging")
@patch("utils.datablocks.cleanup_s3_landingzone")
@patch("utils.datablocks.cleanup_s3_retrieval")
def test_create_datablocks_user_error(
    mock_cleanup_s3_retrieval: MagicMock,
    mock_cleanup_s3_landingzone: MagicMock,
    mock_cleanup_s3_staging: MagicMock,
    mock_cleanup_scratch: MagicMock,
    job_id: UUID,
    dataset_id: str,
    mocked_s3,
):
    num_orig_datablocks = 10
    num_files_per_block = 10
    num_datablocks = 10

    # datablocks created but not moved to staging, therefore none reported
    num_expected_datablocks = 0
    expected_s3_client = mock_s3client()
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
        with pytest.raises(Exception):
            archive_datasets_flow(job_id=job_id, dataset_ids=[dataset_id])

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 2
        assert m.datablocks_post_matcher.call_count == num_expected_datablocks
        assert all([d.call_count == 1 for d in m.datablocks_delete_matcher])

        assert m.jobs_matcher.request_history[0].json() == expected_job_status(
            "archive", SciCatClient.STATUSMESSAGE.IN_PROGRESS
        )
        # v4 only
        # assert m.jobs_matcher.request_history[0].json() == expected_job_status(
        #     "archive", SciCatClient.JOBSTATUSCODE.IN_PROGRESS
        # )

        assert m.datasets_matcher.request_history[0].json() == expected_archival_dataset_lifecycle(
            SciCatClient.ARCHIVESTATUSMESSAGE.STARTED
        )

        # v4 only
        # assert m.jobs_matcher.request_history[1].json() == expected_job_status(
        #     "archive", SciCatClient.JOBSTATUSCODE.FINISHED_UNSUCCESSFULLY
        # )

        assert m.jobs_matcher.request_history[1].json() == expected_job_status(
            "archive", SciCatClient.STATUSMESSAGE.FINISHED_UNSUCCESSFULLY
        )

        assert m.datasets_matcher.request_history[1].json() == expected_archival_dataset_lifecycle(
            SciCatClient.ARCHIVESTATUSMESSAGE.MISSING_FILES
        )

        mock_cleanup_s3_retrieval.assert_not_called()
        mock_cleanup_s3_landingzone.assert_not_called()
        mock_cleanup_s3_staging.assert_called_once_with(expected_s3_client, dataset_id)
        mock_cleanup_scratch.assert_called_once_with(dataset_id)


@pytest.mark.parametrize(
    "job_id,dataset_id",
    [
        (uuid4(), "somePrefix/456"),
    ],
)
@patch("scicat.scicat_tasks.scicat_client", mock_scicat_client)
@patch("utils.datablocks.list_datablocks", mock_list)
@patch("utils.datablocks.download_objects_from_s3", mock_list)
@patch("utils.datablocks.create_tarfiles", mock_void_function)
@patch("utils.datablocks.create_datablock_entries", mock_create_datablock_entries)
@patch("utils.datablocks.upload_objects_to_s3", mock_void_function)
@patch("utils.datablocks.verify_objects", mock_empty_list)
@patch("utils.datablocks.archive_datablock", raise_system_error)
@patch("utils.datablocks.cleanup_scratch")
@patch("utils.datablocks.cleanup_s3_staging")
@patch("utils.datablocks.cleanup_s3_landingzone")
@patch("utils.datablocks.cleanup_s3_retrieval")
def test_archive_datablock_failure(
    mock_cleanup_s3_retrieval: MagicMock,
    mock_cleanup_s3_landingzone: MagicMock,
    mock_cleanup_s3_staging: MagicMock,
    mock_cleanup_scratch: MagicMock,
    job_id: UUID,
    dataset_id: str,
    mocked_s3,
):
    num_orig_datablocks = 10
    num_files_per_block = 10
    num_datablocks = 10

    num_expected_datablocks = num_orig_datablocks

    expected_s3_client = mock_s3client()
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
        with pytest.raises(Exception):
            archive_datasets_flow(job_id=job_id, dataset_ids=[dataset_id])

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 2
        assert m.datablocks_post_matcher.call_count == num_expected_datablocks
        assert all([d.call_count == 1 for d in m.datablocks_delete_matcher])

        assert m.jobs_matcher.request_history[0].json() == expected_job_status(
            "archive", SciCatClient.STATUSMESSAGE.IN_PROGRESS
        )

        assert m.datasets_matcher.request_history[0].json() == expected_archival_dataset_lifecycle(
            SciCatClient.ARCHIVESTATUSMESSAGE.STARTED
        )

        for i in range(num_expected_datablocks):
            assert m.datablocks_post_matcher.request_history[i].json() == expected_datablocks(dataset_id, i)

        assert m.jobs_matcher.request_history[1].json() == expected_job_status(
            "archive", SciCatClient.STATUSMESSAGE.FINISHED_UNSUCCESSFULLY
        )
        assert m.datasets_matcher.request_history[1].json() == expected_archival_dataset_lifecycle(
            SciCatClient.ARCHIVESTATUSMESSAGE.SCHEDULE_ARCHIVE_JOB_FAILED
        )

        # 6: cleanup
        mock_cleanup_s3_retrieval.assert_not_called()
        mock_cleanup_s3_landingzone.assert_not_called()
        mock_cleanup_s3_staging.assert_called_once_with(expected_s3_client, dataset_id)
        mock_cleanup_scratch.assert_called_once_with(dataset_id)
