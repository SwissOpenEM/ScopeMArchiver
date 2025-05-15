from uuid import UUID
from prefect.client.schemas.objects import FlowRun  # noqa: F401
from prefect import flow  # noqa: F401 # required do to https://github.com/PrefectHQ/prefect/issues/16105
from prefect.deployments import run_deployment


async def run_archiving_deployment(job_id: UUID) -> FlowRun:
    a = await run_deployment(
        "archive_datasetlist/datasets_archival",
        parameters={"job_id": job_id},
        timeout=0,
    )  # type: ignore
    return a


async def run_retrieval_deployment(job_id: UUID) -> FlowRun:
    a = await run_deployment(
        "retrieve_datasetlist/datasets_retrieval",
        parameters={"job_id": job_id},
        timeout=0,
    )  # type: ignore
    return a
