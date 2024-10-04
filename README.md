# ScopeMArchiver

An archiver service that allows uploading dataset and registering it with [SciCat](https://scicatproject.github.io).

## Archiver

[Prefect.io](prefect.io) is used to orchestrate the asynchronous jobs (flows) to archive and retrieve datasets. The detail sequence of steps can be found [here](./docs/flows.md)

## Quick start

Starting up all services for development:

```bash
docker compose --profile full --env-file .production.env --env-file .development.env up -d
```

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
docker run --rm -it -v ~/.ssh:/root/.ssh -v ${PWD}:/docs squidfunk/mkdocs-material gh-deploy 
```


Architecture
  High Level Blocks
  - Ingestor App/Service + frontend
  - Storage
  - Scicat
  - Backend
  - Prefect
  Prefect:
  - Server, Worker, Runtime Containers

Deployment 
  - Readme: build, mkdocs, 



