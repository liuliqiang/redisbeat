# Introduction

Using redis as celery scheduler task storage and beat by reading task from redis.

So you can add or remove task dynamic while celery beat is runing and no need to restart celery. And you can add scheduler task dynamic when you need to add schedule task.

# Features

1. Full-featured celery-beat scheduler
2. Dynamically add/remove/modify tasks
3. Original celery scheduler config, no need to change scheduler configs
4. Support multiple instance by Active-Standby model

# Installation

Install redisbeat is so easy, you can using setuptools or pip.

Simplily, you can just instlal by pip package tool:

    # pip install redisbeat

or maybe you can use source install by clone codes:

	# git clone https://github.com/luke0922/celerybeatredis.git
	# cd celerybeatredis
	# python setup.py install

# Usage 

After you install celerybeatredis, you can jsut using it in celery by beat easily:

    # celery -A tasks beat -s redisbeat.RedisScheduler

# Configuration

Config by using redis beat is the same to origin celery config, as an schedule beat, you can config as following:

```
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
```
