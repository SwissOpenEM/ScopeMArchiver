from prefect import serve

from .archive_datasets_flow import archive_datasets_flow, move_datablock_to_lts_flow
from .retrieve_datasets_flow import retrieve_datasets_flow
from .mock_flows import create_test_dataset_flow, end_to_end_test_flow


if __name__ == "__main__":
    # serves flows locally for development
    archiving_deploy = archive_datasets_flow.to_deployment(name="DEV_datasets_archival")
    move_datablock_to_lts_flow_deploy = move_datablock_to_lts_flow.to_deployment(
        name="DEV_move_datablock_to_lts_flow"
    )
    retrieval_delpoy = retrieve_datasets_flow.to_deployment(name="DEV_datasets_retrieval")
    create_test_dataset = create_test_dataset_flow.to_deployment(name="DEV_dataset_creation")
    end_to_end_test = end_to_end_test_flow.to_deployment(name="DEV_end_to_end_test")
    serve(
        archiving_deploy,
        retrieval_delpoy,
        create_test_dataset,
        move_datablock_to_lts_flow_deploy,
    )
