from typing import List, Dict, Any

from pydantic import SecretStr
from archiver.utils.model import DataFile, OrigDataBlock, DataBlock
from archiver.utils.model import Job, Dataset, DatasetLifecycle, JobResultObject, JobResultEntry
from archiver.scicat.scicat_interface import SciCatClient
from pathlib import Path

from archiver.utils.working_storage_interface import S3Storage


def mock_s3client() -> S3Storage:
    s3client = S3Storage(
        url="endpoint:9000",
        user="user",
        password=SecretStr("password"),
        region="eu-west-1"
    )
    return s3client


def create_orig_datablocks(num_blocks: int = 10, num_files_per_block: int = 10) -> List[OrigDataBlock]:
    size_per_file = 1024 * 1024 * 100
    blocks: List[OrigDataBlock] = []
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


def create_datablocks(num_blocks: int = 10, num_files_per_block: int = 10) -> List[DataBlock]:
    size_per_file = 1024 * 1024 * 100
    blocks: List[DataBlock] = []
    for k in range(num_blocks):
        b = DataBlock(
            id=f"Block_{k}",
            archiveId="path/to/block",
            size=size_per_file * num_files_per_block,
            dataFileList=[],
            version="1"
        )
        for i in range(num_files_per_block):
            d = DataFile(
                path=f"/some/path/file_{i}.png",
                size=size_per_file
            )
            b.dataFileList.append(d)
        blocks.append(b)
    return blocks


def expected_job_status(job_type: str, status: SciCatClient.JOBSTATUS) -> Dict[str, Any]:
    match status:
        case SciCatClient.JOBSTATUS.IN_PROGRESS:
            return Job(statusCode="1", statusMessage="inProgress").model_dump(exclude_none=True)
        case SciCatClient.JOBSTATUS.FINISHED_SUCCESSFULLY:
            return Job(statusCode="1", statusMessage="finishedSuccessful").model_dump(exclude_none=True)
        case SciCatClient.JOBSTATUS.FINISHED_UNSUCCESSFULLY:
            return Job(statusCode="1", statusMessage="finishedUnsuccessful").model_dump(exclude_none=True)
        case SciCatClient.JOBSTATUS.FINISHED_WITHDATASET_ERRORS:
            return Job(statusCode="1", statusMessage="finishedWithDatasetErrors").model_dump(exclude_none=True)


def expected_archival_dataset_lifecycle(
        status: SciCatClient.ARCHIVESTATUSMESSAGE, archivable: bool | None = None, retrievable: bool | None = None) -> Dict[
        str, Any]:
    return Dataset(datasetlifecycle=DatasetLifecycle(
        archiveStatusMessage=str(status),
        archivable=archivable,
        retrievable=retrievable
    )).model_dump(exclude_none=True)


def expected_retrieval_dataset_lifecycle(
        status: SciCatClient.RETRIEVESTATUSMESSAGE, archivable: bool | None = None, retrievable: bool | None = None) -> Dict[
        str, Any]:
    return Dataset(datasetlifecycle=DatasetLifecycle(
        archivable=archivable,
        retrievable=retrievable,
        retrieveStatusMessage=str(status),
    )).model_dump(exclude_none=True)


def expected_datablocks(dataset_id: str, idx: int):
    size_per_file = 1024 * 1024 * 100

    return DataBlock(
        id=f"Block_{idx}",
        archiveId=f"/path/to/archived/Block_{idx}.tar.gz",
        size=size_per_file * 10,
        packedSize=size_per_file * 10,
        version=str(1)
    ).model_dump(exclude_none=True)


def expected_jobresultsobject(dataset_id: str, datablocks: List[DataBlock]):
    results: List[JobResultEntry] = []
    for datablock in datablocks:
        results.append(JobResultEntry(
            datasetId=dataset_id,
            name=Path(datablock.archiveId).name,
            size=datablock.size,
            archiveId=datablock.archiveId,
            url=""
        ))

    return JobResultObject(result=results).model_dump(exclude_none=True)


def mock_create_datablocks(s3_client: S3Storage, dataset_id: str, origDataBlocks: List[OrigDataBlock]) -> List[DataBlock]:
    datablocks: List[DataBlock] = []
    for o in origDataBlocks:
        d = DataBlock(
            id=o.id,
            archiveId=f"/path/to/archived/{o.id}.tar.gz",
            size=o.size,
            packedSize=o.size,
            version=str(1),
        )
        datablocks.append(d)
    return datablocks
