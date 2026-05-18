#!/usr/bin/env python
# encoding: utf-8
"""Unit tests for Redis Cluster connection support.

These tests do NOT require a live Redis Cluster -- we mock
``redis.cluster.RedisCluster`` and only assert that ``RedisScheduler``
parses the ``rediscluster://`` URL into the right startup nodes / auth
arguments and dispatches to the cluster client.
"""
import unittest
from unittest.mock import patch, MagicMock

from celery import Celery

from redisbeat import RedisScheduler


class TestRedisClusterConnect(unittest.TestCase):
    def _build_app(self, url):
        app = Celery('tasks')
        app.conf.update(CELERY_REDIS_SCHEDULER_URL=url)
        return app

    def _patched_scheduler(self, url):
        """Return ``(scheduler, RedisCluster mock, ClusterNode mock)``.

        ``skip_init=True`` prevents ``setup_schedule`` from touching the
        (mocked) connection, so we can inspect how the URL was parsed.
        """
        app = self._build_app(url)
        with patch('redis.cluster.RedisCluster') as mock_rc, \
                patch('redis.cluster.ClusterNode') as mock_cn:
            mock_cn.side_effect = lambda host, port: ('node', host, port)
            mock_rc.return_value = MagicMock(name='RedisClusterInstance')
            scheduler = RedisScheduler(app=app, skip_init=True)
            return scheduler, mock_rc, mock_cn

    def test_single_node_url(self):
        scheduler, mock_rc, mock_cn = self._patched_scheduler(
            'rediscluster://localhost:7000')

        mock_cn.assert_called_once_with('localhost', 7000)
        mock_rc.assert_called_once_with(
            startup_nodes=[('node', 'localhost', 7000)])
        self.assertIs(scheduler.rdb, mock_rc.return_value)

    def test_multiple_node_url(self):
        _, mock_rc, mock_cn = self._patched_scheduler(
            'rediscluster://host1:7000,host2:7001,host3:7002')

        self.assertEqual(mock_cn.call_args_list, [
            (('host1', 7000), {}),
            (('host2', 7001), {}),
            (('host3', 7002), {}),
        ])
        startup_nodes = mock_rc.call_args.kwargs['startup_nodes']
        self.assertEqual(len(startup_nodes), 3)

    def test_password_only_auth(self):
        _, mock_rc, _ = self._patched_scheduler(
            'rediscluster://:secret@host1:7000')

        kwargs = mock_rc.call_args.kwargs
        self.assertEqual(kwargs.get('password'), 'secret')
        self.assertNotIn('username', kwargs)

    def test_user_and_password_auth(self):
        _, mock_rc, _ = self._patched_scheduler(
            'rediscluster://alice:secret@host1:7000,host2:7001')

        kwargs = mock_rc.call_args.kwargs
        self.assertEqual(kwargs.get('username'), 'alice')
        self.assertEqual(kwargs.get('password'), 'secret')

    def test_default_port_when_missing(self):
        _, _, mock_cn = self._patched_scheduler(
            'rediscluster://host1,host2:7001')

        # First host: default 6379. Second host: explicit 7001.
        self.assertEqual(mock_cn.call_args_list, [
            (('host1', 6379), {}),
            (('host2', 7001), {}),
        ])

    def test_db_path_is_ignored(self):
        # Cluster only supports DB 0; any path component must not surface as
        # a SELECT / db kwarg.
        _, mock_rc, _ = self._patched_scheduler(
            'rediscluster://host1:7000/0')

        kwargs = mock_rc.call_args.kwargs
        self.assertNotIn('db', kwargs)

    def test_empty_hostspec_raises(self):
        app = self._build_app('rediscluster://')
        with patch('redis.cluster.RedisCluster'), \
                patch('redis.cluster.ClusterNode'):
            with self.assertRaises(ValueError):
                RedisScheduler(app=app, skip_init=True)

    def test_non_cluster_url_still_uses_strict_redis(self):
        """Regression guard: plain ``redis://`` URLs must not hit the cluster
        path even when redis-py exposes ``RedisCluster``."""
        app = self._build_app('redis://localhost:6379')
        with patch('redis.cluster.RedisCluster') as mock_rc, \
                patch('redisbeat.scheduler.StrictRedis') as mock_strict:
            RedisScheduler(app=app, skip_init=True)
            mock_strict.from_url.assert_called_once_with('redis://localhost:6379')
            mock_rc.assert_not_called()


if __name__ == '__main__':
    unittest.main()
