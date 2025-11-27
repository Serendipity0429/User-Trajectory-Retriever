# Gunicorn config file
# For more options, see:
# https://docs.gunicorn.org/en/stable/settings.html
from dotenv import load_dotenv
import os
import multiprocessing
load_dotenv()

# The address to bind to.
# Can be overridden by setting the GUNICORN_BIND_ADDRESS environment variable.
bind = os.getenv("GUNICORN_BIND_ADDRESS", "0.0.0.0:8000")

# The number of worker processes.
# A common recommendation is 2 * cpu_cores + 1
workers = multiprocessing.cpu_count() * 2

# The type of worker to use.
worker_class = "sync"

# Log to stdout and stderr
accesslog = "-"
errorlog = "-"