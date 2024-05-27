from prefect import serve

from .archive_datasets_flow import archive_datasets_flow
from .retrieve_datasets_flow import retrieve_datasets_flow
from .mock_flows import create_test_dataset_flow


if __name__ == "__main__":

    archiving_deploy = archive_datasets_flow.to_deployment(name="archival")
    retrieval_delpoy = retrieve_datasets_flow.to_deployment(name="retrieval")
    create_test_dataset = create_test_dataset_flow.to_deployment(name="create_test_dataset")

    serve(archiving_deploy, retrieval_delpoy, create_test_dataset)
