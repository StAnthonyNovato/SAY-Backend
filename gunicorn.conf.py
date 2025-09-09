import multiprocessing
import os
import logging
from gunicorn.glogging import Logger
# Gunicorn config for Flask app

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
accesslog = "-"  # log to stdout
errorlog = "-"   # log to stdout
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")
proc_name = "say_backend_gunicorn"

logger_class = "gunicorn.glogging.Logger"


def post_fork(server, worker):
    # Optionally, you can add custom logic here
    server.log.info(f"Worker spawned (pid: {worker.pid})")

# pass in worker ID to worker

access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s "%({X-Forwarded-For}i)s" "%({X-Request-ID}i)s" "%({X-Correlation-ID}i)s" "%({X-Cache}o)s" "%({Worker-ID}i)s"'