# -*- coding: utf-8 -*-
# Copyright 2014 Kong Luoxing

# Licensed under the Apache License, Version 2.0 (the 'License'); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0

import sys
from redis.client import StrictRedis
from celery import current_app
from celery.utils.log import get_logger

ADD_ENTRY_ERROR = """\

Couldn't add entry %r to redis schedule: %r. Contents: %r
"""

logger = get_logger(__name__)

PY3 = sys.version_info >= (3, 0)

default_encoding = 'utf-8'
def bytes_to_str(s):
    if PY3:
        if isinstance(s, bytes):
            return s.decode(default_encoding)
    return s

def str_to_bytes(s):
    if PY3:
        if isinstance(s, str):
            return s.encode(default_encoding)
    return s
