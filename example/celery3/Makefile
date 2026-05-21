.PHONY: worker beat add_task rm_task

# celery 3 CLI: `celery worker -A tasks ...`
# (Identical to celery 4; celery 5 reordered to `celery -A tasks worker`.)

worker:
	celery worker -A tasks -l INFO

beat:
	celery beat -A tasks -S redisbeat.RedisScheduler -l DEBUG

add_task:
	python add_task.py

rm_task:
	python rem_task.py
