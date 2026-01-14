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
RUN uv add prefect-docker==0.6.6

FROM prefecthq/prefect:${PREFECT_VERSION} AS test_runner
RUN mkdir -p /app/backend/archiver

WORKDIR /app/backend/archiver

COPY --from=builder --chown=app:app /app/backend/archiver /app/backend/archiver

RUN uv add pytest

RUN uv run pytest . --junitxml=junit/test-results.xml --cov=. --cov-report=xml --cov-report=html


FROM prefecthq/prefect:${PREFECT_VERSION} AS runtime
COPY --from=builder --chown=app:app /app/backend/archiver /app/backend/archiver

RUN apt-get update -y && apt-get upgrade -y
RUN apt install curl gpg -y

# Install the Storage Protect Client
RUN echo "deb [arch=amd64] https://sp-repo.ethz.ch/apt/ stable main" > /etc/apt/sources.list.d/sp-repo.list
RUN cat /etc/apt/sources.list.d/sp-repo.list

RUN curl -s https://sp-repo.ethz.ch/sp-repo.gpg | gpg --no-default-keyring --keyring gnupg-ring:/etc/apt/trusted.gpg.d/sp-repo.gpg --import

RUN chmod 666 /etc/apt/trusted.gpg.d/sp-repo.gpg
RUN apt-get update -y
RUN apt-get install gskcrypt64 gskssl64 tivsm-api64 tivsm-ba
RUN ldconfig /usr/lib64
RUN mkdir /etc/adsm

ARG UID=123
ARG GID=123

RUN mkdir /storage

ARG USER=app
RUN useradd -rm -d /home/${USER} -s /bin/bash  -u ${UID} ${USER}

RUN chown ${UID}:${GID} /storage

COPY --from=storage-client --chown=${UID}:${GID} dsm.opt /opt/tivoli/tsm/client/ba/bin/dsm.opt
COPY --from=storage-client --chown=${UID}:${GID} dsm.sys /opt/tivoli/tsm/client/ba/bin/dsm.sys
COPY --from=storage-client --chown=${UID}:${GID} dsmcert /opt/tivoli/tsm/client/ba/bin/dsmcert
COPY --from=storage-client --chown=${UID}:${GID} dsmcert.idx /opt/tivoli/tsm/client/ba/bin/dsmcert.idx
COPY --from=storage-client --chown=${UID}:${GID} dsmcert.kdb /opt/tivoli/tsm/client/ba/bin/dsmcert.kdb
COPY --from=storage-client --chown=${UID}:${GID} dsmcert.sth /opt/tivoli/tsm/client/ba/bin/dsmcert.sth
COPY --from=storage-client --chown=${UID}:${GID} adsm/ /etc/adsm/

USER ${USER}

WORKDIR /home/${USER}

ENV PYTHONPATH="/app/backend/archiver"
ENV PATH="/app/backend/archiver/.venv/bin:$PATH"
CMD ["/bin/bash"]