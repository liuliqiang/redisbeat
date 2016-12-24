# Introduction

Using redis as celery scheduler task storage and beat by reading task from redis.

So you can add or remove task dynamic while celery beat is runing and no need to restart celery. And you can add scheduler task dynamic when you need to add schedule task.


# Features

1. Full-featured celery-beat scheduler
2. Dynamically add/remove/modify tasks


# Installation

Install redisbeat is so easy, you can using setuptools or pip.

Simplily, you can just instlal by pip package tool:

    # pip install redisbeat

or maybe you can use source install by clone codes:

	# git clone https://github.com/yetship/celerybeatredis.git
	# cd celerybeatredis
	# python setup.py install

# Usage

After you install celerybeatredis, you can jsut using it in celery by beat easily:

```bash
# celery -A tasks beat -s redisbeat.RedisScheduler
```

# Configuration

Config by using redis beat is the same to origin celery config, as an schedule beat, you can config as following:

```python
#encoding: utf-8
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

when you want to add a new task dynamic, you can try this code such like in `__main__`:

```
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


