#!/usr/bin/env python
# encoding: utf-8
import unittest
from datetime import timedelta
from unittest.mock import MagicMock

from celery import Celery
from celery.beat import ScheduleEntry

from redisbeat import RedisScheduler


class FailingCodec(object):
    def decode(self, obj):
        if isinstance(obj, bytes) and obj == b'bad':
            raise ValueError('cannot decode')
        return obj

    def encode(self, obj):
        return b'encoded:' + obj.name.encode('utf-8')


class TestSchedulerDecodeErrors(unittest.TestCase):
    def _scheduler(self):
        app = Celery('tasks')
        app.conf.update(CELERYBEAT_SCHEDULE={})
        scheduler = RedisScheduler.__new__(RedisScheduler)
        scheduler.app = app
        scheduler.Entry = ScheduleEntry
        scheduler.codec = FailingCodec()
        scheduler.key = "celery:beat:order_tasks"
        scheduler.rdb = MagicMock()
        scheduler._when = lambda entry, next_run_time: 123.0
        scheduler._calculate_next_run_time_with_init_policy = (
            lambda entry: (10.0, entry)
        )
        scheduler.skip_init = False
        return scheduler

    def test_merge_inplace_drops_undecodable_entries_and_keeps_valid_tasks(self):
        scheduler = self._scheduler()
        old_entry = ScheduleEntry(
            name='perminute',
            task='tasks.add',
            schedule=timedelta(seconds=3),
            args=(1, 1),
            app=scheduler.app,
        )
        scheduler.rdb.zrangebyscore.return_value = [
            (b'bad', 1.0),
            (old_entry, 2.0),
        ]

        scheduler.merge_inplace({
            'perminute': {
                'task': 'tasks.add',
                'schedule': timedelta(seconds=3),
                'args': (1, 1),
            }
        })

        zrem_args = [call.args for call in scheduler.rdb.zrem.call_args_list]
        self.assertIn((scheduler.key, b'bad'), zrem_args)
        self.assertTrue(
            any(args[0] == scheduler.key and args[1] is old_entry
                for args in zrem_args)
        )
        scheduler.rdb.zadd.assert_called_once()

    def test_setup_schedule_drops_undecodable_entries_and_rewrites_valid_entries(self):
        scheduler = self._scheduler()
        good_entry = ScheduleEntry(
            name='perminute',
            task='tasks.add',
            schedule=timedelta(seconds=3),
            args=(1, 1),
            app=scheduler.app,
        )
        scheduler.rdb.zrange.return_value = [b'bad', good_entry]
        scheduler.merge_inplace = MagicMock()

        scheduler.setup_schedule()

        zrem_args = [call.args for call in scheduler.rdb.zrem.call_args_list]
        self.assertIn((scheduler.key, b'bad'), zrem_args)
        self.assertTrue(
            any(args[0] == scheduler.key and args[1] is good_entry
                for args in zrem_args)
        )
        scheduler.rdb.zadd.assert_called_once()


if __name__ == "__main__":
    unittest.main()
