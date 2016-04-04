# -*- coding: utf-8 -*-
# Copyright 2014 Kong Luoxing

# Licensed under the Apache License, Version 2.0 (the 'License'); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
import celery.schedules
import datetime
import json

from .decoder import DateTimeDecoder, DateTimeEncoder
from .exceptions import TaskTypeError
from .globals import bytes_to_str, default_encoding, logger


class Interval(object):

    def __init__(self, every, period='seconds'):
        self.every = every
        # could be seconds minutes hours
        self.period = period

    @property
    def period_singular(self):
        return self.period[:-1]

    def __unicode__(self):
        if self.every == 1:
            return 'every {0.period_singular}'.format(self)
        return 'every {0.every} {0.period}'.format(self)


class Crontab(object):

    def __init__(self, minute=0, hour=0, day_of_week=None, day_of_month=None, month_of_year=None):
        self.minute = minute
        self.hour = hour
        self.day_of_week = day_of_week or '*'
        self.day_of_month = day_of_month or '*'
        self.month_of_year = month_of_year or '*'

    def __unicode__(self):
        rfield = lambda f: f and str(f).replace(' ', '') or '*'
        return '{0} {1} {2} {3} {4} (m/h/d/dM/MY)'.format(
            rfield(self.minute), rfield(self.hour), rfield(self.day_of_week),
            rfield(self.day_of_month), rfield(self.month_of_year),
        )


class PeriodicTask(object):
    """
    Represents a periodic task.
    This follows the celery.beat.ScheduleEntry class design.
    However it is independent of any celery import, so that any client library can import this module
     and use it to manipulate periodic tasks into a Redis database, without worrying about all the celery imports.
    Should follow the SQLAlchemy DBModel design.
    These are used as delegate from https://github.com/celery/django-celery/blob/master/djcelery/schedulers.py
    """
    name = None
    task = None

    data = None

    args = []
    kwargs = {}
    options = {}

    enabled = True

    # datetime
    last_run_at = None

    total_run_count = 0

    # Follow celery.beat.SchedulerEntry:__init__() signature as much as possible
    def __init__(self, name, task, schedule, key=None, enabled=True, args=(), kwargs=None, options=None,
                 last_run_at=None, total_run_count=None, **extrakwargs):
        """
        :param name: name of the task ( = redis key )
        :param task: taskname ( as in celery : python function name )
        :param schedule: the schedule. maybe also a dict with all schedule content
        :param relative: if the schedule time needs to be relative to the interval ( see celery.schedules )
        :param enabled: whether this task is enabled or not
        :param args: args for the task
        :param kwargs: kwargs for the task
        :param options: options for hte task
        :param last_run_at: lat time the task was run
        :param total_run_count: total number of times the task was run
        :return:
        """

        self.task = task
        self.enabled = enabled

        # Using schedule property conversion
        # logger.warn("Schedule in Task init {s}".format(s=schedule))
        self.schedule = schedule

        self.args = args
        self.kwargs = kwargs or {}
        self.options = options or {}

        self.last_run_at = last_run_at
        self.total_run_count = total_run_count

        self.name = name
        self.key = key if key else self.name
        self.delete_key = 'deleted:' + bytes_to_str(self.key)

        self.running = False

        # storing extra arguments (might be useful to have other args depending on application)
        for elem in extrakwargs.keys():
            setattr(self, elem, extrakwargs[elem])

    @staticmethod
    def get_all_as_dict(rdb, key_prefix):
        """get all of the tasks, for best performance with large amount of tasks, return a generator
        """

        tasks = rdb.keys(key_prefix + '*')
        for task_key in tasks:
            try:
                dct = json.loads(bytes_to_str(rdb.get(task_key)), cls=DateTimeDecoder, encoding=default_encoding)
                # task name should always correspond to the key in redis to avoid
                # issues arising when saving keys - we want to add information to
                # the current key, not create a new key
                yield task_key, dct
            except ValueError:  # handling bad json format by ignoring the task
                logger.warning('ERROR Reading json task at %s', task_key)

    def __repr__(self):
        return '<PeriodicTask ({0} {1}(*{2}, **{3}) options: {4} schedule: {5})>'.format(
            self.name, self.task, self.args,
            self.kwargs, self.options, self.schedule,
        )

    def __unicode__(self):
        fmt = '{0.name}: {0.schedule}'
        return fmt.format(self)

    def get_schedule(self):
        """
        schedule Interval / Crontab -> dict
        :return:
        """
        return vars(self.data)

    def set_schedule(self, schedule):
        """
        schedule dict -> Interval / Crontab if needed
        :return:
        """
        if schedule is None:
            pass
        elif isinstance(schedule, Interval) or isinstance(schedule, Crontab):
            self.data = schedule
        elif isinstance(schedule, celery.schedules.crontab):
            self.data = Crontab(schedule.minute, schedule.hour,
                                schedule.day_of_week, schedule.day_of_month, schedule.month_of_year)
        elif isinstance(schedule, celery.schedules.schedule)\
                or isinstance(schedule, datetime.timedelta):
            self.data = Interval(schedule.seconds)
        else:
            schedule_inst = None
            for s in [Interval, Crontab]:
                try:
                    schedule_inst = s(**schedule)
                except TypeError as typexc:
                    logger.warn("Create schedule failed. {}".format(schedule.__class__))
                    pass

            if schedule_inst is None:
                raise TaskTypeError("Schedule {s} didn't match Crontab or Interval type".format(s=schedule))
            else:
                self.data = schedule_inst

    schedule = property(get_schedule, set_schedule)

    def __iter__(self):
        """
        We iterate on our members a little bit specially
        => data is hidden and schedule is shown instead
        => rdb is hidden
        :return:
        """
        for k, v in vars(self).iteritems():
            if k == 'data':
                yield 'schedule', self.schedule
            else:  # we can expose everything else
                yield k, v
