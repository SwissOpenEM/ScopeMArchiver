ARG PREFECT_VERSION=latest
FROM prefecthq/prefect:${PREFECT_VERSION}

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

RUN apt-get update -y && apt-get upgrade -y

# Configure for NFS mounts; rpcbind.service required for nfsv3 remote locking
RUN apt-get install -y nfs-common systemctl rsync wget
RUN systemctl --system enable rpcbind.service

RUN pip3 install pipenv --upgrade pip

# LTS mount folder
ARG LTS_ROOT_FOLDER=/tmp/LTS
RUN mkdir ${LTS_ROOT_FOLDER}

RUN mkdir /opt/prefect/backend
WORKDIR /opt/prefect/backend

COPY ./backend/ ./

COPY ./backend/archiver/Pipfile ./
COPY ./backend/archiver/Pipfile.lock ./

RUN wget https://cacerts.digicert.com/DigiCertGlobalG2TLSRSASHA2562020CA1-1.crt.pem -O DigiCertGlobalG2TLSRSASHA2562020CA1-1.crt
RUN cp DigiCertGlobalG2TLSRSASHA2562020CA1-1.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates

ENV AWS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --system --deploy
CMD ["/bin/bash"]