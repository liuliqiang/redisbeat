from datetime import timedelta
CELERY_REDIS_SCHEDULER_URL = "redis://localhost:6379/0"
BROKER_URL = "redis://localhost:6379/0"
CELERY_REDIS_SCHEDULER_KEY_PREFIX = 'tasks:meta:'
CELERYBEAT_SCHEDULE = {
    'add-every-3-seconds': {
        'task': 'tasks.add',
        'schedule': timedelta(seconds=3),
        'args': (16, 16)
    },
}
