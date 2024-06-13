from pathlib import Path
from prefect.runtime import flow_run, task_run
from archiver.config.variables import Variables


def generate_task_run_name_job_id():
    task_name = task_run.task_name

    parameters = task_run.parameters
    job_id = parameters["job_id"]

    return f"{task_name}-{job_id}"


def generate_flow_run_name_job_id():
    flow_name = flow_run.get_flow_name()

    parameters = flow_run.get_parameters()
    job_id = parameters["job_id"]

    return f"{flow_name}-{job_id}"


def generate_flow_run_name_dataset_id():
    flow_name = flow_run.get_flow_name()

    parameters = flow_run.get_parameters()
    dataset_id = parameters["dataset_id"]

    return f"{flow_name}-{dataset_id}"


def generate_task_run_name_dataset_id():
    task_name = task_run.task_name

    parameters = task_run.parameters
    dataset_id = parameters["dataset_id"]

    return f"{task_name}-{dataset_id}"


class DatasetError(Exception):
    pass


class SystemError(Exception):
    pass


class StoragePaths:
    @staticmethod
    def scratch_folder(dataset_id: int) -> Path:
        return StoragePaths.scratch_root() / str(dataset_id)

    @staticmethod
    def scratch_root() -> Path:
        return Variables().ARCHIVER_SCRATCH_FOLDER / "archival"

    @staticmethod
    def relative_datablocks_folder(dataset_id: int) -> Path:
        return Path("openem-network") / "datasets" / str(dataset_id)

    @staticmethod
    def scratch_datablocks_folder(dataset_id: int) -> Path:
        return StoragePaths.scratch_root() / StoragePaths.relative_datablocks_folder(dataset_id)

    @staticmethod
    def lts_datablocks_folder(dataset_id: int) -> Path:
        return Variables().LTS_STORAGE_ROOT / StoragePaths.relative_datablocks_folder(dataset_id)
