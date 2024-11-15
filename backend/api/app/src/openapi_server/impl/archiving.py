from typing import List
from uuid import UUID
from prefect.deployments import run_deployment


async def run_create_dataset_deployment(
        file_size_MB: int = 10, num_files: int = 10, datablock_size_MB: int = 20, dataset_id: str | None = None):
    deploy = await run_deployment("create_test_dataset/dataset_creation", parameters={
        "num_files": num_files,
        "file_size_MB": file_size_MB,
        "datablock_size_MB": datablock_size_MB,
        "dataset_id": dataset_id
    }, timeout=0)  # type: ignore
    return deploy


async def run_archiving_deployment(job_id: UUID, dataset_list: List[str]):

    a = await run_deployment("archive_datasetlist/datasets_archival",
                             parameters={
                                 "dataset_ids": dataset_list,
                                 "job_id": job_id
                             },
                             timeout=0)  # type: ignore
    return a


async def run_retrieval_deployment(job_id: UUID, dataset_list: List[str]):
    a = await run_deployment("retrieve_datasetlist/datasets_retrieval",
                             parameters={
                                 "dataset_ids": dataset_list,
                                 "job_id": job_id
                             },
                             timeout=0)  # type: ignore
    return a
