from redisbeat.scheduler import RedisScheduler

from tasks import app


if __name__ == "__main__":
    scheduler = RedisScheduler(app=app, skip_init=True)
    result = scheduler.remove('sub-every-3-seconds')
    print("rem result: ", result)
