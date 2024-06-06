# ScopeMArchiver

A ingester and archiver service that allows uploading data and registering it with [SciCat](https://scicatproject.github.io).

## Archiver

[Prefect.io](prefect.io) is used to orchestrate the asynchronous jobs (flows) to archive (and retrieve) datasets. The detail sequence of steps can be found [here](./backend/archiver/readMe.md)

## Services

| Name           | Description                                   | Endpoint                              |
| -------------- | --------------------------------------------- | ------------------------------------- |
| traefik        | Reverse Proxy                                 | http://localhost/traefik/dashboard/#/ |
| backend        | Endpoint for client applications and Scicat   | http://localhost/api/v1/docs          |
| prefect        | Workflow orchestration https://www.prefect.io | http://localhost/prefect-ui/dashboard |
| prefect-worker | Agent/worker                                  |                                       |
| postgres       | Database for Prefect                          |                                       |
| minio          | S3 Storage                                    | http://localhost/minio/               |
| scicatmock     | Mock implementation of SciCat API             |                                       |

## Development

### Running all services locally

Using docker compose allows starting up all services locally on `localhost`

```bash
docker compose --profile production --env-file .production.env --env-file .development.env up -d
```

> **Note:** .env files are picked up by VSCode and variables defined there are added to the shell that is used. This can lead to confusion as the files is not reloaded after changing values and the values in the session of the shell take precedence.

The `production` profile starts up all services.

### Developing locally

Using the `development` profile

```bash
docker compose --profile development --env-file .production.env --env-file .development.env up -d
```

`prefect-worker` and `backend` are not started and a locally development instance can be used instead (see [vsconfig settings](./backend/.vscode/launch.json))

### Deploying Flows

#### To a Local Prefect Server 

For development and debugging, a local process can server flows, for example by running `python -m archiver.flows`. However, some more configuration is required to fully integration with the other services; therefore a VS Code launch command can be used in [launch.json](./backend/.vscode/launch.json))

#### To a Remote Prefect Server 

For deploying to a remote server, the following command can be used

```bash
PREFECT_API_URL=http://<host>/api python archiver/deploy.py
```

It will tell Prefect to use the flows defined in the git repository and branch configured in [deploy.py](./backend/archiver/deploy.py)


## Mockarchiver

Python based service that mocks behavior of the LTS at ETH.
See its [Readme](./mockarchiver/README.me) for details.

