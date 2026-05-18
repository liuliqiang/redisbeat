#!/usr/bin/env python
# encoding: utf-8
from datetime import timedelta
import logging
import sys

from redisbeat.scheduler import RedisScheduler

from tasks import app

root = logging.getLogger()
root.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
root.addHandler(handler)

if __name__ == "__main__":
    schduler = RedisScheduler(app=app, skip_init=True)
    schduler.add(**{
        'name': 'sub-every-3-seconds',
        'task': 'tasks.sub',
        'schedule': timedelta(seconds=3),
        'args': (1, 1)
    })
