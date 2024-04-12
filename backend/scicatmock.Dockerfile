FROM python:3.11.8

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

CMD ["pipenv", "run", "uvicorn", "archiver.tests.scicat_api_mock:app", "--reload", "--host", "0.0.0.0"]