#!/usr/bin/env python
# encoding: utf-8
from datetime import timedelta
from celery import Celery


app = Celery('tasks', backend='redis://redis:6379',
             broker='redis://redis:6379')

app.conf.update(
    CELERY_REDIS_SCHEDULER_URL = 'redis://redis:6379',
    BROKER_URL = "redis://localhost:6379/0",
    CELERY_REDIS_SCHEDULER_KEY_PREFIX = 'tasks:meta:',
    CELERYBEAT_SCHEDULE={
        'add-every-3-seconds': {
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


