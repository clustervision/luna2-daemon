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
#threads = 3

# Timeout (in seconds) for a request to complete
#timeout = 120

# The maximum number of requests a worker can handle before being respawned
#max_requests = 5000
#max_requests_jitter = 500

# reload_engine = 'auto'
# on_starting = luna.on_starting
# on_reload = luna.on_reload
"""
TODO: add docs
"""
#def on_reload(server):
    # pprint(vars(server))
    # LOGGER.info(vars(server))
   # print('Templates Check On Start')
    # LOGGER.info('Templates Check On Start')
   # return True

# on_starting = luna.on_starting
# def on_starting(server):
    # print('Templates Check On Start')

# def on_reload(server):
#     """
#      Do something on reload
#     """
#     print("Server has reloaded")
# logfile = '/trinity/local/luna/log/luna2-daemon.log'
# loglevel = 'debug'
# accesslogfile = '/trinity/local/luna/log/gunicorn-access.log'
# errorlogfile = '/trinity/local/luna/log/gunicorn-error.log'
