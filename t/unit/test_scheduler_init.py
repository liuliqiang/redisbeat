#!/usr/bin/env python
# encoding: utf-8
import time
from datetime import timedelta
import unittest

from celery import Celery
from redis import StrictRedis

from redisbeat import RedisScheduler


redis_key = "celery:beat:order_tasks"
min_redis_score = 0
max_redis_score = 10000000000

class TestSchedulerInitPolicy(unittest.TestCase):
    def setUp(self):
        super(TestSchedulerInitPolicy, self).setUp()

        self.redis_url = 'redis://localhost:6379'
        self.redis_cli = StrictRedis.from_url(self.redis_url)
        self.redis_cli.zpopmin(redis_key, count=1000)

    def test_default_init_policy(self):
        app = Celery('tasks', backend=self.redis_url, broker=self.redis_url)

        app.conf.update(
            CELERY_REDIS_SCHEDULER_URL=self.redis_url,
            CELERY_REDIS_SCHEDULER_INIT_POLICY="DEFAULT",
            CELERYBEAT_SCHEDULE={
                'perminute': {
                    'task': 'tasks.add',
                    'schedule': timedelta(seconds=1),
                    'args': (1, 1)
                }
            }
        )
        
        RedisScheduler(app=app)
        time.sleep(3)
        RedisScheduler(app=app) # reinit again

        results = self.redis_cli.zrange(redis_key, min_redis_score, max_redis_score, withscores=True)
        self.assertEqual(len(results), 1)
        self.assertLess(results[0][1], time.time())

    def test_reset_init_policy(self):
        app = Celery('tasks', backend=self.redis_url, broker=self.redis_url)

        app.conf.update(
            CELERY_REDIS_SCHEDULER_URL=self.redis_url,
            CELERY_REDIS_SCHEDULER_INIT_POLICY="DEFAULT",
            CELERYBEAT_SCHEDULE={
                'perminute': {
                    'task': 'tasks.add',
                    'schedule': timedelta(seconds=1),
                    'args': (1, 1)
                }
            }
        )
        
        time.sleep(3)

        RedisScheduler(app=app)
        results = self.redis_cli.zrangebyscore(redis_key, min_redis_score, max_redis_score, withscores=True)
        self.assertEqual(len(results), 1)
        self.assertGreater(results[0][1], time.time())

    def test_immediately_init_policy(self):
        app = Celery('tasks', backend=self.redis_url, broker=self.redis_url)

        app.conf.update(
            CELERY_REDIS_SCHEDULER_URL=self.redis_url,
            CELERY_REDIS_SCHEDULER_INIT_POLICY="DEFAULT",
            CELERYBEAT_SCHEDULE={
                'perminute': {
                    'task': 'tasks.add',
                    'schedule': timedelta(seconds=1),
                    'args': (1, 1)
                }
            }
        )
        
        time.sleep(3)

        RedisScheduler(app=app)
        results = self.redis_cli.zrangebyscore(redis_key, min_redis_score, max_redis_score, withscores=True)
        self.assertEqual(len(results), 1)
        self.assertGreater(results[0][1], time.time())

    def test_fast_forward_init_policy(self):
        app = Celery('tasks', backend=self.redis_url, broker=self.redis_url)

        app.conf.update(
            CELERY_REDIS_SCHEDULER_URL=self.redis_url,
            CELERY_REDIS_SCHEDULER_INIT_POLICY="DEFAULT",
            CELERYBEAT_SCHEDULE={
                'perminute': {
                    'task': 'tasks.add',
                    'schedule': timedelta(seconds=1),
                    'args': (1, 1)
                }
            }
        )
        
        time.sleep(3)

        RedisScheduler(app=app)
        results = self.redis_cli.zrangebyscore(redis_key, min_redis_score, max_redis_score, withscores=True)
        self.assertEqual(len(results), 1)
        self.assertGreater(results[0][1], time.time())
