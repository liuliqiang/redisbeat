
.PHONY: worker beat

worker:
	celery -A tasks worker -l INFO

beat:
	celery -A tasks beat -S redisbeat.RedisScheduler -l DEBUG

add_task:
	python add_task.py

rm_task:
	python rem_task.py