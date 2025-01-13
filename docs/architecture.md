# Architecture

## Component Diagram

![Compnents](components.drawio)

### Components

#### Archiver Service

| Name                    | Technology                             | Description                                                      | Endpoint                                |
| ----------------------- | -------------------------------------- | ---------------------------------------------------------------- | --------------------------------------- |
| Reverse Proxy           | Traefik <https://traefik.io/traefik/>  | Routes traffic to endpoints                                      | <https://${HOST}/dashboard/> |
| Backend Api        | FastAPI <https://fastapi.tiangolo.com> | Endpoint for Scicat backend, requests flow scheduling by Prefect | <https://${HOST}/archiver/api/v1/docs>          |
| Workflow Orchestraction | Prefect <https://www.prefect.io>       | Orchestrates workflows for archival and retrieval operations     | <https://${HOST}/archiver/prefect/ui/dashboard> |

#### Workflow Orchestration

| Name           | Technology                                                            | Description | Endpoint                                              |
| -------------- | --------------------------------------------------------------------- | ----------- | ----------------------------------------------------- |
| Prefect Server | <https://docs.prefect.io/3.0/manage/self-host>                        |             | <https://${HOST}/archiver/prefect/ui/dashboard> |
| Prefect Worker | <https://docs.prefect.io/3.0/deploy/infrastructure-concepts/workers>  |             | n/a                                                   |
| Prefect Flow   | <https://docs.prefect.io/3.0/develop/write-flows#write-and-run-flows> |             | n/a                                                   |

#### Storage Components

| Name           | Technology             | Description                                                            | Endpoint                  |
| -------------- | ---------------------- | ---------------------------------------------------------------------- | ------------------------- |
| Storage Server | Minio <https://min.io> | Storage for datasets that are to be archived or are retrievable        | <http://localhost/minio/> |
| LTS Share      | NFS Network share      | ETHZ Long term storage where datasets are stored on and retrieved from | n/a                       |

#### External Components

| Name     | Technology                                       | Description                                                                            | Endpoint                    |
| -------- | ------------------------------------------------ | -------------------------------------------------------------------------------------- | --------------------------- |
| Ingestor | Golang <https://github.com/SwissOpenEM/Ingestor> | Client application to select, ingest, and upload datasets                              | n/a                         |
| SciCat Frontend  | Node.js <https://scicatproject.github.io>        | Data catalog frontend where datasets are registered and archival/retrieval is triggered | <https://discovery.psi.ch/>, <https://${HOST}/>  |
| SciCat Backend | Node.js <https://scicatproject.github.io>        | Data catalog backend where datasets are registered and archival/retrieval is triggered | <https://dacat.psi.ch/explorer/>, <https://${HOST}/scicat/backend/explorer>  |