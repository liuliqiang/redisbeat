from celery import Celery
import time
app = Celery('tasks')

@app.task
def add(x, y):
    time.sleep(3)
    return x + y
