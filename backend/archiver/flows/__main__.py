from prefect import serve

from .archive_datasets_flow import archive_datasets_flow
from .retrieve_datasets_flow import retrieve_datasets_flow
from .mock_flows import create_test_dataset_flow
from prefect.deployments.runner import DeploymentImage
from prefect import flow, task, State, Task, Flow
from prefect.runner.storage import GitRepository


if __name__ == "__main__":

    # serves flows locally for development
    archiving_deploy = archive_datasets_flow.to_deployment(name="DEV_datasets_archival")
    retrieval_delpoy = retrieve_datasets_flow.to_deployment(name="DEV_datasets_retrieval")
    create_test_dataset = create_test_dataset_flow.to_deployment(name="DEV_dataset_creation")
    serve(archiving_deploy, retrieval_delpoy, create_test_dataset)
