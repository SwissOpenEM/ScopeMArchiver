# We're using the latest version of Prefect with Python 3.10
FROM prefecthq/prefect:2-python3.11

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

RUN apt-get update -y && apt-get upgrade -y

RUN pip3 install pipenv --upgrade pip

ARG USER=dev

RUN useradd -rm -d /home/${USER} -s /bin/bash -g root -G sudo -u 1000 ${USER}
USER ${USER}

WORKDIR /home/${USER}

RUN mkdir /tmp/archiving

COPY . ./

RUN echo 'export PATH="${HOME}/.local/bin:$PATH"' >> ~/.bashrc
RUN PATH="${HOME}/.local/bin:$PATH"

RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy

# Run our flow script when the container starts
CMD ["pipenv", "run", "python", "-m", "archiver.config", "-c", "/var/local/config.toml"]
ENTRYPOINT ["pipenv", "run", "python", "-m", "archiver.config", "-c"]