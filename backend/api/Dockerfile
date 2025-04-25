FROM openapitools/openapi-generator-cli:latest AS generator
ADD ./ /local
RUN /usr/local/bin/docker-entrypoint.sh generate -i /local/openapi.yaml   -g python-fastapi   -o /local/out --global-property apis,models

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the generated project
COPY --from=generator --chown=app:app /local /app

# Change the working directory to the `app` directory
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-editable


# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable

FROM python:3.12 AS test_runner
WORKDIR /tmp
# Copy the environment, but not the source code
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder /app/tests tests

ENV PATH=/venv/bin:$PATH

# install test dependencies
RUN pip install pytest

# run tests
RUN pytest tests

FROM python:3.12-slim

# Copy the environment, but not the source code
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Run the application
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT [ "python", "-m", "openapi_server" ]
