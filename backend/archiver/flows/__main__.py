from prefect import serve

from .archiving_flow import archiving_flow, create_test_dataset_flow
from .retrieval_flow import retrieval_flow
from archiver.config import parse_settings

if __name__ == "__main__":
    parse_settings()
    archiving_deploy = archiving_flow.to_deployment(name="archival")
    retrieval_delpoy = retrieval_flow.to_deployment(name="retrieval")
    create_test_dataset = create_test_dataset_flow.to_deployment(name="create_test_dataset")

    serve(archiving_deploy, retrieval_delpoy, create_test_dataset)
