# Introduction

`redisbeat` is a [Celery Beat Scheduler](http://celery.readthedocs.org/en/latest/userguide/periodic-tasks.html) that stores periodic tasks and their status in a [Redis Datastore](https://redis.io/).

Tasks can be added, removed or modified without restarting celery using `redisbeat`.

And you can add scheduler task dynamically when you need to add scheduled task.


# Features

1. Full-featured celery-beat scheduler.
2. Dynamically add/remove/modify tasks.


# Installation

`redisbeat` can be easily installed using setuptools or pip.

    # pip install redisbeat

or you can install from source by cloning this repository:

	# git clone https://github.com/yetship/celerybeatredis.git
	# cd celerybeatredis
	# python setup.py install

# Usage

After you have installed `redisbeat`, you can easily start with following steps:

This is a demo for exmaple, you can check the code in `example` directory

1. install dependence(**IMPORTANT**)

    ```
    $ pip install -r requirements.txt
    ```
    
2. start celery worker

    ```
    $ celery worker -A tasks -l info
    ```

3. start the celery beat with `RedisScheduler` as scheduler:

    ```
    $ celery beat -A tasks -S redisbeat.RedisScheduler
    ```

4. dynamic add the task `sub`

    ```
    $ python add_task.py
    ```

5. dynamic remove the task `sub`

    ```
    $ python rem_task.py
    ```

# Configuration

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

### Multiple node support

For running `redisbeat` in multi node deployment, it uses redis lock to prevent same task to be executed mutiple times.

```python
CELERY_REDIS_MULTI_NODE_MODE = True
CELERY_REDIS_SCHEDULER_LOCK_TTL = 30
```

This is an experimental feature, to use `redisbeat` in production env, set `CELERY_REDIS_MULTI_NODE_MODE = False`, `redisbeat` will not use this feature.


