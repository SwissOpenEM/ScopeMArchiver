ARG PREFECT_VERSION=latest
FROM prefecthq/prefect:${PREFECT_VERSION}

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

RUN apt-get update -y && apt-get upgrade -y

RUN apt-get install -y rsync

RUN pip3 install pipenv --upgrade pip

# LTS mount folder
ARG LTS_ROOT_FOLDER=/tmp/LTS
RUN mkdir ${LTS_ROOT_FOLDER}

RUN mkdir /opt/prefect/backend
WORKDIR /opt/prefect/backend

COPY ./backend ./

RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --system --deploy
CMD ["/bin/bash"]