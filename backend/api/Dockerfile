FROM python:3.11.8 AS builder

WORKDIR /usr/src/app

RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

RUN pip install --upgrade pip
RUN pip install pipenv

COPY . .
RUN pipenv requirements > requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir .


FROM python:3.11.8 AS test_runner
WORKDIR /tmp
COPY --from=builder /venv /venv
COPY --from=builder /usr/src/app/tests tests
ENV PATH=/venv/bin:$PATH

# install test dependencies
RUN pip install pytest

# run tests
RUN pytest tests


FROM python:3.11.8 AS service
WORKDIR /root/app/site-packages
COPY --from=builder /venv /venv
ENV PATH=/venv/bin:$PATH

RUN wget https://cacerts.digicert.com/DigiCertGlobalG2TLSRSASHA2562020CA1-1.crt.pem -O DigiCertGlobalG2TLSRSASHA2562020CA1-1.crt
RUN cp DigiCertGlobalG2TLSRSASHA2562020CA1-1.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates

ENV AWS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

ENTRYPOINT [ "python", "-m", "openapi_server" ]
