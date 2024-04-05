
from unittest.mock import patch
from typing import List
import pytest
from celery import shared_task

from archiver.tasks import create_archiving_pipeline
from archiver.scicat_interface import SciCat
from archiver.tests.scicat_mock import ScicatMock
from archiver.model import Job, OrigDataBlock, Dataset, DatasetLifecycle, DataFile, DataBlock


def create_orig_datablocks(num_blocks: int = 10, num_files_per_block: int = 10) -> List[OrigDataBlock]:
    size_per_file = 1024 * 1024 * 100
    blocks = []
    for k in range(num_blocks):
        b = OrigDataBlock(
            id=f"Block_{k}",
            size=size_per_file * num_files_per_block,
            ownerGroup="me",
            dataFileList=[]
        )
        for i in range(num_files_per_block):
            d = DataFile(
                path=f"/some/path/file_{i}.png",
                size=size_per_file
            )
            b.dataFileList.append(d)
        blocks.append(b)
    return blocks


def job_status_json(job_id: int, job_type: str, status: SciCat.JOBSTATUS) -> str:
    match status:
        case SciCat.JOBSTATUS.IN_PROGRESS:
            return Job(id=str(job_id), type=job_type, jobStatusMessage="inProgress").model_dump_json()
        case SciCat.JOBSTATUS.FINISHED_SUCCESSFULLY:
            return Job(id=str(job_id), type=job_type, jobStatusMessage="finishedSuccessful").model_dump_json()
        case SciCat.JOBSTATUS.FINISHED_UNSUCCESSFULLY:
            return Job(id=str(job_id), type=job_type, jobStatusMessage="finishedUnsuccessful").model_dump_json()
        case SciCat.JOBSTATUS.FINISHED_WITHDATASET_ERRORS:
            return Job(id=str(job_id), type=job_type, jobStatusMessage="finishedWithDatasetErrors").model_dump_json()


def dataset_lifecycle_json(datasets_id: int, status: SciCat.ARCHIVESTATUSMESSAGE, archivable=None, retrievable=None) -> str:
    return Dataset(datasetlifecycle=DatasetLifecycle(
        archiveStatusMessage=str(status),
        archivable=archivable,
        retrievable=retrievable
    )).model_dump_json()


def datablocks_json(dataset_id: int, idx: int):
    size_per_file = 1024 * 1024 * 100

    return DataBlock(
        id=f"Block_{idx}",
        archiveId=f"/path/to/archived/Block_{idx}.tar.gz",
        size=size_per_file * 10,
        packedSize=size_per_file * 10 / 2,
        version=str(1),
        ownerGroup="me"
    ).model_dump_json()


def dataset_datablocks() -> str:
    pass


@shared_task
def mock_create_datablocks(result, dataset_id: int, orig_data_blocks: List[OrigDataBlock]) -> List[DataBlock]:
    datablocks = []
    for o in orig_data_blocks:
        d = DataBlock(
            id=o.id,
            archiveId=f"/path/to/archived/{o.id}.tar.gz",
            size=o.size,
            packedSize=o.size / 2,
            version=str(1),
            ownerGroup="me"
        )
        datablocks.append(d)
    return datablocks


@shared_task
def mock_move_data_to_staging(datablocks: List[DataBlock]) -> List[DataBlock]:
    return datablocks


@shared_task
def mock_move_data_to_LTS(result: List[DataBlock]) -> None:
    pass


@shared_task
def mock_validate_data_in_LTS(result: List[DataBlock]) -> None:
    pass


@pytest.mark.parametrize("job_id,dataset_id", [
    (123, 456),
])
@patch("archiver.tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
@patch("archiver.tasks.create_datablocks", mock_create_datablocks)
@patch("archiver.tasks.move_data_to_staging", mock_move_data_to_staging)
@patch("archiver.tasks.move_data_to_LTS", mock_move_data_to_LTS)
@patch("archiver.tasks.validate_data_in_LTS", mock_validate_data_in_LTS)
def test_scicat_api_archiving(celery_app, celery_worker, job_id, dataset_id):

    num_orig_datablocks = 10
    num_files_per_block = 10
    num_expected_datablocks = num_orig_datablocks

    orig_data_blocks = create_orig_datablocks(num_orig_datablocks, num_files_per_block)

    with ScicatMock(job_id=job_id, dataset_id=dataset_id) as m:
        res = create_archiving_pipeline(job_id=job_id, dataset_id=dataset_id, orig_data_blocks=orig_data_blocks)()
        res.get()

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 2
        assert m.datablocks_matcher.call_count == num_expected_datablocks

        # 3: Update job status
        assert m.jobs_matcher.request_history[0].json() == job_status_json(
            job_id, "archive", SciCat.JOBSTATUS.IN_PROGRESS)

        # 4: Update dataset lifecycle
        assert m.datasets_matcher.request_history[0].json() == dataset_lifecycle_json(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED)

        # 5: Create datablocks: mocked

        # 11: Register Datablocks
        for i in range(num_expected_datablocks):
            assert m.datablocks_matcher.request_history[i].json() == datablocks_json(dataset_id, i)

        # 12: Move datablocks: mocked

        # 15: Validate datablocks: mocked

        # 18: Update dataset lifecycle
        assert m.datasets_matcher.request_history[1].json() == dataset_lifecycle_json(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.DATASETONARCHIVEDISK, retrievable=True)

        # 19: Update job status
        assert m.jobs_matcher.request_history[1].json() == job_status_json(
            job_id, "archive", SciCat.JOBSTATUS.FINISHED_SUCCESSFULLY)


@shared_task
def raise_expection_task(dataset_id: int, **kwargs) -> List[DataBlock]:
    raise Exception("Mock Exception")


@shared_task
def on_error(request, exc, traceback):
    pass


@pytest.mark.parametrize("job_id,dataset_id", [
    (123, 456),
])
@patch("archiver.tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
@patch("archiver.datablocks.create_datablocks", raise_expection_task)
def test_datablock_failure(celery_app, celery_worker, job_id, dataset_id):

    num_orig_datablocks = 10
    num_files_per_block = 10

    # no datablocks created
    num_expected_datablocks = 0

    orig_data_blocks = create_orig_datablocks(num_orig_datablocks, num_files_per_block)

    with ScicatMock(job_id, dataset_id) as m:
        res = create_archiving_pipeline(job_id=job_id, dataset_id=dataset_id, orig_data_blocks=orig_data_blocks)()

        # res.get() will reraise the exception!
        with pytest.raises(Exception):
            res.get()

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 2
        assert m.datablocks_matcher.call_count == num_expected_datablocks

        # 3: Update job status
        assert m.jobs_matcher.request_history[0].json() == job_status_json(
            job_id, "archive", SciCat.JOBSTATUS.IN_PROGRESS)

        # 4: Update dataset lifecycle
        assert m.datasets_matcher.request_history[0].json() == dataset_lifecycle_json(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED)

        # 5: Report Error
        assert m.jobs_matcher.request_history[1].json() == job_status_json(
            job_id, "archive", SciCat.JOBSTATUS.FINISHED_UNSUCCESSFULLY)

        assert m.datasets_matcher.request_history[1].json() == dataset_lifecycle_json(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.SCHEDULE_ARCHIVE_JOB_FAILED)


@pytest.mark.parametrize("job_id,dataset_id", [
    (123, 456),
])
@patch("archiver.tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
@patch("archiver.tasks.create_datablocks", mock_create_datablocks)
@patch("archiver.tasks.move_data_to_staging", raise_expection_task)
def test_move_to_staging_failure(celery_app, celery_worker, job_id, dataset_id):

    num_orig_datablocks = 10
    num_files_per_block = 10

    # datablocks created but not moved to staging, therefore none reported
    num_expected_datablocks = 0

    orig_data_blocks = create_orig_datablocks(num_orig_datablocks, num_files_per_block)

    with ScicatMock(job_id=job_id, dataset_id=dataset_id) as m:
        res = create_archiving_pipeline(job_id=job_id, dataset_id=dataset_id, orig_data_blocks=orig_data_blocks)()

        with pytest.raises(Exception):
            res.get()

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 2
        assert m.datablocks_matcher.call_count == num_expected_datablocks

        # 3: Update job status
        assert m.jobs_matcher.request_history[0].json() == job_status_json(
            job_id, "archive", SciCat.JOBSTATUS.IN_PROGRESS)

        # 4: Update dataset lifecycle
        assert m.datasets_matcher.request_history[0].json() == dataset_lifecycle_json(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED)

        # 5: Report Error
        assert m.jobs_matcher.request_history[1].json() == job_status_json(
            job_id, "archive", SciCat.JOBSTATUS.FINISHED_UNSUCCESSFULLY)

        assert m.datasets_matcher.request_history[1].json() == dataset_lifecycle_json(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.SCHEDULE_ARCHIVE_JOB_FAILED)


@pytest.mark.parametrize("job_id,dataset_id", [
    (123, 456),
])
@patch("archiver.tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
@patch("archiver.tasks.create_datablocks", mock_create_datablocks)
@patch("archiver.tasks.move_data_to_staging", mock_move_data_to_staging)
@patch("archiver.tasks.move_data_to_LTS", raise_expection_task)
def test_move_to_LTS_failure(celery_app, celery_worker, job_id, dataset_id):

    num_orig_datablocks = 10
    num_files_per_block = 10

    num_expected_datablocks = num_orig_datablocks

    orig_data_blocks = create_orig_datablocks(num_orig_datablocks, num_files_per_block)

    with ScicatMock(job_id=job_id, dataset_id=dataset_id) as m:
        res = create_archiving_pipeline(job_id=job_id, dataset_id=dataset_id, orig_data_blocks=orig_data_blocks)()

        with pytest.raises(Exception):
            res.get()

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 2
        assert m.datablocks_matcher.call_count == num_expected_datablocks

        # 3: Update job status
        assert m.jobs_matcher.request_history[0].json() == job_status_json(
            job_id, "archive", SciCat.JOBSTATUS.IN_PROGRESS)

        # 4: Update dataset lifecycle
        assert m.datasets_matcher.request_history[0].json() == dataset_lifecycle_json(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED)

        # 11: Register Datablocks
        for i in range(num_expected_datablocks):
            assert m.datablocks_matcher.request_history[i].json() == datablocks_json(dataset_id, i)

        # 5: Report Error
        assert m.jobs_matcher.request_history[1].json() == job_status_json(
            job_id, "archive", SciCat.JOBSTATUS.FINISHED_UNSUCCESSFULLY)

        assert m.datasets_matcher.request_history[1].json() == dataset_lifecycle_json(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.SCHEDULE_ARCHIVE_JOB_FAILED)


@pytest.mark.parametrize("job_id,dataset_id", [
    (123, 456),
])
@patch("archiver.tasks.scicat._ENDPOINT", ScicatMock.ENDPOINT)
@patch("archiver.tasks.create_datablocks", mock_create_datablocks)
@patch("archiver.tasks.move_data_to_staging", mock_move_data_to_staging)
@patch("archiver.tasks.move_data_to_LTS", mock_move_data_to_LTS)
@patch("archiver.tasks.validate_data_in_LTS", raise_expection_task)
def test_LTS_validation_failure(celery_app, celery_worker, job_id, dataset_id):

    num_orig_datablocks = 10
    num_files_per_block = 10

    num_expected_datablocks = num_orig_datablocks

    orig_data_blocks = create_orig_datablocks(num_orig_datablocks, num_files_per_block)

    with ScicatMock(job_id=job_id, dataset_id=dataset_id) as m:
        res = create_archiving_pipeline(job_id=job_id, dataset_id=dataset_id, orig_data_blocks=orig_data_blocks)()

        with pytest.raises(Exception):
            res.get()

        assert m.jobs_matcher.call_count == 2
        assert m.datasets_matcher.call_count == 2
        assert m.datablocks_matcher.call_count == num_expected_datablocks

        # 3: Update job status
        assert m.jobs_matcher.request_history[0].json() == job_status_json(
            job_id, "archive", SciCat.JOBSTATUS.IN_PROGRESS)

        # 4: Update dataset lifecycle
        assert m.datasets_matcher.request_history[0].json() == dataset_lifecycle_json(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED)

        # 11: Register Datablocks
        for i in range(num_expected_datablocks):
            assert m.datablocks_matcher.request_history[i].json() == datablocks_json(dataset_id, i)

        # TODO: check for different message, specific to validation
        # 5: Report Error
        assert m.jobs_matcher.request_history[1].json() == job_status_json(
            job_id, "archive", SciCat.JOBSTATUS.FINISHED_UNSUCCESSFULLY)

        assert m.datasets_matcher.request_history[1].json() == dataset_lifecycle_json(
            dataset_id, SciCat.ARCHIVESTATUSMESSAGE.SCHEDULE_ARCHIVE_JOB_FAILED)
