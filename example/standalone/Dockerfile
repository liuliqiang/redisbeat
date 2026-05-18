FROM python:3.11-alpine
WORKDIR /usr/src/app

# Bumped from python:2.7-alpine. Py2.7 went EOL in 2020 and can't install
# the post-#42 jsonpickle (3.x is Py3-only) or celery 5.x.

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app
