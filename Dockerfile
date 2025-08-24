# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT

FROM python:3.12-slim as intermediate
WORKDIR /docker
COPY requirements.txt  /docker/requirements.txt
RUN pip install -r /docker/requirements.txt
RUN apt update && apt install -y git
COPY .git .git
RUN python3 -c 'import setuptools_scm; print(setuptools_scm.get_version())' > version.txt

# copy version.txt to the final image
FROM python:3.12-slim
WORKDIR /docker

COPY requirements.txt  /docker/requirements.txt
RUN apt update && apt install -y git curl
RUN pip install -r /docker/requirements.txt

COPY . .
COPY --from=intermediate /docker/version.txt /docker/version.txt

COPY . /docker

EXPOSE 5000

# gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "main:app", "--workers", "2"]