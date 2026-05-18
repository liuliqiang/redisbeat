#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2014 Kong Luoxing

# Licensed under the Apache License, Version 2.0 (the 'License'); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
################################################################
# Copyright 2015-2024 Liqiang Liu

# Licensed under the Apache License, Version 2.0 (the 'License'); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0

import sys
import jsonpickle
from time import mktime
import traceback

from celery.beat import Scheduler
from celery import current_app
from celery.utils.log import get_logger
from redis import StrictRedis
from redis.sentinel import Sentinel
from redis.exceptions import LockError
try:
    import urllib.parse as urlparse
except ImportError:
    import urlparse

try:
    MAXINT = sys.maxint
except AttributeError:
    # python3
    MAXINT = sys.maxsize

from redisbeat.constants import (
    INIT_POLICIES,
    INIT_POLICY_DEFAULT,
    INIT_POLICY_IMMEDIATELY,
    INIT_POLICY_RESET,
    INIT_POLICY_FAST_FORWARD,
    CONFIG_INIT_POLICY,
    BROKER_URL,
    BROKER_KEY,
    BROKER_TRANSPORT_OPTIONS,
    MULTI_NODE_MODE,
    LOCK_TTL,
)


logger = get_logger(__name__)
debug, linfo, error, warning = (logger.debug, logger.info, logger.error,
                                logger.warning)

default_transport_options = {
    "master_name": "mymaster",
}
default_broker_key = "celery:beat:order_tasks"


class EncodeException(Exception):
    pass

class TaskNotExistsException(Exception):
    pass

class Codec(object):
    """
    Codec is used to encode and decode task entry
    The default codec is jsonpickle
    """
    def encode(self, obj):
        encode_obj = jsonpickle.encode(obj)
        if encode_obj is None:
            raise EncodeException("encode obj is None")
        return encode_obj

    def decode(self, obj):
        return jsonpickle.decode(obj)


class RedisScheduler(Scheduler):
    def __init__(self, *args, **kwargs):
        app = kwargs['app']
        self.skip_init = kwargs.get('skip_init', False)

        self.codec = Codec()

        self.key = app.conf.get(BROKER_KEY, default_broker_key)
        self.schedule_init_policy = app.conf.get(CONFIG_INIT_POLICY, INIT_POLICY_DEFAULT)
        if self.schedule_init_policy not in INIT_POLICIES:
            raise ValueError(
                "unexpected init policy '{0}', expected one of {1}".format(
                    self.schedule_init_policy, INIT_POLICIES))
        self.max_interval = 2  # default max interval is 2 seconds
        self.schedule_url = app.conf.get(BROKER_URL, "redis://localhost:6379")
        # using sentinels
        # supports 'sentinel://:pass@host:port/db
        if self.schedule_url.startswith('sentinel://'):
            self.broker_transport_options = app.conf.get(BROKER_TRANSPORT_OPTIONS, default_transport_options)
            self.rdb = self.sentinel_connect(
                self.broker_transport_options['master_name'])
        elif self.schedule_url.startswith('rediscluster://'):
            # Redis Cluster: SELECT is not supported, so any db component in
            # the URL is ignored. Format:
            #   rediscluster://[[user]:password@]host1:port1[,host2:port2,...]
            self.rdb = self.cluster_connect()
        else:
            self.rdb = StrictRedis.from_url(self.schedule_url)
        Scheduler.__init__(self, *args, **kwargs)
        app.add_task = self.add

        self.multi_node = app.conf.get(MULTI_NODE_MODE, False)
        # how long we should hold on to the redis lock in seconds
        if self.multi_node:
            self.lock_ttl = app.conf.get(LOCK_TTL, 30)
            self._lock_acquired = False
            self._lock = self.rdb.lock(
                'celery:beat:task_lock', timeout=self.lock_ttl)
            self._lock_acquired = self._lock.acquire(blocking=False)
        
    def _remove_db(self):
        linfo("remove db now")
        self.rdb.delete(self.key)

    def _when(self, entry, next_run_time):
        return mktime(entry.schedule.now().timetuple()) + (self.adjust(next_run_time) or 0)

    def setup_schedule(self):
        debug("setup schedule, skip_init: %s", self.skip_init)
        if self.skip_init:
            return
        
        # if the tasks in config not exists in db, add it to db
        self.merge_inplace(self.app.conf['CELERYBEAT_SCHEDULE'])

        # init entries
        # entries = [jsonpickle.decode(task) for task in self.rdb.zrange(self.key, 0, -1)]
        entries = self.rdb.zrange(self.key, 0, MAXINT)
        # linfo('Current schedule:\n' + '\n'.join(
            # str('task: ' + entry.task + '; each: ' + repr(entry.schedule))
            # for entry in entries))
        for entry in entries:
            decode_task = self.codec.decode(entry)
            linfo("checking task entry(%s): %s", decode_task.name, decode_task.schedule)
            next_run_interval, new_task = self._calculate_next_run_time_with_init_policy(decode_task)
            next_run_time = self._when(new_task, next_run_interval)

            self.rdb.zrem(self.key, entry)
            self.rdb.zadd(self.key, {self.codec.encode(new_task): next_run_time})
    
    def merge_inplace(self, tasks):
        """Reconcile in-memory schedule config with what's persisted in Redis.

        Strategy:
        - Tasks present in both config and Redis: replace stored payload with the
          one rebuilt from current config (so schedule/args edits take effect),
          but preserve ``last_run_at`` so the init policy can detect missed runs.
        - Tasks new in config: add fresh.
        - Tasks present only in Redis (e.g. added via :meth:`add` at runtime) are
          left alone; we don't have enough information here to decide they are
          stale.
        """
        old_entries = self.rdb.zrangebyscore(self.key, 0, MAXINT, withscores=True)
        old_entries_dict = dict({})
        for task_blob, score in old_entries:
            if not task_blob:
                continue
            debug("ready to load old_entries: %s", task_blob)
            entry = self.codec.decode(task_blob)
            old_entries_dict[entry.name] = (entry, score, task_blob)
        debug("old_entries: %s", old_entries_dict)

        for task_name, task in tasks.items():
            e = self.Entry(**dict(task, name=task_name, app=self.app))
            if task_name in old_entries_dict:
                old_entry, _old_score, old_blob = old_entries_dict[task_name]
                # Preserve last_run_at so init policies can detect missed runs.
                e.last_run_at = old_entry.last_run_at
                # Drop the previous payload; schedule/args may have changed.
                self.rdb.zrem(self.key, old_blob)
            _, next_run_interval = e.is_due()
            next_run_time = self._when(e, next_run_interval)
            linfo("add task entry: %s, next_run_time:%s to db",
                  task_name, next_run_time)
            self.rdb.zadd(self.key, {self.codec.encode(e): next_run_time})

    def _calculate_next_run_time_with_init_policy(self, entry):
        if self.schedule_init_policy == INIT_POLICY_RESET:
            # Pretend the task just ran: next run is one full interval from now.
            entry.last_run_at = entry.default_now()
            _, next_run_time = entry.is_due()
            return next_run_time, entry
        elif self.schedule_init_policy == INIT_POLICY_IMMEDIATELY:
            # Fire every task now and let the post-run advancement take over.
            entry.last_run_at = entry.default_now()
            return 0, entry
        elif self.schedule_init_policy == INIT_POLICY_FAST_FORWARD:
            should_run_now, next_run_time = entry.is_due()
            if not should_run_now:
                return next_run_time, entry
            # Collapse all missed runs into a single immediate run. By setting
            # ``last_run_at`` to one interval ago we guarantee exactly one
            # outstanding run, after which normal cadence resumes.
            run_every = getattr(entry.schedule, 'run_every', None)
            if run_every is not None:
                entry.last_run_at = entry.default_now() - run_every
            return 0, entry
        else:  # INIT_POLICY_DEFAULT
            # Leave ``last_run_at`` untouched; tick() will replay each missed
            # run one interval at a time.
            _, next_run_time = entry.is_due()
            return next_run_time, entry

    def is_due(self, entry):
        return entry.is_due()

    def adjust(self, n, drift=-0.010):
        if n and n > 0:
            return n + drift
        return n

    def add(self, **kwargs):
        e = self.Entry(app=current_app, **kwargs)
        _, next_run_interval = e.is_due()
        next_run_time = self._when(e, next_run_interval)
        self.rdb.zadd(self.key, {self.codec.encode(e): next_run_time})
        return True

    def remove(self, task_key):
        tasks = self.rdb.zrange(self.key, 0, MAXINT) or []
        for idx, task in enumerate(tasks):
            entry = self.codec.decode(task)
            if entry.name == task_key:
                self.rdb.zremrangebyrank(self.key, idx, idx)
                return True
        else:
            return False

    def list(self):
        return [self.codec.decode(entry) for entry in self.rdb.zrange(self.key, 0, MAXINT)]

    def get(self, task_key):
        tasks = self.rdb.zrange(self.key, 0, MAXINT) or []
        for idx, task in enumerate(tasks):
            entry = self.codec.decode(task)
            if entry.name == task_key:
                return entry
        else:
            return None

    def tick(self):
        tasks = self.rdb.zrangebyscore(
            self.key, 0,
            self.adjust(mktime(self.app.now().timetuple()), drift=0.010),
            withscores=True,
        ) or []

        next_times = [self.max_interval, ]

        for task, _ in tasks:
            entry = self.codec.decode(task)
            is_due, next_run_time = self.is_due(entry)

            next_times.append(next_run_time)
            if is_due:
                next_entry = self.reserve(entry)
                try:
                    linfo("add task entry: %s to publisher", entry.name)
                    result = self.apply_async(entry)
                except Exception as exc:
                    error('Message Error: %s\n%s',
                          exc, traceback.format_stack(), exc_info=True)
                else:
                    debug('%s sent. id->%s', entry.task, result)
                self.rdb.zrem(self.key, task)
                self.rdb.zadd(self.key, {self.codec.encode(next_entry): self._when(next_entry, next_run_time) or 0})

        next_task = self.rdb.zrangebyscore(self.key, 0, MAXINT, withscores=True, num=1, start=0)
        if not next_task:
            linfo("no next task found")
            return min(next_times)
        entry = self.codec.decode(next_task[0][0])
        next_times.append(self.is_due(entry)[1])

        return min(next_times)

    def close(self):
        # it would be call after cycle end
        if self.multi_node:
            try:
                self._lock.release()
            except LockError:
                pass
        self.sync()

    def cluster_connect(self):
        """Connect to a Redis Cluster.

        Supported URL format::

            rediscluster://[[user]:password@]host1:port1[,host2:port2,...]

        Notes:
        - Cluster only supports DB 0; any path component in the URL is ignored.
        - Requires redis-py >= 4.1, which ships ``redis.cluster.RedisCluster``.
        """
        try:
            from redis.cluster import RedisCluster, ClusterNode
        except ImportError as exc:
            raise ImportError(
                "Redis Cluster support requires redis-py>=4.1; "
                "install with `pip install 'redis>=4.1'`."
            )

        url = urlparse.urlparse(self.schedule_url)

        if '@' in url.netloc:
            auth, hostspec = url.netloc.split('@', 1)
        else:
            auth = None
            hostspec = url.netloc

        username = None
        password = None
        if auth:
            if ':' in auth:
                username, password = auth.split(':', 1)
                username = username or None
                password = password or None
            else:
                password = auth

        def _parse_host(s):
            if ':' in s:
                host, port = s.rsplit(':', 1)
                port = int(port)
            else:
                host = s
                port = 6379
            return host, port

        startup_nodes = [
            ClusterNode(host, port)
            for host, port in (_parse_host(s) for s in hostspec.split(',') if s)
        ]
        if not startup_nodes:
            raise ValueError(
                "rediscluster URL must include at least one host: %s"
                % self.schedule_url)

        kwargs = {}
        if username is not None:
            kwargs['username'] = username
        if password is not None:
            kwargs['password'] = password

        return RedisCluster(startup_nodes=startup_nodes, **kwargs)

    def sentinel_connect(self, master_name):
        url = urlparse.urlparse(self.schedule_url)

        def parse_host(s):
            if ':' in s:
                host, port = s.split(':', 1)
                port = int(port)
            else:
                host = s
                port = 26379

            return host, port

        if '@' in url.netloc:
            auth, hostspec = url.netloc.split('@', 1)
        else:
            auth = None
            hostspec = url.netloc

        if auth and ':' in auth:
            _, password = auth.split(':', 1)
        else:
            password = None
        path = url.path
        if path.startswith('/'):
            path = path[1:]
        hosts = [parse_host(s) for s in hostspec.split(',')]
        sentinel = Sentinel(hosts, password=password, db=path)
        master = sentinel.master_for(master_name)
        return master

    @property
    def info(self):
        # return infomation about Schedule
        return '    . db -> {self.schedule_url}, key -> {self.key}'.format(self=self)