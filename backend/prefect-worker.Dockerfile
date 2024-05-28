# We're using the latest version of Prefect with Python 3.10
FROM prefecthq/prefect:2-python3.11

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

RUN apt-get update -y && apt-get upgrade -y

# Configure for NFS mounts; rpcbind.service required for nfsv3 remote locking
RUN apt-get install -y nfs-common systemctl
RUN systemctl --system enable rpcbind.service


RUN pip3 install pipenv --upgrade pip

ARG USER=dev
ARG GROUP=dev

RUN groupadd -r ${GROUP} && useradd --no-log-init -d /home/${USER} -r -g ${USER} ${GROUP}

# RUN useradd -rm -d /home/${USER} -s /bin/bash -g root -G sudo -u 1000 ${USER}
USER ${USER}

WORKDIR /home/${USER}

# LTS mount folder
RUN mkdir /tmp/LTS

COPY . ./

RUN echo 'export PATH="${HOME}/.local/bin:$PATH"' >> ~/.bashrc
RUN PATH="${HOME}/.local/bin:$PATH"

RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy

# Run our flow script when the container starts
RUN echo "systemctl start rpcbind.service && pipenv run python -m archiver.flows" > start.sh
RUN chmod +x start.sh
CMD ["./start.sh"]
# CMD ["systemctl", "start", "rpcbind.service", "&&", "pipenv", "run", "python", "-m", "archiver.flows"]