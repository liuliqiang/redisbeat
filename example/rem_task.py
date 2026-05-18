#!/usr/bin/env python
# encoding: utf-8
from redisbeat.scheduler import RedisScheduler

from tasks import app


if __name__ == "__main__":
    schduler = RedisScheduler(app=app, skip_init=True)
    result = schduler.remove('sub-every-3-seconds')
    print("rem result: ", result)
