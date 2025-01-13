# ScopeMArchiver

An archiver service that allows uploading dataset and registering it with [SciCat](https://scicatproject.github.io). It is built on
[Prefect.io](prefect.io) to orchestrate the asynchronous jobs (called flows) to archive and retrieve datasets to/from the ETH LTS.

The full setup is containerized and requires a SciCat instance to run correctly.

Refer to the [Github pages](#github-pages) for more details.

## Quick start

Build all the services:

```bash
docker compose --env-file .prod.env --env-file .development.env build
```

Starting up all services for development:

```bash
docker compose --env-file .prod.env --env-file .development.env up -d
```

## Deploy Local Flows

For development and debugging, a local process can serve flows, for example by running `python -m archiver.flows`. However, some more configuration is required to fully integration with the other services; therefore a VS Code launch command `Prefect Flows` can be used in [launch.json](./backend/.vscode/launch.json)). This allows to debug flows locally and the registered flows have a prefix, `DEV_`.

## Github Pages

The latest documentation can be found in the [GitHub Pages](https://swissopenem.github.io/ScopeMArchiver/)

## Bulding Github Pages

Github pages are built on [mkdocs](https://hub.docker.com/r/squidfunk/mkdocs-material).

Build docker image first:

```bash
docker build . -f docs.Dockerfile -t ghcr.io/swissopenem/scopemarchiver-docs:latest
```

Start development server

```bash
docker run --rm -it -p 8000:8000 -v ${PWD}:/docs ghcr.io/swissopenem/scopemarchiver-docs:latest
```

Build documentation

```bash
docker run --rm -it -p 8000:8000 -v ${PWD}:/docs ghcr.io/swissopenem/scopemarchiver-docs:latest build
```

Deploy documentation to GitHub Pages

```bash
docker run --rm -it -v ~/.ssh:/root/.ssh -v ${PWD}:/docs ghcr.io/swissopenem/scopemarchiver-docs:latest gh-deploy 
```
