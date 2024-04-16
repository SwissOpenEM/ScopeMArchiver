from prefect import serve

from .archiving_flow import archiving_flow
from .retrieval_flow import retrieval_flow

if __name__ == "__main__":
    archiving_deploy = archiving_flow.to_deployment(name="archival")
    retrieval_delpoy = retrieval_flow.to_deployment(name="retrieval")

    serve(archiving_deploy, retrieval_delpoy)
