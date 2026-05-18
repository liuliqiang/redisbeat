FROM python:3.11-alpine
WORKDIR /usr/src/app

# Build context is the repository root (see docker-compose.yml) so we can
# install redisbeat directly from local source. PyPI's redisbeat==1.2.7
# still has a buggy `debug(..., str(task))` log call that spams
# "TypeError: not all arguments converted during string formatting".

COPY example/standalone/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY setup.py /usr/src/redisbeat/
COPY redisbeat /usr/src/redisbeat/redisbeat
RUN pip install --no-cache-dir --no-deps /usr/src/redisbeat

COPY example/standalone/tasks.py example/standalone/add_task.py example/standalone/rem_task.py ./
