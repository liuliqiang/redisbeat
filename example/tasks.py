#!/usr/bin/env python
# encoding: utf-8
from datetime import timedelta
from celery import Celery


app = Celery('tasks', backend='redis://localhost:6379',
             broker='redis://localhost:6379')

app.conf.update(
    CELERYBEAT_SCHEDULE={
        'perminute': {
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


