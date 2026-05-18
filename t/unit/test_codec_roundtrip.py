#!/usr/bin/env python
# encoding: utf-8
"""Regression test for issue #42.

jsonpickle <= 3.0.0 cannot round-trip a ``celery.beat.ScheduleEntry``
(the datetime fields inside crash decode with
``TypeError: 'NoneType' object is not callable`` on 1.x/2.x or
``'module' object is not callable`` on 3.0.0). The bug was fixed in
jsonpickle 3.2.0+, so we just need to require a non-broken version --
no custom DatetimeHandler is needed.

This test guards against re-pinning to a known-broken version.
"""
from datetime import timedelta
import unittest

from celery import Celery
from celery.beat import ScheduleEntry

from redisbeat.scheduler import Codec


class TestCodecRoundtrip(unittest.TestCase):
    def test_schedule_entry_roundtrip(self):
        app = Celery('t')
        entry = ScheduleEntry(
            name='perminute',
            task='tasks.add',
            schedule=timedelta(seconds=3),
            args=(1, 1),
            app=app,
        )

        codec = Codec()
        blob = codec.encode(entry)
        restored = codec.decode(blob)

        self.assertEqual(restored.name, entry.name)
        self.assertEqual(restored.task, entry.task)
        # last_run_at must come back as an aware datetime equal to the
        # original (this is the field that broke under issue #42).
        self.assertEqual(restored.last_run_at, entry.last_run_at)


if __name__ == '__main__':
    unittest.main()
