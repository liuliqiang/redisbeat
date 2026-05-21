FROM python:3.6-alpine
WORKDIR /usr/src/app

# Py3.6 is the newest Python that imports celery 3.1.x. 3.7+ chokes on
# `kombu/async/` because `async` became a reserved keyword. If you've
# already migrated off celery 3, prefer ../celery4/ or ../celery5/.
#
# Build context is the repository root (see docker-compose.yml) so we
# install redisbeat from local source. We pass --no-deps so redisbeat's
# modern jsonpickle floor doesn't clobber the era-appropriate pins in
# requirements.txt.

COPY example/celery3/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY setup.py /usr/src/redisbeat/
COPY redisbeat /usr/src/redisbeat/redisbeat
RUN pip install --no-cache-dir --no-deps /usr/src/redisbeat

COPY example/celery3/tasks.py example/celery3/add_task.py example/celery3/rem_task.py ./
