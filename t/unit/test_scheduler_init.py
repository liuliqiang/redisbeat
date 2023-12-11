#!/usr/bin/env python
# encoding: utf-8
from datetime import timedelta
import os
import unittest

from celery import Celery
from redis import StrictRedis

from redisbeat import RedisScheduler


redis_key = "celery:beat:order_tasks"
min_redis_score = 0
max_redis_score = 10000000000000000

class TestSchedulerInitPolicy(unittest.TestCase):
    def setUp(self):
        super(TestSchedulerInitPolicy, self).setUp()

        self.redis_url = 'redis://localhost:6379'
        self.redis_cli = StrictRedis.from_url(self.redis_url)
        self.redis_cli.zpopmin(redis_key, count=1000)

    def test_redisbeat(self):
        app = Celery('tasks', backend=self.redis_url, broker=self.redis_url)

        app.conf.update(CELERY_REDIS_SCHEDULER_URL = self.redis_url)
        app.conf.update(
            CELERYBEAT_SCHEDULE={
                'perminute': {
                    'task': 'tasks.add',
                    'schedule': timedelta(seconds=3),
                    'args': (1, 1)
                }
            }
        )

        RedisScheduler(app=app)
        results = self.redis_cli.zrangebyscore(redis_key, min_redis_score, max_redis_score, withscores=True)
        for result in results:
            print(result)
        self.assertEqual(len(results), 1)
