import os
import multiprocessing

# Server socket
bind = "0.0.0.0:8000"

# Worker processes - optimized for production
cpu_count = multiprocessing.cpu_count()
workers = min(cpu_count * 2 + 1, 8)  # Cap at 8 workers to avoid memory issues
worker_class = "uvicorn.workers.UvicornWorker"

# Worker lifecycle
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
preload_app = True

# Timeouts
timeout = 300
keepalive = 2
graceful_timeout = 30

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"

# Process naming
proc_name = "wizetale-api"

# Memory management
max_requests_jitter = 50
worker_tmp_dir = "/dev/shm"  # Use RAM for temporary files 