ARG PREFECT_VERSION=3.4.6-python3.13
FROM prefecthq/prefect:${PREFECT_VERSION} AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/


RUN mkdir -p /app/backend/archiver

WORKDIR /app/backend/archiver

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-editable

COPY ./ /app/backend/archiver/

# docker executor needs prefect-docker
RUN uv add prefect-docker==0.6.1

FROM prefecthq/prefect:${PREFECT_VERSION} AS test_runner
RUN mkdir -p /app/backend/archiver

WORKDIR /app/backend/archiver

COPY --from=builder --chown=app:app /app/backend/archiver /app/backend/archiver

RUN uv add pytest

RUN uv run pytest tests --junitxml=junit/test-results.xml --cov=. --cov-report=xml --cov-report=html


FROM prefecthq/prefect:${PREFECT_VERSION} AS runtime
COPY --from=builder --chown=app:app /app/backend/archiver /app/backend/archiver

RUN apt-get update -y && apt-get upgrade -y

# Configure for NFS mounts; rpcbind.service required for nfsv3 remote locking
RUN apt-get install -y nfs-common systemctl rsync wget
RUN systemctl --system enable rpcbind.service

# LTS mount folder
ARG LTS_ROOT_FOLDER=/tmp/LTS
RUN mkdir ${LTS_ROOT_FOLDER}

ARG UID=123
ARG GID=123
RUN chown -R ${UID}:${GID} /app

ARG USER=app
RUN useradd -rm -d /home/${USER} -s /bin/bash  -u ${UID} ${USER}
USER ${USER}

ENV PATH="/app/backend/archiver/.venv/bin:$PATH"
CMD ["/bin/bash"]