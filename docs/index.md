# ScopeMArchiver

A ingester and archiver service that allows uploading data and registering it with [SciCat](https://scicatproject.github.io).

## Archiver

[Prefect.io](prefect.io) is used to orchestrate the asynchronous jobs (flows) to archive (and retrieve) datasets. The detail sequence of steps can be found [here](./backend/archiver/readMe.md)

## Services

There are services that are running and serving the archiver and other services that are just run to configure the archiver:

### Runtime Services

| Name           | Description                                   | Endpoint                              |
| -------------- | --------------------------------------------- | ------------------------------------- |
| traefik        | Reverse Proxy                                 | http://localhost/traefik/dashboard/#/ |
| backend        | Endpoint for client applications and Scicat   | http://localhost/api/v1/docs          |
| prefect-server | Workflow orchestration https://www.prefect.io | http://localhost/prefect-ui/dashboard |
| prefect-worker | Worker that spawns new flows                  |                                       |
| postgres       | Database for Prefect                          |                                       |
| minio          | S3 Storage                                    | http://localhost/minio/               |
| scicatmock     | Mock implementation of SciCat API             |                                       |

### Configuration Containers

In addition to the services, several docker containers are started that configure the Prefect server with workpools, variables and flows defined in the repository. The workpools use a docker executor, i.e. the prefect-workers start every flow in its own container.

| Name                     | Description | Input                                 |
| ------------------------ | ----------- | ------------------------------------- |
| prefect-config           |             | backend/config.toml                   |
| prefect-deploy           |             | backend/prefect.yaml                  |
| prefect-archival-worker  |             | backend/prefect-jobtemplate-prod.json |
| prefect-retrieval-worker |             | backend/prefect-jobtemplate-prod.json |

## Deployment

### Docker Compose Profiles

| Name     | Function                                                                         |
| -------- | -------------------------------------------------------------------------------- |
| services | deploys all the services without reconfigerung, relies on previous configuration |
| config   | configures prefect (variables, blocks, limits)                                   |
| flows    | deploys the prefect flows                                                        |
| full     | deploys all the above                                                            |

### Step by step

1. Startup services
    Using docker compose allows starting up all services.

    ```bash
    docker compose --profile services --env-file .production.env up -d
    ```
  
    This sets up all the necessary services, including the Prefect server instance.

    > Note:  The environment variable `HOST` in `.production.env` determines where the services are hosted and are accessible from

1. Configure Secrets
    1. Create secrets as local text file to be used during deployment in docker compose:

        ```bash
        # Minio
        echo "minioadminuser" > .secrets/miniouser.txt
        openssl rand -base64 12 > .secrets/miniopass.txt # creates random string
        # Postgres
        echo "postgres_user" > .secrets/postgresuser.txt
        openssl rand -base64 12 > .secrets/postgrespass.txt # creates random string
        # Github
        echo "<github_user>" > .secrets/githubuser.txt
        echo "<github_access_token>" > .secrets/githubpass.txt

        ```

    1. Deploy secrets as [Prefect Blocks](https://docs.prefect.io/latest/concepts/blocks/) automatically

        ```bash
        docker compose --profiles config --env-file .production.env run --rm
        ```

1. Add external secrets
    Before being able to deploy flows secrets to the Github container registry need to be configured manually in [the Prefect UI](https://docs.prefect.io/latest/concepts/blocks/) as a `Secret`.

    | Name                       | Description                                        |
    | -------------------------- | -------------------------------------------------- |
    | github-openem-username     | Username for Github container registry             |
    | github-openem-access-token | Personal access token to Github container registry |

1. Deploy Flows

    The [flows](../backend/archiver/flows/__init__.py) can be deployed using a container:

    ```bash
    docker compose --profile flows --env-file .prodduction.env run --rm
    ```

    This deploys the flows as defined in the [prefect.yaml](https://github.com/SwissOpenEM/ScopeMArchiver/backend/prefect.yaml) and requires the secrets set up in the previous step.


## Development

### Setup Development Services

1. Start up all the services

    ```bash
    docker compose --profile services --env-file .production.env --env-file .development.env up -d
    ```

> **Note**: Secrets and flows don't need to be deployed as in the production deployment 

### Debugging Flows Locally

For development and debugging, a local process can serve flows, for example by running `python -m archiver.flows`. However, some more configuration is required to fully integration with the other services; therefore a VS Code launch command `Prefect Flows` can be used in [launch.json](./backend/.vscode/launch.json))

#### To a Remote Prefect Server

For deploying to a remote server, the following command can be used

```bash
cd backend
PREFECT_API_URL=http://<host>/api python deploy --all
```

It will tell Prefect to use the flows defined in the git repository and branch configured in [deploy.py](./backend/archiver/deploy.py)
