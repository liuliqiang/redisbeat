
.PHONY: worker beat

worker:
	celery worker -A tasks -l INFO

beat:
	celery beat -A tasks -S redisbeat.RedisScheduler -l DEBUG	

add_task:
	python add_task.py

rm_task:
	python rem_task.py