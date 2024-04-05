import pytest


@pytest.fixture(scope="function")
def celery_config():
    return {
        "broker_url": "filesystem://",
        "broker_transport_options": {
            'data_folder_in': './.data/broker/out',
            'data_folder_out': './.data/broker/out',
            'data_folder_processed': './.data/broker/processed'
        },
        "result_backend": "rpc://"
    }
