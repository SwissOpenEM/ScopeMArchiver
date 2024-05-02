from prefect import flow

import archiver.datablocks as datablocks_operations


@flow(name="create_test_dataset", )
def create_test_dataset_flow(dataset_id: int):
    return datablocks_operations.create_dummy_dataset(dataset_id)
