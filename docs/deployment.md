# Deployment

![arch](deployment.drawio)



## Service Deployment

The services on the virtual machine can be deployed using a single docker-compose file:

```bash
docker compose --env-file .env --env-file .development.env up -d
```

There are configuration parameters for all the services for production and develoment:

### Production

```bash
{!../.env!}
```

### Development

For development, it is useful to override some configuration:

```bash
{!../.development.env!}
```

> Note: The `lts-mock-volume` is a local volume here and not the LTS share.


## Prefect Deployment

Prefect is set up in a slightly non-standard way (with respect to their described use cases). There are two workers deployed (archival/retrieval) that mount the hosts Docker socket in order
to create containers at runtime in which the flows run. The flows are baked into the containers and the code is not pulled from any repository (Prefect would allow to, for example, store the code in an S3 bucket). The ETHZ LTS volume is mounted in a Docker volume such that the runtime containers can mount those during startup.


![prefect](prefect.drawio)

| Name              | Technology                                                                                                               | Description | Endpoint                                |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------ | ----------- | --------------------------------------- |
| Prefect Server    | Workflow orchestration <https://www.prefect.io>                                                                          |             | <http://localhost/prefect-ui/dashboard> |
| Postgres Database | Database for Prefect                                                                                                     |             | n/a                                     |
| Prefect Worker    | <https://docs.prefect.io/3.0/deploy/infrastructure-concepts/workers>                                                     |             | n/a                                     |
| Runtime Container | [prefect-runtime.Dockerfile](https://github.com/SwissOpenEM/ScopeMArchiver/blob/main/backend/prefect-runtime.Dockerfile) |             | n/a                                     |

### Prefect Server

In order to run Prefect server, variables, secrets and concurrency limits need to be configured.
#### Configuration
All of the configuration can be done by running

  ```bash
    docker compose --env-file .env --env-file .development.env run --rm prefect-config
  ```

with the appropriate PREFECT_API_URL set.

##### Variables

Variables are used at runtime and are fetched from the server by the flow. External endpoints and other parameters of the flow belong here:

```toml
{!../backend/prefect-vars.toml!}
```

##### Concurrrency Limits

There are certain sections of the code (tasks) that can only run in a limited manner concurrently (i.e. writing to the LTS), see <https://docs.prefect.io/3.0/develop/task-run-limits#limit-concurrent-task-runs-with-tags>.

```toml
{!../backend/concurrency-limits.toml!}
```

##### Internal Secrets

Internal secrets can be created at deployment time.

```bash
# Postgres
echo "postgres_user" > .secrets/postgresuser.txt
openssl rand -base64 12 > .secrets/postgrespass.txt # creates random string
```

##### External Secrets

The Minio deployment might already provide its own secrets and can be added manually in the UI too.

```bash
# Minio
echo "minioadminuser" > .secrets/miniouser.txt
openssl rand -base64 12 > .secrets/miniopass.txt # creates random string

// TODO: Needed ?
# Github
echo "<github_user>" > .secrets/githubuser.txt
echo "<github_access_token>" > .secrets/githubpass.txt
```

| Name                       | Description                                        |
| -------------------------- | -------------------------------------------------- |
| github-openem-username     | Username for Github container registry             |
| github-openem-access-token | Personal access token to Github container registry |

### Prefect Worker

Workers can only be deployed on a machine that has access to

- the Prefect server (no authentication implemented in Prefect for on-premise deployement currently)
- the S3 storage
- the ETHZ LTS share (ip whitelisting within ETHZ network)

They can be started by the following command:

```bash
docker compose --env-file .env --env-file .development.env up -d prefect-archival-worker
docker compose --env-file .env --env-file .development.env up -d prefect-retrieval-worker
```

> Note: due to a bug in Prefect the workers concurrency limit needs to be set manually in the UI.

### Flows

The [flows](../backend/archiver/flows/__init__.py) can be deployed using a container:

```bash
docker compose --env-file .env --env-file .development.env run --rm prefect-flows-deployment
```

This deploys the flows as defined in the [prefect.yaml](https://github.com/SwissOpenEM/ScopeMArchiver/backend/prefect.yaml) and requires the secrets set up in the previous step.
