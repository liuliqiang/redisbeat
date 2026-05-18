#!/usr/bin/env python
# encoding: utf-8
"""Integration tests for the four init policies.

These tests require a live Redis at ``localhost:6379`` -- they are unit-style
in shape but exercise real Redis to make sure the serialized schedule has the
score / ``last_run_at`` shape each policy promises.
"""
import time
from datetime import datetime, timedelta
from time import mktime
import unittest

import jsonpickle
from celery import Celery
from redis import StrictRedis

from redisbeat import RedisScheduler
from redisbeat.constants import (
    INIT_POLICY_DEFAULT,
    INIT_POLICY_FAST_FORWARD,
    INIT_POLICY_IMMEDIATELY,
    INIT_POLICY_RESET,
)


redis_key = "celery:beat:order_tasks"
min_redis_score = 0
max_redis_score = 10000000000


def _scheduler_now_epoch():
    """Mirror ``RedisScheduler._when``'s clock anchor.

    The scheduler stores scores via ``mktime(schedule.now().timetuple())``,
    where ``schedule.now()`` is the (UTC) ``app.now()`` from Celery. Feeding a
    UTC ``timetuple`` to ``mktime`` (which interprets it as local time) yields
    a value offset from ``time.time()`` by the system TZ; the tests only care
    about the relative position of the score, so we reproduce the same anchor.
    """
    return mktime(datetime.utcnow().timetuple())


class TestSchedulerInitPolicy(unittest.TestCase):
    def setUp(self):
        super(TestSchedulerInitPolicy, self).setUp()

        self.redis_url = 'redis://localhost:6379'
        self.redis_cli = StrictRedis.from_url(self.redis_url)
        self.redis_cli.delete(redis_key)

    def tearDown(self):
        self.redis_cli.delete(redis_key)
        super(TestSchedulerInitPolicy, self).tearDown()

    # ------------------------------------------------------------------ helpers

    def _build_app(self, policy):
        app = Celery('tasks', backend=self.redis_url, broker=self.redis_url)
        app.conf.update(
            CELERY_REDIS_SCHEDULER_URL=self.redis_url,
            CELERY_REDIS_SCHEDULER_INIT_POLICY=policy,
            CELERYBEAT_SCHEDULE={
                'perminute': {
                    'task': 'tasks.add',
                    'schedule': timedelta(seconds=1),
                    'args': (1, 1),
                },
            },
        )
        return app

    def _only_entry(self):
        results = self.redis_cli.zrange(
            redis_key, min_redis_score, max_redis_score, withscores=True)
        self.assertEqual(len(results), 1, "expected exactly one entry in redis")
        blob, score = results[0]
        return jsonpickle.decode(blob), score

    # -------------------------------------------------------------------- tests

    def test_default_init_policy_preserves_last_run_at(self):
        """DEFAULT: ``last_run_at`` must be preserved across restarts so that
        ``tick`` can replay each missed run."""
        app = self._build_app(INIT_POLICY_DEFAULT)

        RedisScheduler(app=app)
        initial_entry, _ = self._only_entry()
        original_last_run = initial_entry.last_run_at

        time.sleep(2.2)

        RedisScheduler(app=app)  # reinit
        entry, _score = self._only_entry()

        # last_run_at must NOT have been bumped by the restart.
        self.assertEqual(entry.last_run_at, original_last_run)

    def test_reset_init_policy_updates_last_run_at(self):
        """RESET: ``last_run_at`` is bumped to the restart moment so the task
        next fires one full interval from now."""
        app = self._build_app(INIT_POLICY_RESET)

        RedisScheduler(app=app)
        initial_entry, _ = self._only_entry()
        original_last_run = initial_entry.last_run_at

        time.sleep(2.2)

        before_reinit = _scheduler_now_epoch()
        RedisScheduler(app=app)  # reinit
        entry, score = self._only_entry()

        self.assertGreater(entry.last_run_at, original_last_run)
        # Score should be ~ now + interval (1s), definitely in the future.
        self.assertGreater(score, before_reinit)

    def test_immediately_init_policy_fires_now(self):
        """IMMEDIATELY: score is collapsed to the restart moment so ``tick``
        picks the task up on the very next pass."""
        app = self._build_app(INIT_POLICY_IMMEDIATELY)

        RedisScheduler(app=app)
        time.sleep(2.2)

        before_reinit = _scheduler_now_epoch()
        RedisScheduler(app=app)  # reinit
        _entry, score = self._only_entry()

        # Score must be at-or-before "now-ish" so the next tick fires the task.
        self.assertLessEqual(score, before_reinit + 0.5)

    def test_fast_forward_init_policy_collapses_missed_runs(self):
        """FAST_FORWARD: missed runs are collapsed into a single immediate
        run, then the cadence resumes normally."""
        app = self._build_app(INIT_POLICY_FAST_FORWARD)

        RedisScheduler(app=app)
        initial_entry, _ = self._only_entry()
        original_last_run = initial_entry.last_run_at

        time.sleep(2.2)

        before_reinit = _scheduler_now_epoch()
        RedisScheduler(app=app)  # reinit
        entry, score = self._only_entry()

        # last_run_at advances to ~ (now - interval) so exactly one fire is due.
        self.assertGreater(entry.last_run_at, original_last_run)
        # Score is now-ish so the entry is immediately due once.
        self.assertLessEqual(score, before_reinit + 0.5)

    def test_unknown_init_policy_raises(self):
        app = self._build_app('NOT_A_REAL_POLICY')
        with self.assertRaises(ValueError):
            RedisScheduler(app=app)
