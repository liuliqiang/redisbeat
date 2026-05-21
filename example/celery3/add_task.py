from datetime import timedelta
import logging
import sys

from redisbeat.scheduler import RedisScheduler

from tasks import app


root = logging.getLogger()
root.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
root.addHandler(handler)


if __name__ == "__main__":
    scheduler = RedisScheduler(app=app, skip_init=True)
    scheduler.add(**{
        'name': 'sub-every-3-seconds',
        'task': 'tasks.sub',
        'schedule': timedelta(seconds=3),
        'args': (1, 1),
    })
