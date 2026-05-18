#!/usr/bin/env python
# encoding: utf-8
"""Smoke test: connect to the Redis Cluster via redisbeat and register a task.

Run from inside the worker/beat container, e.g.:
    docker compose run --rm beat python add_task.py
"""
from datetime import timedelta
import logging
import sys

from redisbeat.scheduler import RedisScheduler

from tasks import app


root = logging.getLogger()
root.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
root.addHandler(handler)


if __name__ == "__main__":
    scheduler = RedisScheduler(app=app, skip_init=True)
    scheduler.add(**{
        'name': 'sub-every-5-seconds',
        'task': 'tasks.sub',
        'schedule': timedelta(seconds=5),
        'args': (2, 1),
    })
    print("task registered on cluster")
