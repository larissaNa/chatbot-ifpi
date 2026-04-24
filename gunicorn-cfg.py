# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os

bind = f"0.0.0.0:{os.getenv('PORT', '5005')}"
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
accesslog = '-'
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
capture_output = True
enable_stdio_inheritance = True
timeout = int(os.getenv("GUNICORN_TIMEOUT", "300"))
