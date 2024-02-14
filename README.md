# ScopeMArchiver

A archiving servce that allows uploading data and registering it with [SciCat](https://scicatproject.github.io).

## Mockarchiver

Python based service that mocks behavior of the LTS at ETH.
See its [Readme](./mockarchiver/README.me) for details.

## Deployment

All the services can be deployed using docker compose:

```bash
docker compose up -d
```

> Note: Individual image tags need to be passed as env variables
