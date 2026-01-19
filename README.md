# ScopeMArchiver

[![release](https://github.com/SwissOpenEM/ScopeMArchiver/actions/workflows/release.yml/badge.svg)](https://github.com/SwissOpenEM/ScopeMArchiver/actions/workflows/release.yml)

An archiver service that allows uploading dataset and registering it with [SciCat](https://scicatproject.github.io). It is built on
[Prefect.io](prefect.io) to orchestrate the asynchronous jobs (called flows) to archive and retrieve datasets to/from the ETH LTS.

The full setup is containerized and requires a SciCat instance to run correctly.

Refer to the [Github pages](#github-pages) for more details.

## Quick start

Build all the services:

```bash
docker compose --env-file .env.prod --env-file .env.development build
```

Starting up all services for development:

```bash
docker compose --env-file .env.prod --env-file .env.development up -d
```

## Deploy Local Flows

For development and debugging, a local process can serve flows, for example by running `python -m archiver.flows`. However, some more configuration is required to fully integration with the other services; therefore a VS Code launch command `Prefect Flows` can be used in [launch.json](./backend/.vscode/launch.json)). This allows to debug flows locally and the registered flows have a prefix, `DEV_`.


## Creating Storage Protect Client Docker Image

In order to use the [Storage Protect client](https://www.ibm.com/docs/en/storage-protect/8.1.27?topic=clients) in a container, a one time setup is necessary in which certificates and config files are created using the credential on the Storage Protect server.



| File                / Folder              |
|-------------------------------------------|
| /opt/tivoli/tsm/client/ba/bin/dsm.opt     |
| /opt/tivoli/tsm/client/ba/bin/dsm.sys     |
| /opt/tivoli/tsm/client/ba/bin/dsmcert     |
| /opt/tivoli/tsm/client/ba/bin/dsmcert.idx |
| /opt/tivoli/tsm/client/ba/bin/dsmcert.kdb |
| /opt/tivoli/tsm/client/ba/bin/dsmcert.sth |
| /etc/adsm/*                               |

### Configure Storage Protect Client using Docker container

1. Create config files on host

    storage-client-setup/dsm.opt
    ```
    SERVERNAME FILESYSTEM
    ```

    storage-client-setup/dsm.sys

    ```toml
    SERVERNAME FILESYSTEM
        COMMMETHOD        TCPIP
        NODENAME          <user name>
        TCPSERVERADDRESS  <server adress>
        TCPPORT           15209
        PASSWORDACCESS    GENERATE
        MANAGEDSERVICES   SCHEDULE
        SCHEDLOGRETENTION 30 D
        ERRORLOGRETENTION 30 D
    ```

2. Run container

   ```bash
   storage-client-setup> docker compose build
   storage-client-setup> docker compose run setup-storage-client
   ```

3. In the container, register client

   ```bash
   root@ubuntu> dsmc
   ```

   Enter user name and password when prompted

4. Exit the storage client
   ```bash
   Protect> quit
   ```

4. Copy all files and folders in table above into mounted host folder
   root@ubuntu>cp /opt/tivoli/tsm/client/ba/bin/dsm.opt /mnt/


The files generated in `deployment/.storage-client` are required to build the image at `backend/prefect/runtime.Dockerfile` which includes
the authorized Storage Protect Client CLI.


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
