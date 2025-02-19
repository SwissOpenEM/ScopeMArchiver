FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN mkdir /app

WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-editable

COPY ./flows /app/flows

RUN apt-get update -y && apt-get upgrade -y

# Configure for NFS mounts; rpcbind.service required for nfsv3 remote locking
RUN apt-get install -y nfs-common systemctl rsync wget
RUN systemctl --system enable rpcbind.service

# LTS mount folder
ARG LTS_ROOT_FOLDER=/tmp/LTS
RUN mkdir ${LTS_ROOT_FOLDER}

CMD ["/bin/bash"]