.PHONY: worker beat add_task rm_task

# celery 4 CLI: `celery worker -A tasks ...`
# (celery 5 removed this form -- see ../celery5/Makefile for the new
# `celery -A tasks worker ...` order.)

worker:
	celery worker -A tasks -l INFO

beat:
	celery beat -A tasks -S redisbeat.RedisScheduler -l DEBUG

add_task:
	python add_task.py

rm_task:
	python rem_task.py
