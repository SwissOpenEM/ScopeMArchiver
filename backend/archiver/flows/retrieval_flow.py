from prefect import flow, task, State, Task, Flow
from prefect.client.schemas import TaskRun, FlowRun
from functools import partial
import os
from typing import List

from ..scicat_interface import SciCat
from ..model import OrigDataBlock, DataBlock
from .. import datablocks as datablocks_operations

from ..scicat_tasks import update_scicat_dataset_lifecycle, update_scicat_job_status, register_datablocks, report_error
from ..scicat_interface import SciCat


def on_flow_failure(flow: Flow, flow_run: FlowRun, state: State):
    pass
    # report_error(job_id=flow_run.parameters['job_id'], dataset_id=flow_run.parameters['dataset_id'])


@flow(name="retrieval_flow", on_failure=[on_flow_failure])
def retrieval_flow(dataset_id: int, job_id: int, orig_data_blocks: List[OrigDataBlock]):
    job_update = update_scicat_job_status.submit(job_id, SciCat.JOBSTATUS.IN_PROGRESS)
    dataset_update = update_scicat_dataset_lifecycle.submit(
        dataset_id, SciCat.ARCHIVESTATUSMESSAGE.STARTED)


async def create_retrieval_flow(dataset_id: int, job_id: int, orig_data_blocks: List[OrigDataBlock]):
    from prefect.deployments import run_deployment
    res = await run_deployment(name="archiving_flow/archiving_flow", timeout=0)
    return res
