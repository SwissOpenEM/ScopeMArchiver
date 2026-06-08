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

ARG UID=123
ARG GID=123


ARG USER=app
RUN useradd -rm -d /home/${USER} -s /bin/bash  -u ${UID} ${USER}

USER ${USER}

WORKDIR /home/${USER}

ENV PYTHONPATH="/app/backend/archiver"
ENV PATH="/app/backend/archiver/.venv/bin:$PATH"
CMD ["/bin/bash"]