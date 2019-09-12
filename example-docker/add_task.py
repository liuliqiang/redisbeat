#!/usr/bin/env python
# encoding: utf-8
from datetime import timedelta

from redisbeat.scheduler import RedisScheduler

from tasks import app


if __name__ == "__main__":
    schduler = RedisScheduler(app=app)
    schduler.add(**{
        'name': 'sub-perminute',
        'task': 'tasks.sub',
        'schedule': timedelta(seconds=3),
        'args': (1, 1)
    })
