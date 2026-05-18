#!/usr/bin/env python
# encoding: utf-8
"""Celery app wired to a Redis Cluster for redisbeat scheduling.

Env vars (set by docker-compose.yml):
  CELERY_BROKER_URL           standalone redis used as broker/backend
  CELERY_RESULT_BACKEND       standalone redis used as result backend
  CELERY_REDIS_SCHEDULER_URL  rediscluster:// URL for redisbeat
"""
from datetime import timedelta
import os

from celery import Celery


broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://broker:6379/0')
result_backend = os.environ.get('CELERY_RESULT_BACKEND', broker_url)
scheduler_url = os.environ.get(
    'CELERY_REDIS_SCHEDULER_URL',
    'rediscluster://redis-node-0:6379,redis-node-1:6379,redis-node-2:6379',
)

app = Celery('tasks', backend=result_backend, broker=broker_url)

app.conf.update(
    CELERY_REDIS_SCHEDULER_URL=scheduler_url,
    CELERYBEAT_SCHEDULE={
        'every-3-seconds': {
            'task': 'tasks.add',
            'schedule': timedelta(seconds=3),
            'args': (1, 1),
        },
    },
)


@app.task
def add(x, y):
    return x + y


@app.task
def sub(x, y):
    return x - y
