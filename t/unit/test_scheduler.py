#!/usr/bin/env python
# encoding: utf-8
from datetime import timedelta
import os
import unittest

from celery import Celery
from redis import StrictRedis

from redisbeat import RedisScheduler


class TestStringMethods(unittest.TestCase):
    def test_redisbeat(self):
        redis_url = 'redis://localhost:6379'
        hostname = os.getenv("HOSTNAME")
        if hostname != "beat" and hostname != "worker":
            redis_url = 'redis://localhost:6379'

        app = Celery('tasks', backend=redis_url, broker=redis_url)

        app.conf.update(CELERY_REDIS_SCHEDULER_URL = redis_url)
        app.conf.update(
            CELERYBEAT_SCHEDULE={
                'perminute': {
                    'task': 'tasks.add',
                    'schedule': timedelta(seconds=3),
                    'args': (1, 1)
                }
            }
        )

        scheduler = RedisScheduler(app=app)
        redis_cli = StrictRedis.from_url(redis_url)
        results = redis_cli.zrangebyscore("celery:beat:order_tasks", 0, 10000000000000000, withscores=True)
        for result in results:
            print(result)
        self.assertEqual(len(results), 1)
