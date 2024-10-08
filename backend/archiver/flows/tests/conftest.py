import pytest
import os
from pathlib import Path


@pytest.fixture(autouse=True)
def config_fixture():

    envs = {
        'LTS_FREE_SPACE_PERCENTAGE': ".01",
        'SCICAT_API_PREFIX': "/",
        'LTS_STORAGE_ROOT': "/tmp/LTS",
        'ARCHIVER_SCRATCH_FOLDER': "/tmp/data/scratch",
        'ARCHIVER_LTS_FILE_TIMEOUT_S': "30"
    }

    Path("/tmp/LTS").mkdir(exist_ok=True)
    Path("/tmp/data/scratch").mkdir(exist_ok=True, parents=True)

    for k, v in envs.items():
        os.environ[k] = v

    yield

    for k, v in envs.items():
        os.environ.pop(k)
