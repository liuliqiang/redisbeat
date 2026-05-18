# Introduction

`redisbeat` is a [Celery Beat Scheduler](http://celery.readthedocs.org/en/latest/userguide/periodic-tasks.html) that stores periodic tasks and their status in a [Redis Datastore](https://redis.io/).

Tasks can be added, removed or modified without restarting celery using `redisbeat`.

And you can add scheduler task dynamically when you need to add scheduled task.


# Features

1. Full-featured celery-beat scheduler.
2. Dynamically add/remove/modify tasks.


# Upgrade notes — READ BEFORE UPGRADING

> **redisbeat persists each schedule entry as a `jsonpickle`-serialized `celery.beat.ScheduleEntry` blob.** When the underlying `jsonpickle`, Python, or Celery version changes, the new code may fail to decode blobs written by the old version. The decode loop in `merge_inplace` has no graceful fallback today, so a single undecodable blob can prevent beat from starting.

**Pre-upgrade ritual (recommended for any non-trivial version jump):**

```bash
# 1. Snapshot first so you can roll back
redis-cli --rdb /tmp/redisbeat.rdb

# 2. Drop the schedule key so the new redisbeat reseeds it on first boot
redis-cli del celery:beat:order_tasks
```

## Static vs dynamic tasks

- **Static tasks (declared in `CELERYBEAT_SCHEDULE`)** — re-encoded with the *current* `jsonpickle` on every beat startup, with `last_run_at` preserved. **They self-heal across upgrades.**
- **Dynamic tasks (added at runtime via `RedisScheduler.add(...)`)** — live only in Redis. If the new code can't decode them, beat won't start, and there is no source-of-truth to rebuild from.

## Risk by upgrade path

| Path | Risk | Reason |
|---|---|---|
| `jsonpickle 3.0.0 → 3.3.0` (same Python) | low | same major, wire format stable |
| `jsonpickle 1.x / 2.x → 3.x` | medium | wire-format drift across major versions; some payloads no longer decode |
| Python 2.7 → Python 3 | **high** | old blobs reference `__builtin__.unicode` etc., absent on Py3 |
| celery 4 → celery 5 | **high** | celery 5 uses `zoneinfo`; old blobs reference `pytz.UTC` |
| standalone Redis → Redis Cluster | n/a | different Redis instance — old data isn't even visible; re-`add()` dynamic tasks manually |

## Recovery if beat refuses to start after an upgrade

```bash
redis-cli del celery:beat:order_tasks
```

Static tasks from `CELERYBEAT_SCHEDULE` repopulate on the next boot. Dynamic tasks are lost — re-`add()` them.


# Installation

`redisbeat` can be easily installed using setuptools or pip.

    # pip install redisbeat

or you can install from source by cloning this repository:

	# git clone https://github.com/liuliqiang/redisbeat.git
	# cd redisbeat
	# python setup.py install

# Docker-compose demo

`redisbeat` provides Docker demos under the `example/` folder, one per supported Redis topology:

- `example/standalone/` — single Redis node, celery 5 (Python 3.11)
- `example/celery4/` — single Redis node, celery 4.x (Python 3.8) for legacy stacks
- `example/cluster/` — 6-node Redis Cluster (3 masters + 3 replicas), see the [Redis Cluster mode](#redis-cluster-mode) section below

To run the standalone demo:

```
# cd redisbeat/example/standalone
# docker-compose up -d
```

After you have compose running, you can easily see it working with following commands:

1. Celery worker logs

    ```
    # docker-compose logs worker
    ```

1. Celery beat logs

    ```
    # docker-compose logs beat
    ```

4. dynamic add the task `sub`

    ```
    # docker exec -it beat python add_task.py
    ```

5. dynamic remove the task `sub`

    ```
    # docker exec -it beat python rem_task.py
    ```

# Running demo locally without Docker

If you want to try locally you can install the requirements from pip, and run it as a python project changing the url of redis from 'redis' to 'localhost' in tasks.py Celery instance and config:

```python
#(...)
app = Celery('tasks', backend='redis://redis:6379',
                broker='redis://redis:6379')

app.conf.update(
    CELERY_REDIS_SCHEDULER_URL = 'redis://redis:6379',
#(...)
```

Commands to start worker and beat:

```
# celery worker -A tasks -l INFO
# celery beat -A tasks -S redisbeat.RedisScheduler -l INFO
```

# Configuration and Usage

Configuration for `redisbeat` is similar to the original celery configuration for beat.
You can configure `redisbeat` as:


```python
# encoding: utf-8

from datetime import timedelta
from celery.schedules import crontab
from celery import Celery

app = Celery('tasks', backend='redis://localhost:6379',
             broker='redis://localhost:6379')

app.conf.update(
    CELERYBEAT_SCHEDULE={
        'perminute': {
            'task': 'tasks.add',
            'schedule': timedelta(seconds=3),
            'args': (1, 1)
        }
    }
)

@app.task
def add(x, y):
    return x + y

@app.task
def sub(x, y):
    return x - y
```

when you want to add a new task dynamically, you can try this code such like in `__main__`:

```python
#!/usr/bin/env python
# encoding: utf-8
from datetime import timedelta
from celery import Celery
from redisbeat.scheduler import RedisScheduler


app = Celery('tasks', backend='redis://localhost:6379',
             broker='redis://localhost:6379')

app.conf.update(
    CELERYBEAT_SCHEDULE={
        'perminute': {
            'task': 'tasks.add',
            'schedule': timedelta(seconds=3),
            'args': (1, 1)
        }
    }
)

@app.task
def add(x, y):
    return x + y

@app.task
def sub(x, y):
    return x - y

if __name__ == "__main__":
    schduler = RedisScheduler(app=app)
    schduler.add(**{
        'name': 'sub-perminute',
        'task': 'tasks.sub',
        'schedule': timedelta(seconds=3),
        'args': (1, 1)
    })
```

It can be easily to add task for two step:

1. Init a `RedisScheduler` object from Celery app
2. Add new tasks by `RedisScheduler` object


Or you can define settings in your celery configuration file similar to other configurations.

```python
CELERY_BEAT_SCHEDULER = 'redisbeat.RedisScheduler'
CELERY_REDIS_SCHEDULER_URL = 'redis://localhost:6379/1'
CELERY_REDIS_SCHEDULER_KEY = 'celery:beat:order_tasks'
CELERYBEAT_SCHEDULE = {
    'perminute': {
        'task': 'tasks.add',
        'schedule': timedelta(seconds=3),
        'args': (1, 1)
    }
}
```

# Redis Cluster mode

If your Redis runs in cluster mode, use the `rediscluster://` URL scheme so redisbeat connects via `redis.cluster.RedisCluster` instead of the standalone client (the latter issues `SELECT`, which Redis Cluster rejects — see issue #43).

```python
CELERY_REDIS_SCHEDULER_URL = "rediscluster://host1:7000,host2:7001,host3:7002"
```

Supported URL forms:

```
rediscluster://host1:port1[,host2:port2,...]
rediscluster://:password@host1:port1[,host2:port2,...]
rediscluster://user:password@host1:port1[,host2:port2,...]
```

Requires `redis-py >= 4.1`. A full docker-compose stack with a 6-node cluster lives at `example/cluster/`:

```
# cd redisbeat/example/cluster
# docker compose up --build
```

### Multiple node support

For running `redisbeat` in multi node deployment, it uses redis lock to prevent same task to be executed mutiple times.

```python
CELERY_REDIS_MULTI_NODE_MODE = True
CELERY_REDIS_SCHEDULER_LOCK_TTL = 30
```

This is an experimental feature, to use `redisbeat` in production env, set `CELERY_REDIS_MULTI_NODE_MODE = False`, `redisbeat` will not use this feature.


