FROM python:3.8-alpine
WORKDIR /usr/src/app

# Py3.8 is the newest Python officially supported by celery 4.4.x.
# 3.11+ won't import celery 4 (Click/asyncio compat). Keep this image
# pinned if you actually need celery 4 -- the modern example lives in
# ../standalone/.

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app
