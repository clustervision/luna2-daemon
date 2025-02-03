#!/usr/bin/env python3

"""
Start Luna 2 Daemon as a service luna2-daemon.service
"""
import luna
# The IP address (typically localhost) and port that the gunicorn WSGI process should listen on
bind = '0.0.0.0:7050'

# Number of gunicorn workers to spawn. This should typically be 2n+1, where
# n is the number of CPU cores present.
workers = 4

# Number of threads per worker process
# threads = 3

# Timeout (in seconds) for a request to complete
timeout = 600

# The maximum number of requests a worker can handle before being spawned
# max_requests = 5000
# max_requests_jitter = 500

reload_engine = 'auto'

#### Automated Process ####
on_starting = luna.on_starting      ## Called when service starts
on_exit = luna.on_exit              ## Called when service exits
on_reload = luna.on_reload          ## Called when service reload
worker_abort = luna.worker_abort    ## Called when a worker is killed
#### Automated Process ####

certfile = "/trinity/local/etc/ssl/office-controller1.cluster.crt"
keyfile = "/trinity/local/etc/ssl/office-controller1.cluster.key"
cert_reqs = 0
