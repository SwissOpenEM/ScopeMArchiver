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
    os.environ["MINIO_EXTERNAL_ENDPOINT"] = "endpoint:9000"


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
        "SCICAT_API_PREFIX": "/api/v1",
        "SCICAT_JOBS_API_PREFIX": "/api/v4",
        "ARCHIVER_SCRATCH_FOLDER": "/tmp/data/scratch",
    }

    Path("/tmp/data/scratch").mkdir(exist_ok=True, parents=True)

    for k, v in envs.items():
        os.environ[k] = v

    yield

    for k, v in envs.items():
        os.environ.pop(k)
