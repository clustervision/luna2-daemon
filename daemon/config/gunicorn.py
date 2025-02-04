#!/usr/bin/env python3

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>

"""
Start Luna 2 Daemon as a service luna2-daemon.service
"""
import luna
# The IP address (typically localhost) and port that the gunicorn WSGI process should listen on
bind = '[::]:7050'
#bind = '0.0.0.0:7050'

# Number of gunicorn workers to spawn. This should typically be 2n+1, where
# n is the number of CPU cores present.
workers = 4

# Number of threads per worker process
# threads = 3

# Timeout (in seconds) for a request to complete
# timeout = 120

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
