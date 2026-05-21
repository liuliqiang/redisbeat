FROM python:3.8-alpine
WORKDIR /usr/src/app

# Py3.8 is the newest Python officially supported by celery 4.4.x.
# 3.11+ won't import celery 4 (Click/asyncio compat). Keep this image
# pinned if you actually need celery 4 -- the modern example lives in
# ../celery5/.
#
# Build context is the repository root (see docker-compose.yml) so we
# install redisbeat from local source. PyPI's redisbeat==1.2.7 has a
# buggy debug() log call that spams "TypeError: not all arguments
# converted during string formatting".

COPY example/celery4/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY setup.py /usr/src/redisbeat/
COPY redisbeat /usr/src/redisbeat/redisbeat
RUN pip install --no-cache-dir --no-deps /usr/src/redisbeat

COPY example/celery4/tasks.py example/celery4/add_task.py example/celery4/rem_task.py ./
