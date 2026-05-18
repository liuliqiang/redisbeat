FROM python:3.11-alpine
WORKDIR /usr/src/app

# Build context is the repository root (see docker-compose.yml) so we can
# install redisbeat directly from local source — the rediscluster:// support
# is not on PyPI yet.

COPY example/cluster/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY setup.py /usr/src/redisbeat/
COPY redisbeat /usr/src/redisbeat/redisbeat
RUN pip install --no-cache-dir --no-deps /usr/src/redisbeat

COPY example/cluster/tasks.py example/cluster/add_task.py ./
