import os
import boto3
from pathlib import Path
from moto import mock_aws
from pydantic import SecretStr
import pytest
from archiver.utils.s3_storage_interface import S3Storage, Bucket


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"


@pytest.fixture(scope="function")
def s3(aws_credentials):
    """
    Return a mocked S3 client
    """
    with mock_aws():
        user = "user"
        password = "pass"
        region = "eu-west-1"
        client = boto3.client(
            's3',
        )

        location = {'LocationConstraint': region}
        client.create_bucket(Bucket="landingzone",
                                    CreateBucketConfiguration=location)
        client.put_object(Bucket="landingzone", Key="test-file", Body="asdf")

        yield S3Storage(url=None, user=user, password=SecretStr(password), region=region)  # type: ignore


@mock_aws
def test_s3_interface(s3):

    bucket = Bucket("landingzone")
    filename = "test-file"

    presigned_url = s3.get_presigned_url(
        bucket=bucket,
        filename=filename
    )
    assert filename in presigned_url

    listed_objects = s3.list_objects(
        bucket=bucket,
        folder=""
    )

    assert len(listed_objects) == 1
    assert listed_objects[0].Name == filename

    stat_object = s3.stat_object(
        bucket=bucket,
        filename=filename
    )
    assert stat_object.Size == 4

    import tempfile
    with tempfile.NamedTemporaryFile() as tmp_file:
        tmp_file.close()
        s3.fget_object(
            bucket=bucket,
            folder="",
            object_name=filename,
            target_path=Path(tmp_file.name)
        )

        assert os.path.exists(tmp_file.name)
        assert os.stat(tmp_file.name).st_size == 4

    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_file.write(b'test-string')
        tmp_file.close()

        s3.fput_object(
            bucket=bucket,
            source_file=Path(tmp_file.name),
            destination_file=Path(tmp_file.name)
        )

        stat_object = s3.stat_object(
            bucket=bucket,
            filename=tmp_file.name
        )
        assert stat_object.Size == os.stat(tmp_file.name).st_size

    listed_objects = s3.list_objects(
        bucket=bucket,
        folder="/tmp"
    )

    assert len(listed_objects) == 1

    s3.delete_object(
        bucket=bucket,
        minio_prefix="/tmp")

    listed_objects = s3.list_objects(
        bucket=bucket,
        folder="/tmp"
    )

    assert len(listed_objects) == 0
