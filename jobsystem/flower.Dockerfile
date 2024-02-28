FROM python:3.10.1

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

RUN apt-get update -y && apt-get upgrade -y

RUN pip3 install pipenv --upgrade pip

ARG USER=dev

RUN useradd -rm -d /home/${USER} -s /bin/bash -g root -G sudo -u 1000 ${USER}


WORKDIR /home/${USER}
COPY . ./

RUN chmod a+rw Pipfile Pipfile.lock

USER ${USER}

RUN echo 'export PATH="${HOME}/.local/bin:$PATH"' >> ~/.bashrc
RUN PATH="${HOME}/.local/bin:$PATH"

RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy

RUN PIPENV_VENV_IN_PROJECT=1 pipenv install flower

CMD ["pipenv", "run", "celery", "-A", "tasks", "flower"]