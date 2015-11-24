# -*- coding: utf-8 -*-
# Copyright 2014 Kong Luoxing

# Licensed under the Apache License, Version 2.0 (the 'License'); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
import datetime

from celery.beat import Scheduler, ScheduleEntry
from celery import current_app
import celery.schedules
from redis.exceptions import LockError

from .task import PeriodicTask
from .globals import rdb, logger, ADD_ENTRY_ERROR


class RedisScheduleEntry(ScheduleEntry):
    scheduler = None

    def __init__(self, task):
        self._task = task

        self.app = current_app._get_current_object()
        self.name = self._task.key  # passing key here as the task name is a human use only field.
        self.task = self._task.task

        self.schedule = self._task.schedule

        self.args = self._task.args
        self.kwargs = self._task.kwargs
        self.options = {
            'queue': self._task.queue,
            'exchange': self._task.exchange,
            'routing_key': self._task.routing_key,
            'expires': self._task.expires
        }
        if not self._task.total_run_count:
            self._task.total_run_count = 0
        self.total_run_count = self._task.total_run_count

        if not self._task.last_run_at:
            # subtract some time from the current time to populate the last time
            # that the task was run so that a newly scheduled task does not get missed
            time_subtract = (self.app.conf.CELERYBEAT_MAX_LOOP_INTERVAL or 30)
            self._task.last_run_at = self._default_now() - datetime.timedelta(seconds=time_subtract)
            self.save()
        self.last_run_at = self._task.last_run_at

    def _default_now(self):
        return self.app.now()

    def next(self):
        self._task.last_run_at = self.app.now()
        self._task.total_run_count += 1
        return self.__class__(self._task)

    __next__ = next

    def is_due(self):
        due = self.schedule.is_due(self.last_run_at)

        if not self.scheduler._lock_acquired:
            return celery.schedules.schedstate(is_due=False, next=due[1])

        if not self._task.enabled:
            logger.info('task %s disabled', self.name)
            # if the task is disabled, we always return false, but the time that
            # it is next due is returned as usual
            return celery.schedules.schedstate(is_due=False, next=due[1])

        return due

    def __repr__(self):
        return '<RedisScheduleEntry ({0} {1}(*{2}, **{3}) {{4}})>'.format(
            self.name, self.task, self.args,
            self.kwargs, self.schedule,
        )

    def reserve(self, entry):
        new_entry = Scheduler.reserve(entry)
        return new_entry

    def save(self):
        if self.total_run_count > self._task.total_run_count:
            self._task.total_run_count = self.total_run_count
        if self.last_run_at and self._task.last_run_at and self.last_run_at > self._task.last_run_at:
            self._task.last_run_at = self.last_run_at
        self._task.save()

    @classmethod
    def from_entry(cls, name, skip_fields=('relative', 'options'), **entry):
        options = entry.get('options') or {}
        fields = dict(entry)
        for skip_field in skip_fields:
            fields.pop(skip_field, None)
        fields['name'] = current_app.conf.CELERY_REDIS_SCHEDULER_KEY_PREFIX + name
        schedule = fields.pop('schedule')
        schedule = celery.schedules.maybe_schedule(schedule)
        if isinstance(schedule, celery.schedules.crontab):
            fields['crontab'] = {
                'minute': schedule._orig_minute,
                'hour': schedule._orig_hour,
                'day_of_week': schedule._orig_day_of_week,
                'day_of_month': schedule._orig_day_of_month,
                'month_of_year': schedule._orig_month_of_year
            }
        elif isinstance(schedule, celery.schedules.schedule):
            fields['interval'] = {'every': max(schedule.run_every.total_seconds(), 0), 'period': 'seconds'}

        fields['args'] = fields.get('args', [])
        fields['kwargs'] = fields.get('kwargs', {})
        fields['queue'] = options.get('queue')
        fields['exchange'] = options.get('exchange')
        fields['routing_key'] = options.get('routing_key')
        fields['key'] = fields['name']
        return cls(PeriodicTask.from_dict(fields))


class RedisScheduler(Scheduler):
    # how often should we sync in schedule information
    # from the backend redis database
    UPDATE_INTERVAL = datetime.timedelta(seconds=5)

    Entry = RedisScheduleEntry

    def __init__(self, *args, **kwargs):
        if hasattr(current_app.conf, 'CELERY_REDIS_SCHEDULER_URL'):
            logger.info('backend scheduler using %s',
                                      current_app.conf.CELERY_REDIS_SCHEDULER_URL)
        else:
            logger.info('backend scheduler using %s',
                                      current_app.conf.CELERY_REDIS_SCHEDULER_URL)

        self._schedule = {}
        self._last_updated = None
        Scheduler.__init__(self, *args, **kwargs)
        self.max_interval = (kwargs.get('max_interval') \
                             or self.app.conf.CELERYBEAT_MAX_LOOP_INTERVAL or 300)
        self._lock = rdb.lock('celery:beat:task_lock')
        self._lock_acquired = self._lock.acquire(blocking=False)
        self.Entry.scheduler = self

    def setup_schedule(self):
        self.install_default_entries(self.schedule)
        self.update_from_dict(self.app.conf.CELERYBEAT_SCHEDULE)

    def requires_update(self):
        """check whether we should pull an updated schedule
        from the backend database"""
        if not self._last_updated:
            return True
        return self._last_updated + self.UPDATE_INTERVAL < datetime.datetime.now()

    def tick(self):
        if not self._lock_acquired:
            self._lock_acquired = self._lock.acquire(blocking=False)

        # still cannot get lock
        if not self._lock_acquired:
            logger.warn('another beat is running, disable this node util it is shutdown')
        return super(RedisScheduler, self).tick()

    def get_from_database(self):
        self.sync()
        d = {}
        for task in PeriodicTask.get_all(current_app.conf.CELERY_REDIS_SCHEDULER_KEY_PREFIX):
            t = PeriodicTask.from_dict(task)
            d[t.key] = RedisScheduleEntry(t)
        return d

    def update_from_dict(self, dict_):
        s = {}
        for name, entry in dict_.items():
            try:
                s[name] = self.Entry.from_entry(name, **entry)
            except Exception as exc:
                error(ADD_ENTRY_ERROR, name, exc, entry)
        self.schedule.update(s)

    @property
    def schedule(self):
        if self.requires_update():
            self._schedule = self.get_from_database()
            self._last_updated = datetime.datetime.now()
        return self._schedule

    def sync(self):
        for entry in self._schedule.values():
            entry.save()

    def close(self):
        try:
            self._lock.release()
        except LockError:
            pass
        self.sync()

    def __del__(self):
        # celery beat will create Scheduler twice, first time create then destroy it, so we need release lock here
        try:
            self._lock.release()
        except LockError:
            pass
