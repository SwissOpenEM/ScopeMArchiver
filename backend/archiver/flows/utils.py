from pathlib import Path
from prefect.runtime import flow_run, task_run
from archiver.config.variables import Variables


def generate_task_name_dataset():
    task_name = task_run.task_name
    parameters = task_run.get_parameters()
    dataset_id = parameters["dataset_id"]

    return f"{task_name}-dataset_id-{dataset_id}"


def generate_task_name_job():
    task_name = task_run.task_name
    parameters = task_run.get_parameters()
    job_id = parameters["job_id"]

    return f"{task_name}-job_id-{job_id}"


def generate_flow_name_dataset():
    flow_name = flow_run.task_name
    parameters = flow_run.get_parameters()
    dataset_id = parameters["dataset_id"]

    return f"{flow_name}-dataset_id-{dataset_id}"


def generate_flow_name_job_id():
    flow_name = flow_run.get_flow_name()
    parameters = flow_run.get_parameters()
    job_id = parameters["job_id"]

    return f"{flow_name}-job_id-{job_id}"


def generate_subflow_run_name_job_id_dataset_id():
    flow_name = flow_run.get_flow_name()
    parameters = flow_run.get_parameters()
    dataset_id = parameters["dataset_id"]

    return f"{flow_name}-dataset_id-{dataset_id}"


class DatasetError(Exception):
    """Custom exception to report different error types to Scicat
    """
    pass


class SystemError(Exception):
    """Custom exception to report different error types to Scicat
    """
    pass


class StoragePaths:
    """Helper class to create paths in scratch and LTS folder
    """

    @staticmethod
    def scratch_folder(dataset_id: int) -> Path:
        return StoragePaths.scratch_archival_root() / StoragePaths._relative_dataset_folder(dataset_id)

    @staticmethod
    def scratch_archival_root() -> Path:
        return Variables().ARCHIVER_SCRATCH_FOLDER / "archival"

    @staticmethod
    def _relative_dataset_folder(dataset_id):
        return Path("openem-network") / "datasets" / str(dataset_id)

    _relative_datablocks_folder: Path = Path("datablocks")
    _relative_origdatablocks_folder: Path = Path("origdatablocks")
    _relative_files_folder: Path = Path("raw_files")

    @staticmethod
    def relative_datablocks_folder(dataset_id: int):
        return StoragePaths._relative_dataset_folder(dataset_id) / StoragePaths._relative_datablocks_folder

    @staticmethod
    def relative_origdatablocks_folder(dataset_id: int):
        return StoragePaths._relative_dataset_folder(dataset_id) / StoragePaths._relative_origdatablocks_folder

    @staticmethod
    def relative_files_folder(dataset_id: int):
        return StoragePaths._relative_dataset_folder(dataset_id) / StoragePaths._relative_files_folder

    @staticmethod
    def scratch_archival_datablocks_folder(dataset_id: int) -> Path:
        return StoragePaths.scratch_archival_root() / StoragePaths.relative_datablocks_folder(dataset_id)

    @staticmethod
    def scratch_archival_origdatablocks_folder(dataset_id: int) -> Path:
        return StoragePaths.scratch_archival_root() / StoragePaths.relative_origdatablocks_folder(dataset_id)

    @staticmethod
    def scratch_archival_files_folder(dataset_id: int) -> Path:
        return StoragePaths.scratch_archival_root() / StoragePaths.relative_files_folder(dataset_id)

    @staticmethod
    def lts_datablocks_folder(dataset_id: int) -> Path:
        return Variables().LTS_STORAGE_ROOT / StoragePaths.relative_datablocks_folder(dataset_id)
