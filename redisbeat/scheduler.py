# -*- coding: utf-8 -*-
# Copyright 2014 Kong Luoxing

# Licensed under the Apache License, Version 2.0 (the 'License'); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
import sys
import pickle
import traceback
from time import mktime
from functools import partial

from celery.five import values
from celery.beat import Scheduler
from redis import StrictRedis
from celery import current_app

from celery.utils.log import get_logger

logger  = get_logger(__name__)
debug, linfo, error, warning = (logger.debug, logger.info, logger.error,
                                logger.warning)


class RedisScheduler(Scheduler):
    def __init__(self, *args, **kwargs):
        app = kwargs['app']
        self.key = app.conf.get("CELERY_REDIS_SCHEDULER_KEY",
                                "celery:beat:order_tasks")
        self.schedule_url = app.conf.get("CELERY_REDIS_SCHEDULER_URL",
                                         "redis://localhost:6379")
        self.rdb = StrictRedis.from_url(self.schedule_url)
        Scheduler.__init__(self, *args, **kwargs)
        app.add_task = partial(self.add, self)

    def _remove_db(self):
        self.rdb.delete(self.key)

    def _when(self, entry, next_time_to_run):
        return mktime(entry.schedule.now().timetuple()) + (self.adjust(next_time_to_run) or 0)

    def setup_schedule(self):
        # init entries
        self.rdb.delete(self.key)
        self.merge_inplace(self.app.conf.CELERYBEAT_SCHEDULE)
        tasks = self.rdb.zrangebyscore(self.key, 0, sys.maxint)
        debug('Current schedule:\n' + '\n'.join(
            repr(pickle.loads(entry)) for entry in tasks))

    def merge_inplace(self, tasks):
        for key in tasks:
            e = self.Entry(**dict(tasks[key], name=key, app=self.app))
            self.rdb.zadd(self.key, self._when(e, e.is_due()[1]) or 0, pickle.dumps(e))

    def is_due(self, entry):
        return entry.is_due()

    def adjust(self, n, drift=-0.010):
        if n and n > 0:
            return n + drift
        return n

    def add(self, **kwargs):
        e = self.Entry(app=current_app, **kwargs)
        self.rdb.zadd(self.key, self._when(e, e.is_due()[1]) or 0, pickle.dumps(e))
        return True

    def tick(self):
        if not self.rdb.exists(self.key):
            logger.warn("key: {} not in rdb".format(self.key))
            for e in values(self.schedule):
                self.rdb.zadd(self.key, self._when(e, e.is_due()[1]) or 0, pickle.dumps(e))

        tasks = self.rdb.zrangebyscore(
            self.key, 0,
            self.adjust(mktime(self.app.now().timetuple()), drift=0.010),
            withscores=True) or []

        next_times = [self.max_interval, ]

        for task, score in tasks:
            entry = pickle.loads(task)
            is_due, next_time_to_run = self.is_due(entry)

            next_times.append(next_time_to_run)
            if is_due:
                next_entry = self.reserve(entry)
                try:
                    linfo("add task entry: {} to publisher".format(entry.name))
                    result = self.apply_async(entry)
                except Exception as exc:
                    error('Message Error: %s\n%s',
                        exc, traceback.format_stack(), exc_info=True)
                else:
                    debug('%s sent. id->%s', entry.task, result.id)
                self.rdb.zrem(self.key, task)
                self.rdb.zadd(self.key, self._when(next_entry, next_time_to_run) or 0, pickle.dumps(next_entry))

        next_task = self.rdb.zrangebyscore(self.key, 0, sys.maxint, withscores=True, num=1, start=0)
        if not next_task:
            linfo("no next task found")
            return min(next_times)
        entry = pickle.loads(next_task[0][0])
        next_times.append(self.is_due(entry)[1])

        return min(next_times)

    def close(self):
        # 在轮询结束时会被调用
        self.sync()

    @property
    def info(self):
        # 返回这个 Scheduler 的信息
        return '    . db -> {self.schedule_url}, key -> {self.key}'.format(self=self)
