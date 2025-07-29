import multiprocessing
import os

# Gunicorn config for Flask app

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
accesslog = "-"  # log to stdout
errorlog = "-"   # log to stdout
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")
proc_name = "say_backend_gunicorn"

def post_fork(server, worker):
    # Optionally, you can add custom logic here
    server.log.info(f"Worker spawned (pid: {worker.pid})")

# pass in worker ID to worker
