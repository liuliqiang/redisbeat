# celerybeat-redis

It's modified from celerybeat-mongo (https://github.com/zakird/celerybeat-mongo)

See Changelog in [CHANGES.md](./CHANGES.md)

This is a Celery Beat Scheduler (http://celery.readthedocs.org/en/latest/userguide/periodic-tasks.html)
that stores both the schedules themselves and their status
information in a backend Redis database.

# Features

1. Full-featured celery-beat scheduler
2. Dynamically add/remove/modify tasks
3. Support multiple instance by Active-Standby model

# Installation

It can be installed by
installing the celerybeat-redis Python egg:

    # pip install celerybeat-redis

And specifying the scheduler when running Celery Beat, e.g.

    $ celery beat -S celerybeatredis.schedulers.RedisScheduler

# Configuration

Settings for the scheduler are defined in your celery configuration file
similar to how other aspects of Celery are configured

    CELERY_REDIS_SCHEDULER_URL = "redis://localhost:6379/1"
    CELERY_REDIS_SCHEDULER_KEY_PREFIX = 'tasks:meta:'

You mush make these two value configured. `CELERY_REDIS_SCHEDULER_URL` is used
to store tasks. `CELERY_REDIS_SCHEDULER_KEY_PREFIX` is used to generate keys in
redis. The key was like

    tasks:meta:task-name-here
    tasks:meta:test-fib-every-3s

# Quickstart

After installed and configure the needs by above, you can make a try with test, cd to test directory, start a worker by:

    $ celery worker -A tasks -l info

then start the beat by:

    $ celery beat -S celerybeatredis.schedulers.RedisScheduler

celerybeat-redis will load the entry from celeryconfig.py

# Detailed Configuration

There was two ways to add a period task:

## Add in celeryconfig.py

Celery provide a `CELERYBEAT_SCHEDULE` entry in config file, when
celerybeat-redis starts with such a config, it will load tasks to redis, create
them as a celerybeat-redis task.

It's perfect for quick test

## Manaully add to Redis

You can create task by insert specify data to redis, according to following described:

Schedules can be manipulated in the Redis database through
direct database manipulation. There exist two types of schedules,
interval and crontab.

```json
{
    "name" : "interval test schedule",
    "task" : "task-name-goes-here",
    "enabled" : true,
    "interval" : {
        "every" : 5,
        "period" : "minutes"
    },
    "args" : [
        "param1",
        "param2"
    ],
    "kwargs" : {
        "max_targets" : 100
    },
    "total_run_count" : 5,
    "last_run_at" : {
        "__type__": "datetime",
        "year": 2014,
        "month": 8,
        "day": 30,
        "hour": 8,
        "minute": 10,
        "second": 6,
        "microsecond": 667
    }
}
```

The example from Celery User Guide::Periodic Tasks.
```python
CELERYBEAT_SCHEDULE = {
    'interval-test-schedule': {
        'task': 'tasks.add',
        'schedule': timedelta(seconds=30),
        'args': (param1, param2)
    }
}
```

Becomes the following::
```json
{
    "name" : "interval test schedule",
    "task" : "task.add",
    "enabled" : true,
    "interval" : {
        "every" : 30,
        "period" : "seconds",
    },
    "args" : [
        "param1",
        "param2"
    ],
    "kwargs" : {
        "max_targets" : 100
    },
    "total_run_count": 5,
    "last_run_at" : {
        "__type__": "datetime",
        "year": 2014,
        "month": 8,
        "day": 30,
        "hour": 8,
        "minute": 10,
        "second": 6,
        "microsecond": 667
    }
}
```

The following fields are required: name, task, crontab || interval,
enabled when defining new tasks.
`total_run_count` and `last_run_at` are maintained by the
scheduler and should not be externally manipulated.

The example from Celery User Guide::Periodic Tasks.
(see: http://docs.celeryproject.org/en/latest/userguide/periodic-tasks.html#crontab-schedules)

```python
CELERYBEAT_SCHEDULE = {
    # Executes every Monday morning at 7:30 A.M
    'add-every-monday-morning': {
        'task': 'tasks.add',
        'schedule': crontab(hour=7, minute=30, day_of_week=1),
        'args': (16, 16),
    },
}
```

Becomes:

```json
{
    "name" : "add-every-monday-morning",
    "task" : "tasks.add",
    "enabled" : true,
    "crontab" : {
        "minute" : "30",
        "hour" : "7",
        "day_of_week" : "1",
        "day_of_month" : "*",
        "month_of_year" : "*"
    },
    "args" : [
        "16",
        "16"
    ],
    "kwargs" : {},
    "total_run_count" : 1,
    "last_run_at" : {
        "__type__": "datetime",
        "year": 2014,
        "month": 8,
        "day": 30,
        "hour": 8,
        "minute": 10,
        "second": 6,
        "microsecond": 667
    }
}
```

# Deploy multiple nodes

Original celery beat doesn't support multiple node deployment, multiple beat
will send multiple tasks and make worker duplicate execution, celerybeat-redis
use a redis lock to deal with it. Only one node running at a time, other nodes
keep tick with minimal task interval, if this node down, when other node
ticking, it will acquire the lock and continue to run.

WARNING: this is an experiment feature, need more test, not production ready at
this time.
