ARG PREFECT_VERSION
FROM prefecthq/prefect:${PREFECT_VERSION}

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

RUN apt-get update -y && apt-get upgrade -y

RUN pip3 install pipenv --upgrade pip

ARG USER=dev
ARG GROUP=dev

RUN groupadd -r ${GROUP} && useradd --no-log-init -d /home/${USER} -r -g ${USER} ${GROUP}

WORKDIR /home/${USER}/backend

COPY . ./

RUN pipenv install prefect-docker==0.6.1

RUN echo 'export PATH="${HOME}/.local/bin:$PATH"' >> ~/.bashrc
RUN PATH="${HOME}/.local/bin:$PATH"

RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --system --deploy

ENV PYTHONPATH=/home/${USER}
USER ${USER}
CMD ["python", "archiver/mock_flows.py"]