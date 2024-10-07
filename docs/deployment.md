# Deployment

![arch](deployment.drawio)




## Service Deployment Configuration

### Production

```bash
{!../.production.env!}
```

### Development

For development, it is useful to override some configuration:

```bash
{!../.development.env!}
```

> Note: The `lts-mock-volume` is a local volume here and not the LTS share.

## Prefect Deployment

- non standard setup
- docker worker as described
- create runtime container on host through docker sockets
- mount lts as network share through docker volume
- flow states stored?
- flow result not stored?

<!-- ```yaml
{!../backend/prefect.yaml!}
``` -->

![prefect](prefect.drawio)

| Name              | Technology                                      | Description                             | Endpoint |
| ----------------- | ----------------------------------------------- | --------------------------------------- | -------- |
| Prefect Server    | Workflow orchestration <https://www.prefect.io> | <http://localhost/prefect-ui/dashboard> |          |
| Database          | Database for Prefect                            |                                         |          |
| Prefect Worker    | Worker that spawns new flows                    |                                         |          |
| Runtime Container |                                                 |                                         |          |

### Prefect Server

#### Configuration

  ```bash
    docker compose --env-file .production.env --env-file .development.env run --rm prefect-config
  ```

##### Variables

> TODO: add description 

```toml
{!../backend/prefect-vars.toml!}
```

##### Concurrrency Limits

```toml
{!../backend/concurrency-limits.toml!}
```

##### Internal Secrets

```bash
# Postgres
echo "postgres_user" > .secrets/postgresuser.txt
openssl rand -base64 12 > .secrets/postgrespass.txt # creates random string
```

##### External Secrets

```bash
# Minio
echo "minioadminuser" > .secrets/miniouser.txt
openssl rand -base64 12 > .secrets/miniopass.txt # creates random string

# Github
echo "<github_user>" > .secrets/githubuser.txt
echo "<github_access_token>" > .secrets/githubpass.txt
```

| Name                       | Description                                        |
| -------------------------- | -------------------------------------------------- |
| github-openem-username     | Username for Github container registry             |
| github-openem-access-token | Personal access token to Github container registry |

### Prefect Worker

```bash
docker compose --env-file .production.env --env-file .development.env up -d prefect-archival-worker
docker compose --env-file .production.env --env-file .development.env up -d prefect-retrieval-worker
```

### Flows

The [flows](../backend/archiver/flows/__init__.py) can be deployed using a container:

```bash
docker compose --env-file .production.env --env-file .development.env run --rm prefect-flows-deployment
```

This deploys the flows as defined in the [prefect.yaml](https://github.com/SwissOpenEM/ScopeMArchiver/backend/prefect.yaml) and requires the secrets set up in the previous step.
