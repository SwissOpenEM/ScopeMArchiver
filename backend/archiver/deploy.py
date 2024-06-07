import logging
from prefect import flow, Flow
from prefect.runner.storage import GitRepository

if __name__ == "__main__":

    branch = "main"
    image = f"ghcr.io/swissopenem/scopemarchiver-openem-runtime:{branch}"
    flows = [
        ("dataset_creation", "backend/archiver/flows/mock_flows.py:create_test_dataset_flow", "archival-docker-workpool"),
        ("datasets_archival", "backend/archiver/flows/archive_datasets_flow.py:archive_datasets_flow", "archival-docker-workpool"),
    ]

    for name, entrypoint, pool in flows:

        r = flow.from_source(
            source=GitRepository(
                url="https://github.com/SwissOpenEM/ScopeMArchiver.git",
                branch=branch
            ),
            entrypoint=entrypoint
        ).deploy(
            name=name,
            image=image,
            work_pool_name=pool,
            build=False
        )
