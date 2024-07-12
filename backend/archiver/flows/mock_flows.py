import random
from prefect import flow, task
from prefect.deployments.deployments import run_deployment
import os
import asyncio
import shutil
import requests
from pathlib import Path
from archiver.config.variables import Variables
from archiver.utils.datablocks import upload_objects_to_s3, create_tarballs
from archiver.utils.working_storage_interface import S3Storage
from archiver.utils.model import OrigDataBlock, DataFile
from archiver.flows.utils import StoragePaths
from .task_utils import generate_task_name_dataset
from archiver.flows.utils import StoragePaths


@task(task_run_name=generate_task_name_dataset)
def create_dummy_dataset(dataset_id: int, file_size_MB: int, num_files: int, datablock_size_MB: int):
    dataset_root = Variables().ARCHIVER_SCRATCH_FOLDER / str(dataset_id)

    raw_files_folder = dataset_root / "raw_files"
    if not raw_files_folder.exists():
        raw_files_folder.mkdir(parents=True)

    datablocks_folder = dataset_root / "datablocks"
    if not datablocks_folder.exists():
        datablocks_folder.mkdir(parents=True)

    for i in range(num_files):
        os.system(f"dd if=/dev/urandom of={raw_files_folder}/file_{i}.bin bs={file_size_MB}M count=1 iflag=fullblock")

    create_tarballs(dataset_id=dataset_id, src_folder=raw_files_folder,
                    dst_folder=datablocks_folder, target_size=datablock_size_MB * (1024**2))

    files = upload_objects_to_s3(prefix=Path(StoragePaths.relative_origdatablocks_folder(dataset_id)),
                                 bucket=S3Storage().LANDINGZONE_BUCKET, source_folder=datablocks_folder, ext=".gz")

    shutil.rmtree(dataset_root)
    checksums = []

    # dataset = Dataset(
    #     datasetlifecycle="",
    #     updatedAt="",
    # )
    # {
    #     "ownerGroup": "ingestor",
    #     "accessGroups": [
    #         "ingestor"
    #     ],
    #     "instrumentGroup": "string",
    #     "owner": "ingestor",
    #     "ownerEmail": "scicatingestor@your.site",
    #     "orcidOfOwner": "ingestor",
    #     "contactEmail": "name@mail.com",
    #     "sourceFolder": "./",
    #     "sourceFolderHost": "test.com",
    #     "size": 0,
    #     "packedSize": 0,
    #     "numberOfFiles": 0,
    #     "numberOfFilesArchived": 0,
    #     "creationTime": "2024-07-02T12:11:56.234Z",
    #     "validationStatus": "string",
    #     "keywords": [
    #         "string"
    #     ],
    #     "description": "string",
    #     "datasetName": "string",
    #     "classification": "string",
    #     "license": "string",
    #     "isPublished": false,
    #     "techniques": [],
    #     "sharedWith": [],
    #     "relationships": [],
    #     "datasetlifecycle": {},
    #     "scientificMetadata": {},
    #     "comment": "string",
    #     "dataQualityMetrics": 0,
    #     "principalInvestigator": "string",
    #     "endTime": "2024-07-02T12:11:56.234Z",
    #     "creationLocation": "string",
    #     "dataFormat": "string",
    #     "proposalId": "string",
    #     "sampleId": "string",
    #     "instrumentId": "string",
    #     "pid": "1122",
    #     "version": "string",
    #     "type": "raw",
    #     "investigator": "string",
    #     "inputDatasets": [
    #         "string"
    #     ],
    #     "usedSoftware": [
    #         "string"
    #     ],
    #     "jobParameters": {},
    #     "jobLogData": "string",
    #     "attachments": [
    #         {
    #             "createdBy": "string",
    #             "updatedBy": "string",
    #             "createdAt": "2024-07-02T12:11:56.234Z",
    #             "updatedAt": "2024-07-02T12:11:56.234Z",
    #             "ownerGroup": "string",
    #             "accessGroups": [
    #                 "string"
    #             ],
    #             "instrumentGroup": "string",
    #             "isPublished": false,
    #             "id": "string",
    #             "thumbnail": "string",
    #             "caption": "string",
    #             "datasetId": "string",
    #             "proposalId": "string",
    #             "sampleId": "string"
    #         }
    #     ],
    #     "origdatablocks": [
    #         {
    #             "createdBy": "ingestor",
    #             "updatedBy": "ingestor",
    #             "createdAt": "2024-07-02T12:11:56.234Z",
    #             "updatedAt": "2024-07-02T12:11:56.234Z",
    #             "ownerGroup": "ingestor",
    #             "accessGroups": [
    #                 "ingestor"
    #             ],
    #             "instrumentGroup": "string",
    #             "isPublished": false,
    #             "_id": "1122",
    #             "datasetId": "1122",
    #             "size": 0,
    #             "chkAlg": "string",
    #             "dataFileList": [
    #                 {
    #                     "path": "string",
    #                     "size": 0,
    #                     "time": "2024-07-02T12:11:56.234Z",
    #                     "chk": "string",
    #                     "uid": "string",
    #                     "gid": "string",
    #                     "perm": "string"
    #                 }
    #             ]
    #         }
    #     ],
    #     "datablocks": [
    #         {
    #             "createdBy": "string",
    #             "updatedBy": "string",
    #             "createdAt": "2024-07-02T12:11:56.234Z",
    #             "updatedAt": "2024-07-02T12:11:56.234Z",
    #             "ownerGroup": "string",
    #             "accessGroups": [
    #                 "string"
    #             ],
    #             "instrumentGroup": "string",
    #             "isPublished": false,
    #             "_id": "string",
    #             "datasetId": "string",
    #             "archiveId": "string",
    #             "size": 0,
    #             "packedSize": 0,
    #             "chkAlg": "string",
    #             "version": "string",
    #             "dataFileList": [
    #                 {
    #                     "path": "string",
    #                     "size": 0,
    #                     "time": "2024-07-02T12:11:56.234Z",
    #                     "chk": "string",
    #                     "uid": "string",
    #                     "gid": "string",
    #                     "perm": "string"
    #                 }
    #             ]
    #         }
    #     ]
    # }

    # create orig datablocks
    origdatablock = OrigDataBlock(id=str(dataset_id),
                                  datasetId=str(dataset_id),
                                  size=2 * file_size_MB,
                                  ownerGroup="0",
                                  dataFileList=[DataFile(path=str(p), chk=c) for p, c in zip(files, checksums)]
                                  )
    j = origdatablock.model_dump_json()

    # register orig datablocks
    requests.post(f"{Variables().SCICAT_ENDPOINT}{Variables().SCICAT_API_PREFIX}OrigDatablocks/",
                  data=j)


@flow(name="create_test_dataset")
def create_test_dataset_flow(file_size_MB: int = 10, num_files: int = 10, datablock_size_MB: int = 20):
    dataset_id = random.randint(0, 10000)
    create_dummy_dataset(dataset_id, file_size_MB, num_files, datablock_size_MB)
