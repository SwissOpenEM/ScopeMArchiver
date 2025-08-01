from pathlib import Path
from pydantic import SecretStr

from prefect import State
from prefect.client.schemas.objects import TaskRun

from config.variables import Variables
from scicat.scicat_tasks import (
    report_dataset_system_error,
    report_dataset_user_error,
    report_dataset_retrieval_error
)


class DatasetError(Exception):
    """Custom exception to report different error types to Scicat"""

    pass


class SystemError(Exception):
    """Custom exception to report different error types to Scicat"""

    pass


def report_archival_error(dataset_id: str, state: State, task_run: TaskRun, token: SecretStr):
    """Report an error of an archival job of a dataset. Differntiates betwen "DatasetError" (User error, e.g. missing files)
    and SystemError (transient error).

    Args:
        dataset_id (str): dataset id
        state (State): task run state
        task_run (TaskRun): task run
    """
    try:
        state.result()
    except DatasetError:
        report_dataset_user_error(dataset_id=dataset_id, token=token)
    except SystemError:
        report_dataset_system_error(dataset_id=dataset_id, token=token)
    except Exception:
        # TODO: add some info about unknown errors
        report_dataset_system_error(dataset_id=dataset_id, token=token)


def report_retrieval_error(dataset_id: str, state: State, task_run: TaskRun, token: SecretStr):
    """Report a retrieval error of a job of a dataset. Differentiates between "DatasetError" (User error, e.g. missing files)
    and SystemError (transient error).

    Args:
        dataset_id (str): dataset id
        state (State): task run state
        task_run (TaskRun): task run
    """

    report_dataset_retrieval_error(dataset_id=dataset_id, token=token)


class StoragePaths:
    """Helper class to create paths in scratch and LTS folder"""

    @staticmethod
    def scratch_folder(dataset_id: str) -> Path:
        return StoragePaths.scratch_archival_root() / StoragePaths._relative_dataset_folder(dataset_id)

    @staticmethod
    def scratch_archival_root() -> Path:
        return Variables().ARCHIVER_SCRATCH_FOLDER / "archival"

    @staticmethod
    def _relative_dataset_folder(dataset_id: str) -> Path:
        return Path("openem-network") / "datasets" / dataset_id

    _relative_datablocks_folder: Path = Path("datablocks")
    _relative_raw_files_folder: Path = Path("raw_files")

    @staticmethod
    def relative_datablocks_folder(dataset_id: str):
        return StoragePaths._relative_dataset_folder(dataset_id) / StoragePaths._relative_datablocks_folder

    @staticmethod
    def relative_raw_files_folder(dataset_id: str):
        return StoragePaths._relative_dataset_folder(dataset_id) / StoragePaths._relative_raw_files_folder

    @staticmethod
    def scratch_archival_datablocks_folder(dataset_id: str) -> Path:
        return StoragePaths.scratch_archival_root() / StoragePaths.relative_datablocks_folder(dataset_id)

    @staticmethod
    def scratch_archival_raw_files_folder(dataset_id: str) -> Path:
        return StoragePaths.scratch_archival_root() / StoragePaths.relative_raw_files_folder(dataset_id)

    @staticmethod
    def lts_datablocks_folder(dataset_id: str) -> Path:
        return Variables().LTS_STORAGE_ROOT / StoragePaths.relative_datablocks_folder(dataset_id)
