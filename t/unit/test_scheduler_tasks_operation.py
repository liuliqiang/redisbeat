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
max_redis_score = 100000000000

class TestDynamicOeration(unittest.TestCase):
    def setUp(self):
        super(TestDynamicOeration, self).setUp()
        
        self.redis_url = 'redis://localhost:6379'
        self.redis_cli = StrictRedis.from_url(self.redis_url)
        self.redis_cli.zpopmin(redis_key, count=1000)

    def test_add_tasks(self):
        app = Celery('tasks', backend=self.redis_url, broker=self.redis_url)

        app.conf.update(
            CELERY_REDIS_SCHEDULER_URL=self.redis_url,
            CELERYBEAT_SCHEDULE={
                'perminute': {
                    'task': 'tasks.add',
                    'schedule': timedelta(seconds=3),
                    'args': (1, 1)
                }
            }
        )

        results = self.redis_cli.zrange(redis_key, min_redis_score, max_redis_score)
        self.assertEqual(len(results), 0)

        RedisScheduler(app=app)
        results = self.redis_cli.zrange(redis_key, min_redis_score, max_redis_score)
        for result in results:
            print(result)
        self.assertEqual(len(results), 1)
