from moto import mock_aws
import pytest
import os
from pathlib import Path


@pytest.fixture(scope="function")
def aws_and_s3_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"
    os.environ["MINIO_REGION"] = "eu-west-1"
    os.environ["MINIO_ENDPOINT"] = "endpoint:9000"


@pytest.fixture(scope="function")
def mocked_s3(aws_and_s3_credentials):
    """
    Mock all AWS interactions
    Requires you to create your own boto3 clients
    """
    with mock_aws():
        yield


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
