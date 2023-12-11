#!/usr/bin/env python
# encoding: utf-8
from datetime import timedelta
import os

from celery import Celery


redis_url = 'redis://redis:6379'
hostname = os.getenv("HOSTNAME")
if hostname != "beat" and hostname != "worker":
    redis_url = 'redis://localhost:6379'

app = Celery('tasks', backend=redis_url, broker=redis_url)

app.conf.update(CELERY_REDIS_SCHEDULER_URL = redis_url)

if hostname == "beat":
    app.conf.update(
        CELERYBEAT_SCHEDULE={
            'every-3-seconds': {
                'task': 'tasks.add',
                'schedule': timedelta(seconds=3),
                'args': (1, 1)
            }
        }
    )


@app.task
def add(x, y):
    return x + y


@app.task
def sub(x, y):
    return x - y

