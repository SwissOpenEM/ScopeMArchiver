# ScopeMArchiver

A ingester and archiver service that allows uploading data and registering it with [SciCat](https://scicatproject.github.io).

## Archiver

[Prefect.io](prefect.io) is used to orchestrate the asynchronous jobs (flows) to archive and retrieve datasets. The detail sequence of steps can be found [here](./docs/flows.md)

## Deployment

Using docker compose allows starting up all services:

```bash
docker compose --env-file .production.env up -d
```

## Github pages

Detailed documentation can be  found in the [GitHub Pages](https://swissopenem.github.io/ScopeMArchiver/)