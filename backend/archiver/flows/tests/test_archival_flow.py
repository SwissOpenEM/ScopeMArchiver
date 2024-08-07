
from unittest.mock import patch, MagicMock

import pytest
from prefect.testing.utilities import prefect_test_harness

from archiver.flows.archive_datasets_flow import archive_datasets_flow
from archiver.scicat.scicat_interface import SciCat
from archiver.flows.tests.scicat_unittest_mock import ScicatMock
from archiver.flows.utils import DatasetError, SystemError
from archiver.flows.tests.helpers import create_datablocks, create_orig_datablocks, mock_create_datablocks, expected_datablocks, expected_archival_dataset_lifecycle, expected_job_status


def raise_user_error(*args, **kwargs):
    raise DatasetError("Mock Dataset Error")


def raise_system_error(*args, **kwargs):
    raise SystemError("Mock System Error")


def mock_void_function(*args, **kwargs):
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize("job_id,dataset_id", [
    (123, 456),
])
@patch("archiver.scicat.scicat_tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
@patch("archiver.utils.datablocks.create_datablocks", mock_create_datablocks)
@patch("archiver.utils.datablocks.move_data_to_LTS", mock_void_function)
@patch("archiver.utils.datablocks.verify_data_in_LTS", mock_void_function)
@patch("archiver.utils.datablocks.cleanup_lts_folder")
@patch("archiver.utils.datablocks.cleanup_scratch")
@patch("archiver.utils.datablocks.cleanup_s3_staging")
@patch("archiver.utils.datablocks.cleanup_s3_landingzone")
@patch("archiver.utils.datablocks.cleanup_s3_retrieval")
async def test_scicat_api_archiving(
        mock_cleanup_s3_retrieval: MagicMock,
        mock_cleanup_s3_landingzone: MagicMock,
        mock_cleanup_s3_staging: MagicMock,
        mock_cleanup_scratch: MagicMock,
        mock_cleanup_lts: MagicMock,
        job_id: int, dataset_id: int):

    num_orig_datablocks = 10
    num_files_per_block = 10
    num_datablocks = 10
    num_expected_datablocks = num_orig_datablocks

    origDataBlocks = create_orig_datablocks(num_blocks=num_orig_datablocks, num_files_per_block=num_files_per_block)
    datablocks = create_datablocks(num_blocks=num_datablocks, num_files_per_block=num_files_per_block)

    with ScicatMock(job_id=job_id, dataset_id=dataset_id, origDataBlocks=origDataBlocks, datablocks=datablocks) as m, prefect_test_harness():
        try:
            await archive_datasets_flow(job_id=job_id, dataset_ids=[dataset_id])
        except Exception as e:
            pass

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 2
        assert m.datablocks_post_matcher.call_count == num_expected_datablocks

        # 3: Update job status
        assert m.jobs_matcher.request_history[0].json() == expected_job_status(
            job_id, "archive", SciCat.JOBSTATUS.IN_PROGRESS)

        # 4: Update dataset lifecycle
        assert m.datasets_matcher.request_history[0].json() == expected_archival_dataset_lifecycle(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED)

        # 5: Create datablocks: mocked

        # 11: Register Datablocks
        for i in range(num_expected_datablocks):
            assert m.datablocks_post_matcher.request_history[i].json(
            ) == expected_datablocks(dataset_id, i)

            # 12: Move datablocks: mocked

            # 15: Validate datablocks: mocked

        # 18: Update dataset lifecycle
        assert m.datasets_matcher.request_history[1].json() == expected_archival_dataset_lifecycle(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.DATASET_ON_ARCHIVEDISK, retrievable=True)

        # 19: Update job status
        assert m.jobs_matcher.request_history[1].json() == expected_job_status(
            job_id, "archive", SciCat.JOBSTATUS.FINISHED_SUCCESSFULLY)

        mock_cleanup_s3_retrieval.assert_not_called()
        mock_cleanup_s3_landingzone.assert_called_once_with(dataset_id)
        mock_cleanup_s3_staging.assert_called_once_with(dataset_id)
        mock_cleanup_scratch.assert_called_once_with(dataset_id)
        mock_cleanup_lts.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("job_id,dataset_id", [
    (123, 456),
])
@patch("archiver.scicat.scicat_tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
@patch("archiver.utils.datablocks.create_datablocks", raise_user_error)
@patch("archiver.utils.datablocks.cleanup_lts_folder")
@patch("archiver.utils.datablocks.cleanup_scratch")
@patch("archiver.utils.datablocks.cleanup_s3_staging")
@patch("archiver.utils.datablocks.cleanup_s3_landingzone")
@patch("archiver.utils.datablocks.cleanup_s3_retrieval")
async def test_create_datablocks_user_error(
        mock_cleanup_s3_retrieval: MagicMock,
        mock_cleanup_s3_landingzone: MagicMock,
        mock_cleanup_s3_staging: MagicMock,
        mock_cleanup_scratch: MagicMock,
        mock_cleanup_lts: MagicMock,
        job_id: int, dataset_id: int):

    num_orig_datablocks = 10
    num_files_per_block = 10
    num_datablocks = 10

    # datablocks created but not moved to staging, therefore none reported
    num_expected_datablocks = 0

    origDataBlocks = create_orig_datablocks(num_blocks=num_orig_datablocks, num_files_per_block=num_files_per_block)
    datablocks = create_datablocks(num_blocks=num_datablocks, num_files_per_block=num_files_per_block)
    with ScicatMock(job_id=job_id, dataset_id=dataset_id, origDataBlocks=origDataBlocks, datablocks=datablocks) as m, prefect_test_harness():
        with pytest.raises(Exception):
            await archive_datasets_flow(job_id=job_id, dataset_ids=[dataset_id])

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 2
        assert m.datablocks_post_matcher.call_count == num_expected_datablocks

        # 5: Update job status
        assert m.jobs_matcher.request_history[0].json() == expected_job_status(
            job_id, "archive", SciCat.JOBSTATUS.IN_PROGRESS)

        # 6: Update dataset lifecycle
        assert m.datasets_matcher.request_history[0].json() == expected_archival_dataset_lifecycle(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED)

        # 5: Report User Error
        assert m.jobs_matcher.request_history[1].json() == expected_job_status(
            job_id, "archive", SciCat.JOBSTATUS.FINISHED_UNSUCCESSFULLY)

        # 13: Missing files
        assert m.datasets_matcher.request_history[1].json() == expected_archival_dataset_lifecycle(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.MISSING_FILES)

        mock_cleanup_s3_retrieval.assert_not_called()
        mock_cleanup_s3_landingzone.assert_not_called()
        mock_cleanup_s3_staging.assert_called_once_with(dataset_id)
        mock_cleanup_scratch.assert_called_once_with(dataset_id)
        mock_cleanup_lts.assert_called_once_with(dataset_id)


@pytest.mark.asyncio
@ pytest.mark.parametrize("job_id,dataset_id", [
    (123, 456),
])
@patch("archiver.scicat.scicat_tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
@patch("archiver.utils.datablocks.create_datablocks", mock_create_datablocks)
@patch("archiver.utils.datablocks.move_data_to_LTS", raise_system_error)
@patch("archiver.utils.datablocks.cleanup_lts_folder")
@patch("archiver.utils.datablocks.cleanup_scratch")
@patch("archiver.utils.datablocks.cleanup_s3_staging")
@patch("archiver.utils.datablocks.cleanup_s3_landingzone")
@patch("archiver.utils.datablocks.cleanup_s3_retrieval")
async def test_move_to_LTS_failure(
        mock_cleanup_s3_retrieval: MagicMock,
        mock_cleanup_s3_landingzone: MagicMock,
        mock_cleanup_s3_staging: MagicMock,
        mock_cleanup_scratch: MagicMock,
        mock_cleanup_lts: MagicMock,
        job_id: int, dataset_id: int):

    num_orig_datablocks = 10
    num_files_per_block = 10
    num_datablocks = 10

    num_expected_datablocks = num_orig_datablocks

    origDataBlocks = create_orig_datablocks(num_blocks=num_orig_datablocks, num_files_per_block=num_files_per_block)
    datablocks = create_datablocks(num_blocks=num_datablocks, num_files_per_block=num_files_per_block)
    with ScicatMock(job_id=job_id, dataset_id=dataset_id, origDataBlocks=origDataBlocks, datablocks=datablocks) as m, prefect_test_harness():
        with pytest.raises(Exception):
            await archive_datasets_flow(job_id=job_id, dataset_ids=[dataset_id])

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 2
        assert m.datablocks_post_matcher.call_count == num_expected_datablocks

        # 3: Update job status
        assert m.jobs_matcher.request_history[0].json() == expected_job_status(
            job_id, "archive", SciCat.JOBSTATUS.IN_PROGRESS)

        # 4: Update dataset lifecycle
        assert m.datasets_matcher.request_history[0].json() == expected_archival_dataset_lifecycle(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED)

        # 11: Register Datablocks
        for i in range(num_expected_datablocks):
            assert m.datablocks_post_matcher.request_history[i].json(
            ) == expected_datablocks(dataset_id, i)

        # 5: Report Error
        assert m.jobs_matcher.request_history[1].json() == expected_job_status(
            job_id, "archive", SciCat.JOBSTATUS.FINISHED_UNSUCCESSFULLY)

        assert m.datasets_matcher.request_history[1].json() == expected_archival_dataset_lifecycle(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.SCHEDULE_ARCHIVE_JOB_FAILED)

        # 6: cleanup LTS
        mock_cleanup_s3_retrieval.assert_not_called()
        mock_cleanup_s3_landingzone.assert_not_called()
        mock_cleanup_s3_staging.assert_called_once_with(dataset_id)
        mock_cleanup_scratch.assert_called_once_with(dataset_id)
        mock_cleanup_lts.assert_called_once_with(dataset_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("job_id,dataset_id", [
    (123, 456),
])
@patch("archiver.scicat.scicat_tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
@patch("archiver.utils.datablocks.create_datablocks", mock_create_datablocks)
@patch("archiver.utils.datablocks.move_data_to_LTS", mock_void_function)
@patch("archiver.utils.datablocks.verify_data_in_LTS", raise_system_error)
@patch("archiver.utils.datablocks.cleanup_lts_folder")
@patch("archiver.utils.datablocks.cleanup_scratch")
@patch("archiver.utils.datablocks.cleanup_s3_staging")
@patch("archiver.utils.datablocks.cleanup_s3_landingzone")
@patch("archiver.utils.datablocks.cleanup_s3_retrieval")
async def test_LTS_validation_failure(
        mock_cleanup_s3_retrieval: MagicMock,
        mock_cleanup_s3_landingzone: MagicMock,
        mock_cleanup_s3_staging: MagicMock,
        mock_cleanup_scratch: MagicMock,
        mock_cleanup_lts: MagicMock,
        job_id: int, dataset_id: int):

    num_orig_datablocks = 10
    num_files_per_block = 10
    num_datablocks = 10

    origDataBlocks = create_orig_datablocks(num_blocks=num_orig_datablocks, num_files_per_block=num_files_per_block)
    datablocks = create_datablocks(num_blocks=num_datablocks, num_files_per_block=num_files_per_block)

    num_expected_datablocks = num_orig_datablocks

    with ScicatMock(job_id=job_id, dataset_id=dataset_id, origDataBlocks=origDataBlocks, datablocks=datablocks) as m, prefect_test_harness():
        with pytest.raises(Exception):
            await archive_datasets_flow(job_id=job_id, dataset_ids=[dataset_id])

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 2
        assert m.datablocks_post_matcher.call_count == num_expected_datablocks

        # 3: Update job status
        assert m.jobs_matcher.request_history[0].json() == expected_job_status(
            job_id, "archive", SciCat.JOBSTATUS.IN_PROGRESS)

        # 4: Update dataset lifecycle
        assert m.datasets_matcher.request_history[0].json() == expected_archival_dataset_lifecycle(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED)

        # 11: Register Datablocks
        for i in range(num_expected_datablocks):
            assert m.datablocks_post_matcher.request_history[i].json(
            ) == expected_datablocks(dataset_id, i)

        # TODO: check for different message, specific to validation
        # 5: Report Error
        assert m.jobs_matcher.request_history[1].json() == expected_job_status(
            job_id, "archive", SciCat.JOBSTATUS.FINISHED_UNSUCCESSFULLY)

        assert m.datasets_matcher.request_history[1].json() == expected_archival_dataset_lifecycle(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.SCHEDULE_ARCHIVE_JOB_FAILED)

        # 6: cleanup LTS
        mock_cleanup_s3_retrieval.assert_not_called()
        mock_cleanup_s3_landingzone.assert_not_called()
        mock_cleanup_s3_staging.assert_called_once_with(dataset_id)
        mock_cleanup_scratch.assert_called_once_with(dataset_id)
        mock_cleanup_lts.assert_called_once_with(dataset_id)


# Multiple flows
