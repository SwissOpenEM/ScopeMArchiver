FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

COPY . /usr/src/app
WORKDIR /usr/src/app
RUN uv sync
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

RUN pip install --upgrade pip
RUN pip install pipenv

COPY . .
# RUN pipenv requirements > requirements.txt
# RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir .


FROM python:3.12 AS test_runner
WORKDIR /tmp
COPY --from=builder /venv /venv
COPY --from=builder /usr/src/app/tests tests
ENV PATH=/venv/bin:$PATH

# install test dependencies
RUN pip install pytest

# run tests
RUN pytest tests


FROM python:3.12 AS service
WORKDIR /root/app/site-packages
COPY --from=builder /venv /venv
ENV PATH=/venv/bin:$PATH

ENTRYPOINT [ "python", "-m", "openapi_server" ]
