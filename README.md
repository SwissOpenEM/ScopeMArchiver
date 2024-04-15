# OpenEM Service

A ingester and archiver service that allows uploading data and registering it with [SciCat](https://scicatproject.github.io).

## Development

```bash
docker compose --env-file .production.env --env-file .development.env up -d
```

> **Note:** .env files are picked up by VSCode and variables defined there are added to the shell that is used. This can lead to confusion as the files is not reloaded after changing values and the values in the session of the shell take precedence.

## Archiver

The archiver functionality can be enabled by setting the following env variable:

```bash
ARCHIVER_ENABLED=True
```

### Mockarchiver

Python based service that mocks behavior of the LTS at ETH.
See its [Readme](./mockarchiver/README.me) for details.

## Ingester

The ingester functionality can be enabled by setting the following env variable:

```bash
INGESTER_ENABLED=True
```

## Deployment

Production:

```bash
docker compose --env_file .production.env up -d
```

Development:

```bash
docker compose --env-file .production.env --env-file .development.env --profile archiver up -d
```

## Endpoints

Deploying it locally for development provide the following endpoints

| Service           | Endpoint                              |
| ----------------- | ------------------------------------- |
| Archiver Frontend | <http://localhost>                    |
| Traefik           | <http://traefik.localhost/dashboard/> |
| Jobs API          | <http://localhost/api/v1/docs>        |

## Elastic Search

```bash
sudo sysctl -w vm.max_map_count=262144
```
