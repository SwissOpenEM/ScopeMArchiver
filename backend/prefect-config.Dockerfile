FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /archiver/

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=archiver/uv.lock,target=uv.lock \
    --mount=type=bind,source=archiver/pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-editable

ADD archiver /archiver/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable


FROM python:3.12-slim AS runtime
# # Copy the environment, but not the source code
COPY --from=builder --chown=app:app /archiver /archiver

COPY ./prefect-config.py /

ENV PATH="/archiver/.venv/bin:$PATH"
# Run our flow script when the container starts
ENTRYPOINT ["python", "prefect-config.py"]