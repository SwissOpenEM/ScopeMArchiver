from prefect import flow, Flow, State
from prefect.client.schemas import FlowRun
from typing import List
from prefect.deployments.deployments import run_deployment

from archiver.scicat.scicat_interface import SciCat
from archiver.utils.model import OrigDataBlock, Job
from archiver.scicat.scicat_tasks import update_scicat_dataset_lifecycle, update_scicat_job_status


def on_flow_failure(flow: Flow, flow_run: FlowRun, state: State):
    # report_error(job_id=flow_run.parameters['job_id'], dataset_id=flow_run.parameters['dataset_id'])
    pass


@flow(name="retrieve_datasetlist", on_failure=[on_flow_failure])
def retrieve_datasets_flow(dataset_id: int, job_id: int, orig_data_blocks: List[OrigDataBlock]):
    job_update = update_scicat_job_status.submit(job_id, SciCat.JOBSTATUS.IN_PROGRESS)
    dataset_update = update_scicat_dataset_lifecycle.submit(
        dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED)


def run_retrieval_deployment(job: Job):
    run_deployment(name="retrieval/retrieve_datasetlist", timeout=0)
