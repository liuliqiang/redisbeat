# Copyright 2014 Kong Luoxing

# Licensed under the Apache License, Version 2.0 (the 'License'); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
import datetime
from copy import deepcopy
from redis import StrictRedis

try:
    import simplejson as json
except ImportError:
    import json

from .exceptions import ValidationError
from .decoder import DateTimeDecoder, DateTimeEncoder
from .globals import logger


class Interval(object):

    def __init__(self, every, period='seconds'):
        self.every = every
        # could be seconds minutes hours
        self.period = period

    # def schedule(self, celery_schedules):
    #     return celery_schedules.schedule(datetime.timedelta(**{self.period: self.every}))

    @property
    def period_singular(self):
        return self.period[:-1]

    def __unicode__(self):
        if self.every == 1:
            return 'every {0.period_singular}'.format(self)
        return 'every {0.every} {0.period}'.format(self)

    # @classmethod
    # def fromdict(cls, d):
    #     try:
    #         return cls(d['every'], d.get('period', None))
    #     except ValueError as exc:
    #         raise  # not correct json


class Crontab(object):

        def __init__(self, minute, hour, day_of_week, day_of_month, month_of_year):
            self.minute = minute
            self.hour = hour
            self.day_of_week = day_of_week
            self.day_of_month = day_of_month
            self.month_of_year = month_of_year

        # def schedule(self, celery_schedules):
        #     return celery_schedules.crontab(minute=self.minute,
        #                                     hour=self.hour,
        #                                     day_of_week=self.day_of_week,
        #                                     day_of_month=self.day_of_month,
        #                                     month_of_year=self.month_of_year)

        def __unicode__(self):
            rfield = lambda f: f and str(f).replace(' ', '') or '*'
            return '{0} {1} {2} {3} {4} (m/h/d/dM/MY)'.format(
                rfield(self.minute), rfield(self.hour), rfield(self.day_of_week),
                rfield(self.day_of_month), rfield(self.month_of_year),
            )

        # @classmethod
        # def fromdict(cls, d):
        #     try :
        #         return cls(d['minute'], d['hour'], d['day_of_week'], d['day_of_month'], d['month_of_year'])
        #     except ValueError as exc:
        #         raise  # not correct json


class PeriodicTask(object):
    """
    Represents a periodic task.
    This follows the celery.beat.ScheduleEntry class design.
    However it is independent of any celery import, so that any client library can import this module
    and use it to manipulate periodic tasks into a Redis database, without worrying about all the celery imports.
    """
    name = None
    task = None

    type_ = None

    data = None

    args = []
    kwargs = {}
    options = {}

    # datetime
    expires = None
    enabled = True

    # datetime
    last_run_at = None

    total_run_count = 0

    date_changed = None
    description = None

    no_changes = False

    #TODO : match with celery.beat.SchedulerEntry:__init__() signature
    def __init__(self, scheduler_url, name, task, schedule, enabled=True, args=(), kwargs=None, options=None,
                 last_run_at=None, total_run_count=None, **extrakwargs):
        # TODO : get rid of schduler_url if possible
        """

        :param scheduler_url: the URL of the redic DB where to find the schedule
        :param name: name of the task (pretty long one)
        :param task: taskname ( as in celery : python function name )
        :param schedule: the schedule. maybe also a dict with all schedule content
        :param relative: if the schedule time needs to be relative to the interval ( see celery.schedules )
        :param key: the key of this task
        :param queue: the queue where to send this task (should be in options)
        :param enabled: whether this task is enabled or not
        :param args: args for hte task
        :param kwargs: kwargs for the task
        :param options: options for hte task
        :param last_run_at: lat time the task was run
        :param total_run_count: total number of times the task was run
        :return:
        """

        self.task = task
        self.enabled = enabled

        # Using schedule property conversion
        logger.warn("Schedule in Task init {s}".format(s=schedule))
        self.schedule = schedule

        self.args = args
        self.kwargs = kwargs or {}
        self.options = options or {}

        self.last_run_at = last_run_at
        self.total_run_count = total_run_count

        self.name = name
        self.rdb = StrictRedis.from_url(scheduler_url)

        # storing extra arguments (might be useful to have other args depending on application)
        for elem in extrakwargs.keys():
            setattr(self, elem, extrakwargs[elem])



    @staticmethod
    def get_all_as_dict(scheduler_url, key_prefix):
        """get all of the tasks, for best performance with large amount of tasks, return a generator
        """
        rdb = StrictRedis.from_url(scheduler_url)
        tasks = rdb.keys(key_prefix + '*')
        for task_key in tasks:
            try:
                dct = json.loads(rdb.get(task_key), cls=DateTimeDecoder)
                # task name should always correspond to the key in redis to avoid
                # issues arising when saving keys - we want to add information to
                # the current key, not create a new key
                #dct['key'] = task_key  # TODO : maybe we can get rid of this ?
                yield task_key, dct
            except json.JSONDecodeError:  # handling bad json format by ignoring the task
                logger.warning('ERROR Reading json task at %s', task_key)

    def _next_instance(self, last_run_at):
        self.last_run_at = last_run_at
        self.total_run_count += 1
        """Return a new instance of the same class, but with
        its date and count fields updated."""
        return self.__class__(**dict(
            self,
            last_run_at=last_run_at,
            total_run_count=self.total_run_count + 1,
        ))
    __next__ = next = _next_instance  # for 2to3

    def delete(self):
        self.rdb.delete(self.name)

    def save(self, key):
        # must do a deepcopy using our custom iterator to choose what to save (matching external view)
        self_dict = deepcopy({k: v for k, v in iter(self)})
        self.rdb.set(key, json.dumps(self_dict, cls=DateTimeEncoder))

    # def clean(self):
    #     """validation to ensure that you have a schedule"""
    #     if not (self.schedule):
    #         msg = 'Must define a schedule.'
    #         raise ValidationError(msg)

    def update(self, other):
        """Update values from another task.

        Does only update "editable" fields (task, schedule, args, kwargs,
        options).

        """
        self.__dict__.update({'task': other.task, 'schedule': other.schedule,
                              'args': other.args, 'kwargs': other.kwargs,
                              'options': other.options})

    # @staticmethod
    # def from_dict(d, scheduler_url):
    #     """
    #     build PeriodicTask instance from dict
    #     :param d: dict
    #     :return: PeriodicTask instance
    #     """
    #     # TODO : get rid of this, calling the constructor with **d should be enough
    #     task = PeriodicTask(scheduler_url, d['name'], d['task'], d['schedule'], d['key'])
    #     for elem in d:
    #         if elem not in ('schedule'):
    #             setattr(task, elem, d[elem])
    #     return task
    #
    # def inject_celery(self, celery_schedules):
    #         return self.schedule.schedule(celery_schedules)

    def __repr__(self):
        return '<PeriodicTask ({0} {1}(*{2}, **{3}) {{4}})>'.format(
            self.name, self.task, self.args,
            self.kwargs, self.schedule,
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
        if isinstance(schedule, Interval) or isinstance(schedule, Crontab):
            self.data = schedule
        else:
            schedule_inst = None
            for s in [Interval, Crontab]:
                try:
                    schedule_inst = s(**schedule)
                except TypeError as typexc:
                    pass

            if schedule_inst is None:
                raise Exception(logger.warn("Schedule {s} didn't match Crontab or Interval type".format(s=schedule)))
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
            elif not k in ['rdb']:  # list the keys we don't want to expose
                yield k, v