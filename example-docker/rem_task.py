#!/usr/bin/env python
# encoding: utf-8
from redisbeat.scheduler import RedisScheduler

from tasks import app


if __name__ == "__main__":
    schduler = RedisScheduler(app=app)
    result = schduler.remove('sub-perminute')
    print("rem result: ", result)
