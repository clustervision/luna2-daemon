#!/usr/bin/env python3

"""
Start luna daemon
"""
import luna
# The IP address (typically localhost) and port that the Netbox WSGI process should listen on
bind = '0.0.0.0:7050'

# Number of gunicorn workers to spawn. This should typically be 2n+1, where
# n is the number of CPU cores present.
# workers = 4
workers = 1

# Number of threads per worker process
# threads = 3

# Timeout (in seconds) for a request to complete
# timeout = 120

# The maximum number of requests a worker can handle before being respawned
# max_requests = 5000
# max_requests_jitter = 500

reload_engine = 'auto'
on_starting = luna.on_starting
on_exit = luna.on_exit
# on_reload = luna.on_reload

