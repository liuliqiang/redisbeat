# -*- coding: utf-8 -*-
# Copyright 2014 Kong Luoxing

# Licensed under the Apache License, Version 2.0 (the 'License'); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
import datetime
import logging
from functools import partial
# we don't need simplejson, builtin json module is good enough
import json
from copy import deepcopy

from celery.beat import Scheduler, ScheduleEntry
from redis import StrictRedis
from celery import current_app
import kombu.utils
import celery.schedules
from redis.exceptions import LockError

from .task import PeriodicTask
from .exceptions import ValidationError, TaskTypeError
from .decoder import DateTimeDecoder, DateTimeEncoder
from .globals import logger


class RedisScheduleEntry(object):
    """
    The Schedule Entry class is mainly here to handle the celery dependency injection
     and delegates everything to a PeriodicTask instance
    It follows the Adapter Design pattern, trivially implemented in python with __getattr__ and __setattr__
    This is similar to https://github.com/celery/django-celery/blob/master/djcelery/schedulers.py
     that uses SQLAlchemy DBModels as delegates.
    """

    def __init__(self, name=None, task=None, enabled=True, last_run_at=None,
                 total_run_count=None, schedule=None, args=(), kwargs=None,
                 options=None, app=None, **extrakwargs):

        # defaults (MUST NOT call self here - or loop __getattr__ for ever)
        app = app or current_app
        # Setting a default time a bit before now to not miss a task that was just added.
        last_run_at = last_run_at or app.now() - datetime.timedelta(
                seconds=app.conf.CELERYBEAT_MAX_LOOP_INTERVAL)

        # using periodic task as delegate
        object.__setattr__(self, '_task', PeriodicTask(
                # Note : for compatibiilty with celery methods, the name of the task is actually the key in redis DB.
                # For extra fancy fields (like a human readable name, you can leverage extrakwargs)
                name=name,
                task=task,
                enabled=enabled,
                schedule=schedule,  # TODO : sensible default here ?
                args=args,
                kwargs=kwargs or {},
                options=options or {},
                last_run_at=last_run_at,
                total_run_count=total_run_count or 0,
                **extrakwargs
        ))

        #
        # Initializing members here and not in delegate
        #

        # The app is kept here (PeriodicTask should not need it)
        object.__setattr__(self, 'app', app)

    # automatic delegation to PeriodicTask (easy delegate)
    def __getattr__(self, attr):
        return getattr(self._task, attr)

    def __setattr__(self, attr, value):
        # We set the attribute in the task delegate if available
        if hasattr(self, '_task') and hasattr(self._task, attr):
            setattr(self._task, attr, value)
            return
        # else we raise
        raise AttributeError(
                "Attribute {attr} not found in {tasktype}".format(attr=attr,
                                                                  tasktype=type(self._task)))

    #
    # Overrides schedule accessors in PeriodicTask to store dict in json but retrieve proper celery schedules
    #
    def get_schedule(self):
        if {'every', 'period'}.issubset(self._task.schedule.keys()):
            return celery.schedules.schedule(
                    datetime.timedelta(
                        **{self._task.schedule['period']: self._task.schedule['every']}),
                    self.app)
        elif {'minute', 'hour', 'day_of_week', 'day_of_month', 'month_of_year'}.issubset(
                self._task.schedule.keys()):
            return celery.schedules.crontab(minute=self._task.schedule['minute'],
                                            hour=self._task.schedule['hour'],
                                            day_of_week=self._task.schedule['day_of_week'],
                                            day_of_month=self._task.schedule['day_of_month'],
                                            month_of_year=self._task.schedule['month_of_year'],
                                            app=self.app)
        else:
            raise TaskTypeError('Existing Task schedule type not recognized')

    def set_schedule(self, schedule):
        if isinstance(schedule, celery.schedules.schedule):
            # TODO : unify this with Interval in PeriodicTask
            self._task.schedule = {
                'every': max(schedule.run_every.total_seconds(), 0),
                'period': 'seconds'
            }
        elif isinstance(schedule, celery.schedules.crontab):
            # TODO : unify this with Crontab in PeriodicTask
            self._task.schedule = {
                'minute': schedule._orig_minute,
                'hour': schedule._orig_hour,
                'day_of_week': schedule._orig_day_of_week,
                'day_of_month': schedule._orig_day_of_month,
                'month_of_year': schedule._orig_month_of_year
            }
        else:
            raise TaskTypeError('New Task schedule type not recognized')

    schedule = property(get_schedule, set_schedule)

    #
    # Overloading ScheduleEntry methods
    #
    def is_due(self):
        """See :meth:`~celery.schedule.schedule.is_due`."""
        due = self.schedule.is_due(self.last_run_at)

        logger.debug('task {0} due : {1}'.format(self.name, due))
        if not self.enabled:
            logger.info('task {0} is disabled. not triggered.'.format(self.name))
            # if the task is disabled, we always return false, but the time that
            # it is next due is returned as usual
            return celery.schedules.schedstate(is_due=False, next=due[1])

        return due

    def __repr__(self):
        return '<RedisScheduleEntry: {0.name} {call} {0.schedule}'.format(
                self,
                call=kombu.utils.reprcall(self.task, self.args or (), self.kwargs or {}),
        )

    def update(self, other):
        """
        Update values from another entry.
        This is used to dynamically update periodic entry from edited redis values
        Does not update "non-editable" fields
        Extra arguments will be updated (considered editable)
        """
        # Handle delegation properly here
        self._task.update(other._task)
        # we should never need to touch the app here

    #
    # ScheduleEntry needs to be an iterable
    #

    # from celery.beat.ScheduleEntry._default_now
    def _default_now(self):
        return self.get_schedule().now() if self.schedule else self.app.now()

    # from celery.beat.ScheduleEntry._next_instance
    def _next_instance(self, last_run_at=None):
        """Return a new instance of the same class, but with
        its date and count fields updated."""
        return self.__class__(**dict(
                self,
                last_run_at=last_run_at or self._default_now(),
                total_run_count=self.total_run_count + 1,
        ))

    __next__ = next = _next_instance  # for 2to3

    def __iter__(self):
        # We need to delegate iter (iterate on task members, not on multiple tasks)
        # Following celery.SchedulerEntry.__iter__() design
        return iter(self._task)

    @staticmethod
    def get_all_as_dict(scheduler_url, key_prefix):
        """get all of the tasks, for best performance with large amount of tasks, return a generator
        """
        # Calling another generator
        for task_key, task_dict in PeriodicTask.get_all_as_dict(scheduler_url, key_prefix):
            yield task_key, task_dict

    @classmethod
    def from_entry(cls, scheduler_url, name, **entry):
        options = entry.get('options') or {}
        fields = dict(entry)
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
            fields['interval'] = {'every': max(schedule.run_every.total_seconds(), 0),
                                  'period': 'seconds'}

        fields['args'] = fields.get('args', [])
        fields['kwargs'] = fields.get('kwargs', {})
        fields['key'] = fields['name']
        return cls(PeriodicTask.from_dict(fields, scheduler_url))


class RedisScheduler(Scheduler):
    Entry = RedisScheduleEntry

    def __init__(self, *args, **kwargs):
        if hasattr(current_app.conf, 'CELERY_REDIS_SCHEDULER_URL'):
            logger.info('backend scheduler using %s',
                        current_app.conf.CELERY_REDIS_SCHEDULER_URL)
        else:
            logger.info('backend scheduler using %s',
                        current_app.conf.CELERY_REDIS_SCHEDULER_URL)

        self.update_interval = current_app.conf.get('UPDATE_INTERVAL') or datetime.timedelta(
                seconds=10)

        # how long we should hold on to the redis lock in seconds
        if 'CELERY_REDIS_SCHEDULER_LOCK_TTL' in current_app.conf:
            lock_ttl = current_app.conf.CELERY_REDIS_SCHEDULER_LOCK_TTL
        else:
            lock_ttl = 30

        if lock_ttl < self.update_interval.seconds:
            lock_ttl = self.update_interval.seconds * 2
        self.lock_ttl = lock_ttl

        self._dirty = set()  # keeping modified entries by name for sync later on
        self._schedule = {}  # keeping dynamic schedule from redis DB here
        # self.data is used for statically configured schedule
        self.schedule_url = current_app.conf.CELERY_REDIS_SCHEDULER_URL
        self.rdb = StrictRedis.from_url(self.schedule_url)
        self._last_updated = None
        self._lock_acquired = False
        self._lock = self.rdb.lock('celery:beat:task_lock', timeout=self.lock_ttl)
        self._lock_acquired = self._lock.acquire(blocking=False)
        self.Entry.scheduler = self

        # This will launch setup_schedule if not lazy
        super(RedisScheduler, self).__init__(*args, **kwargs)

    def setup_schedule(self):
        super(RedisScheduler, self).setup_schedule()
        # In case we have a preconfigured schedule
        self.update_from_dict(self.app.conf.CELERYBEAT_SCHEDULE)

    def tick(self):
        """Run a tick, that is one iteration of the scheduler.
        Executes all due tasks.
        """
        # need to grab all data (might have been updated) from schedule DB.
        # we need to merge it with whatever schedule was set in config, and already installed default tasks
        try:
            s = self.all_as_schedule()
            self.merge_inplace(s)
        except Exception as exc:
            logger.error(
                    "Exception when getting tasks from {url} : {exc}".format(url=self.schedule_url,
                                                                             exc=exc))
            # TODO : atomic merge : be able to cancel it if there s a problem
            raise

        # displaying the schedule we got from redis
        logger.debug("DB schedule : {0}".format(self.schedule))

        # this will call self.maybe_due() to check if any entry is due.
        return super(RedisScheduler, self).tick()

    def all_as_schedule(self, key_prefix=None, entry_class=None):
        logger.debug('RedisScheduler: Fetching database schedule')
        key_prefix = key_prefix or current_app.conf.CELERY_REDIS_SCHEDULER_KEY_PREFIX
        entry_class = entry_class or self.Entry

        d = {}
        for key, task in entry_class.get_all_as_dict(self.rdb, key_prefix):
            # logger.debug('Building {0} from : {1}'.format(entry_class, task))
            d[key] = entry_class(**dict(task, app=self.app))
        return d

    def reserve(self, entry):
        # called when the task is about to be run (and data will be modified -> sync() will need to save it)
        new_entry = super(RedisScheduler, self).reserve(entry)
        # Need to store the key of the entry, because the entry may change in the mean time.
        self._dirty.add(new_entry.name)
        return new_entry

    def sync(self):
        logger.info('Writing modified entries...')
        _tried = set()
        try:
            while self._dirty:
                name = self._dirty.pop()
                _tried.add(name)
                # Saving the entry back into Redis DB.
                self.rdb.set(name, self.schedule[name].jsondump())
        except Exception as exc:
            # retry later
            self._dirty |= _tried
            logger.error('Error while sync: %r', exc, exc_info=1)

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

    @property
    def info(self):
        return '    . db -> {self.schedule_url}'.format(self=self)
