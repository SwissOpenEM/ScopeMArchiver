from prefect import serve

from .archiving_flow import archiving_flow
from .retrieval_flow import retrieval_flow
from .mock_flows import create_test_dataset_flow

from archiver.config import register_variables_from_config


if __name__ == "__main__":

    register_variables_from_config()

    archiving_deploy = archiving_flow.to_deployment(name="archival")
    retrieval_delpoy = retrieval_flow.to_deployment(name="retrieval")
    create_test_dataset = create_test_dataset_flow.to_deployment(name="create_test_dataset")

    serve(archiving_deploy, retrieval_delpoy, create_test_dataset)
