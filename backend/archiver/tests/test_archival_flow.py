
from unittest.mock import patch, MagicMock
from typing import List, Dict, Any
import pytest
from prefect.testing.utilities import prefect_test_harness

from archiver.flows.archiving_flow import archiving_flow
from archiver.scicat_interface import SciCat
from archiver.tests.scicat_unittest_mock import ScicatMock
from archiver.model import Job, OrigDataBlock, Dataset, DatasetLifecycle, DataBlock


def expected_job_status(job_id: int, job_type: str, status: SciCat.JOBSTATUS) -> Dict[str, Any]:
    match status:
        case SciCat.JOBSTATUS.IN_PROGRESS:
            return Job(id=str(job_id), type=job_type, jobStatusMessage="inProgress").model_dump(exclude_none=True)
        case SciCat.JOBSTATUS.FINISHED_SUCCESSFULLY:
            return Job(id=str(job_id), type=job_type, jobStatusMessage="finishedSuccessful").model_dump(exclude_none=True)
        case SciCat.JOBSTATUS.FINISHED_UNSUCCESSFULLY:
            return Job(id=str(job_id), type=job_type, jobStatusMessage="finishedUnsuccessful").model_dump(exclude_none=True)
        case SciCat.JOBSTATUS.FINISHED_WITHDATASET_ERRORS:
            return Job(id=str(job_id), type=job_type, jobStatusMessage="finishedWithDatasetErrors").model_dump(exclude_none=True)


def expected_dataset_lifecycle(
        datasets_id: int, status: SciCat.ARCHIVESTATUSMESSAGE, archivable: bool | None = None, retrievable: bool | None = None) -> Dict[
        str, Any]:
    return Dataset(datasetlifecycle=DatasetLifecycle(
        archiveStatusMessage=str(status),
        archivable=archivable,
        retrievable=retrievable
    )).model_dump(exclude_none=True)


def expected_datablocks(dataset_id: int, idx: int):
    size_per_file = 1024 * 1024 * 100

    return DataBlock(
        id=f"Block_{idx}",
        archiveId=f"/path/to/archived/Block_{idx}.tar.gz",
        size=size_per_file * 10,
        packedSize=size_per_file * 10,
        version=str(1),
        ownerGroup="me"
    ).model_dump(exclude_none=True)


def mock_create_datablocks(dataset_id: int, origDataBlocks: List[OrigDataBlock]) -> List[DataBlock]:
    datablocks: List[DataBlock] = []
    for o in origDataBlocks:
        d = DataBlock(
            id=o.id,
            archiveId=f"/path/to/archived/{o.id}.tar.gz",
            size=o.size,
            packedSize=o.size,
            version=str(1),
            ownerGroup="me"
        )
        datablocks.append(d)
    return datablocks


def raise_exception_task(*args, **kwargs):
    raise Exception("Mock Exception")


def mock_void_function(*args, **kwargs):
    pass


@ pytest.mark.parametrize("job_id,dataset_id", [
    (123, 456),
])
@ patch("archiver.scicat_tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
@ patch("archiver.datablocks.create_datablocks", mock_create_datablocks)
@ patch("archiver.datablocks.move_data_to_LTS", mock_void_function)
@ patch("archiver.datablocks.validate_data_in_LTS", mock_void_function)
@ patch("archiver.datablocks.cleanup_scratch", mock_void_function)
@ patch("archiver.datablocks.cleanup_staging", mock_void_function)
def test_scicat_api_archiving(job_id: int, dataset_id: int):

    num_orig_datablocks = 10
    num_files_per_block = 10
    num_expected_datablocks = num_orig_datablocks

    with ScicatMock(job_id=job_id, dataset_id=dataset_id, num_blocks=num_orig_datablocks, num_files_per_block=num_files_per_block) as m, prefect_test_harness():
        archiving_flow(job_id=job_id, dataset_id=dataset_id)

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 2
        assert m.datablocks_matcher.call_count == num_expected_datablocks

        # 3: Update job status
        assert m.jobs_matcher.request_history[0].json() == expected_job_status(
            job_id, "archive", SciCat.JOBSTATUS.IN_PROGRESS)

        # 4: Update dataset lifecycle
        assert m.datasets_matcher.request_history[0].json() == expected_dataset_lifecycle(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED)

        # 5: Create datablocks: mocked

        # 11: Register Datablocks
        for i in range(num_expected_datablocks):
            assert m.datablocks_matcher.request_history[i].json(
            ) == expected_datablocks(dataset_id, i)

            # 12: Move datablocks: mocked

            # 15: Validate datablocks: mocked

            # 18: Update dataset lifecycle
            assert m.datasets_matcher.request_history[1].json() == expected_dataset_lifecycle(
                dataset_id, SciCat.ARCHIVESTATUSMESSAGE.DATASETONARCHIVEDISK, retrievable=True)

            # 19: Update job status
            assert m.jobs_matcher.request_history[1].json() == expected_job_status(
                job_id, "archive", SciCat.JOBSTATUS.FINISHED_SUCCESSFULLY)


@ pytest.mark.parametrize("job_id,dataset_id", [
    (123, 456),
])
@ patch("archiver.scicat_tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
@ patch("archiver.datablocks.create_datablocks", raise_exception_task)
@ patch("archiver.datablocks.cleanup_scratch")
@ patch("archiver.datablocks.cleanup_staging")
def test_move_to_staging_failure(mock_cleanup_staging: MagicMock, mock_cleanup_scratch: MagicMock, job_id: int, dataset_id: int):

    num_orig_datablocks = 10
    num_files_per_block = 10

    # datablocks created but not moved to staging, therefore none reported
    num_expected_datablocks = 0

    with ScicatMock(job_id=job_id, dataset_id=dataset_id, num_blocks=num_orig_datablocks, num_files_per_block=num_files_per_block)as m, prefect_test_harness():
        with pytest.raises(Exception):
            archiving_flow(job_id=job_id, dataset_id=dataset_id)

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 2
        assert m.datablocks_matcher.call_count == num_expected_datablocks

        # 3: Update job status
        assert m.jobs_matcher.request_history[0].json() == expected_job_status(
            job_id, "archive", SciCat.JOBSTATUS.IN_PROGRESS)

        # 4: Update dataset lifecycle
        assert m.datasets_matcher.request_history[0].json() == expected_dataset_lifecycle(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED)

        # 5: Report Error
        assert m.jobs_matcher.request_history[1].json() == expected_job_status(
            job_id, "archive", SciCat.JOBSTATUS.FINISHED_UNSUCCESSFULLY)

        assert m.datasets_matcher.request_history[1].json() == expected_dataset_lifecycle(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.SCHEDULE_ARCHIVE_JOB_FAILED)

        mock_cleanup_staging.assert_called_once_with(dataset_id)
        mock_cleanup_scratch.assert_called_once_with(dataset_id, "archival")


@ pytest.mark.parametrize("job_id,dataset_id", [
    (123, 456),
])
@ patch("archiver.scicat_tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
@ patch("archiver.datablocks.create_datablocks", mock_create_datablocks)
@ patch("archiver.datablocks.move_data_to_LTS", raise_exception_task)
@ patch("archiver.datablocks.cleanup_lts_folder")
def test_move_to_LTS_failure(mock_cleanup_lts_folder: MagicMock, job_id: int, dataset_id: int):

    num_orig_datablocks = 10
    num_files_per_block = 10

    num_expected_datablocks = num_orig_datablocks

    with ScicatMock(job_id=job_id, dataset_id=dataset_id, num_blocks=num_orig_datablocks, num_files_per_block=num_files_per_block) as m, prefect_test_harness():
        with pytest.raises(Exception):
            archiving_flow(job_id=job_id, dataset_id=dataset_id)

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 2
        assert m.datablocks_matcher.call_count == num_expected_datablocks

        # 3: Update job status
        assert m.jobs_matcher.request_history[0].json() == expected_job_status(
            job_id, "archive", SciCat.JOBSTATUS.IN_PROGRESS)

        # 4: Update dataset lifecycle
        assert m.datasets_matcher.request_history[0].json() == expected_dataset_lifecycle(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED)

        # 11: Register Datablocks
        for i in range(num_expected_datablocks):
            assert m.datablocks_matcher.request_history[i].json(
            ) == expected_datablocks(dataset_id, i)

        # 5: Report Error
        assert m.jobs_matcher.request_history[1].json() == expected_job_status(
            job_id, "archive", SciCat.JOBSTATUS.FINISHED_UNSUCCESSFULLY)

        assert m.datasets_matcher.request_history[1].json() == expected_dataset_lifecycle(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.SCHEDULE_ARCHIVE_JOB_FAILED)

        # 6: cleanup LTS
        mock_cleanup_lts_folder.assert_called_once_with(dataset_id)


@ pytest.mark.parametrize("job_id,dataset_id", [
    (123, 456),
])
@ patch("archiver.scicat_tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
@ patch("archiver.datablocks.create_datablocks", mock_create_datablocks)
@ patch("archiver.datablocks.move_data_to_LTS", mock_void_function)
@ patch("archiver.datablocks.validate_data_in_LTS", raise_exception_task)
@ patch("archiver.datablocks.cleanup_lts_folder")
def test_LTS_validation_failure(mock_cleanup_lts_folder: MagicMock, job_id: int, dataset_id: int):

    num_orig_datablocks = 10
    num_files_per_block = 10

    num_expected_datablocks = num_orig_datablocks

    with ScicatMock(job_id=job_id, dataset_id=dataset_id, num_blocks=num_orig_datablocks, num_files_per_block=num_files_per_block) as m, prefect_test_harness():
        with pytest.raises(Exception):
            archiving_flow(job_id=job_id, dataset_id=dataset_id)

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 2
        assert m.datablocks_matcher.call_count == num_expected_datablocks

        # 3: Update job status
        assert m.jobs_matcher.request_history[0].json() == expected_job_status(
            job_id, "archive", SciCat.JOBSTATUS.IN_PROGRESS)

        # 4: Update dataset lifecycle
        assert m.datasets_matcher.request_history[0].json() == expected_dataset_lifecycle(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED)

        # 11: Register Datablocks
        for i in range(num_expected_datablocks):
            assert m.datablocks_matcher.request_history[i].json(
            ) == expected_datablocks(dataset_id, i)

        # TODO: check for different message, specific to validation
        # 5: Report Error
        assert m.jobs_matcher.request_history[1].json() == expected_job_status(
            job_id, "archive", SciCat.JOBSTATUS.FINISHED_UNSUCCESSFULLY)

        assert m.datasets_matcher.request_history[1].json() == expected_dataset_lifecycle(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.SCHEDULE_ARCHIVE_JOB_FAILED)

        # 6: cleanup LTS
        mock_cleanup_lts_folder.assert_called_once_with(dataset_id)
