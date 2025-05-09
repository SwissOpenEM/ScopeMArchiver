from typing import List
from uuid import UUID
from prefect.client.schemas.objects import FlowRun  # noqa: F401
from prefect import flow  # noqa: F401 # required do to https://github.com/PrefectHQ/prefect/issues/16105
from prefect.deployments import run_deployment


async def run_archiving_deployment(job_id: UUID, dataset_list: List[str]):
    a = await run_deployment(
        "archive_datasetlist/datasets_archival",
        parameters={"dataset_ids": dataset_list, "job_id": job_id},
        timeout=0,
    )  # type: ignore
    return a


async def run_retrieval_deployment(job_id: UUID, dataset_list: List[str]):
    a = await run_deployment(
        "retrieve_datasetlist/datasets_retrieval",
        parameters={"dataset_ids": dataset_list, "job_id": job_id},
        timeout=0,
    )  # type: ignore
    return a
