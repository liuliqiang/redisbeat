# -*- coding: utf-8 -*-
# Copyright 2014 Kong Luoxing

# Licensed under the Apache License, Version 2.0 (the 'License'); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
import datetime
from copy import deepcopy

try:
    import simplejson as json
except ImportError:
    import json

import celery.schedules

from .decoder import DateTimeDecoder, DateTimeEncoder
from .globals import rdb, bytes_to_str, default_encoding


class PeriodicTask(object):
    '''represents a periodic task
    '''
    name = None
    task = None

    type_ = None

    interval = None
    crontab = None

    args = []
    kwargs = {}

    queue = None
    exchange = None
    routing_key = None

    # datetime
    expires = None
    enabled = True

    # datetime
    last_run_at = None

    total_run_count = 0

    date_changed = None
    description = None

    no_changes = False

    def __init__(self, name, task, schedule, key, queue='celery', enabled=True, task_args=[], task_kwargs={}, **kwargs):
        self.task = task
        self.enabled = enabled
        if isinstance(schedule, self.Interval):
            self.interval = schedule
        if isinstance(schedule, self.Crontab):
            self.crontab = schedule

        self.queue = queue

        self.args = task_args
        self.kwargs = task_kwargs

        self.name = name
        self.key = key

        self.running = False

    class Interval(object):

        def __init__(self, every, period='seconds'):
            self.every = every
            # could be seconds minutes hours
            self.period = period

        @property
        def schedule(self):
            return celery.schedules.schedule(datetime.timedelta(**{self.period: self.every}))

        @property
        def period_singular(self):
            return self.period[:-1]

        def __unicode__(self):
            if self.every == 1:
                return 'every {0.period_singular}'.format(self)
            return 'every {0.every} {0.period}'.format(self)

    class Crontab(object):

        def __init__(self, minute, hour, day_of_week, day_of_month, month_of_year):
            self.minute = minute
            self.hour = hour
            self.day_of_week = day_of_week
            self.day_of_month = day_of_month
            self.month_of_year = month_of_year

        @property
        def schedule(self):
            return celery.schedules.crontab(minute=self.minute,
                                            hour=self.hour,
                                            day_of_week=self.day_of_week,
                                            day_of_month=self.day_of_month,
                                            month_of_year=self.month_of_year)

        def __unicode__(self):
            rfield = lambda f: f and str(f).replace(' ', '') or '*'
            return '{0} {1} {2} {3} {4} (m/h/d/dM/MY)'.format(
                rfield(self.minute), rfield(self.hour), rfield(self.day_of_week),
                rfield(self.day_of_month), rfield(self.month_of_year),
            )

    @staticmethod
    def get_all(key_prefix):
        """get all of the tasks, for best performance with large amount of tasks, return a generator
        """
        tasks = rdb.keys(key_prefix + '*')
        for task_key in tasks:
            try:
                dct = json.loads(bytes_to_str(rdb.get(task_key)), cls=DateTimeDecoder, encoding=default_encoding)
                # task name should always correspond to the key in redis to avoid
                # issues arising when saving keys - we want to add information to
                # the current key, not create a new key
                dct['key'] = task_key
                yield dct
            except json.JSONDecodeError:  # handling bad json format by ignoring the task
                logger.warning('ERROR Reading task value at %s', task_key)

    def delete(self):
        rdb.delete(self.name)

    def save(self):
        # must do a deepcopy
        self_dict = deepcopy(self.__dict__)
        if self_dict.get('interval'):
            self_dict['interval'] = self.interval.__dict__
        if self_dict.get('crontab'):
            self_dict['crontab'] = self.crontab.__dict__

        # remove the key from the dict so we don't save it into the redis
        del self_dict['key']
        rdb.set(self.key, json.dumps(self_dict, cls=DateTimeEncoder))

    def clean(self):
        """validation to ensure that you only have
        an interval or crontab schedule, but not both simultaneously"""
        if self.interval and self.crontab:
            msg = 'Cannot define both interval and crontab schedule.'
            raise ValidationError(msg)
        if not (self.interval or self.crontab):
            msg = 'Must defined either interval or crontab schedule.'
            raise ValidationError(msg)

    @staticmethod
    def from_dict(d):
        """
        build PeriodicTask instance from dict
        :param d: dict
        :return: PeriodicTask instance
        """
        if d.get('interval'):
            schedule = PeriodicTask.Interval(d['interval']['every'], d['interval']['period'])
        if d.get('crontab'):
            schedule = PeriodicTask.Crontab(
                d['crontab']['minute'],
                d['crontab']['hour'],
                d['crontab']['day_of_week'],
                d['crontab']['day_of_month'],
                d['crontab']['month_of_year']
            )
        task = PeriodicTask(d['name'], d['task'], schedule, d['key'])
        for elem in d:
            if elem not in ('interval', 'crontab', 'schedule'):
                setattr(task, elem, d[elem])
        return task

    @property
    def schedule(self):
        if self.interval:
            return self.interval.schedule
        elif self.crontab:
            return self.crontab.schedule
        else:
            raise Exception('must define interval or crontab schedule')

    def __unicode__(self):
        fmt = '{0.name}: {{no schedule}}'
        if self.interval:
            fmt = '{0.name}: {0.interval}'
        elif self.crontab:
            fmt = '{0.name}: {0.crontab}'
        else:
            raise Exception('must define internal or crontab schedule')
        return fmt.format(self)
