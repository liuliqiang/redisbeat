from datetime import timedelta
redis_scheduler_url = "redis://localhost:6379/0"
broker_url = "redis://localhost:6379/0"
redis_scheduler_key_prefix = 'tasks:meta:'
beat_schedule = {
    'add-every-3-seconds': {
        'task': 'tasks.add',
        'schedule': timedelta(seconds=3),
        'args': (16, 16)
    },
}
