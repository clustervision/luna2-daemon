#!/bin/bash

# This File should be called via systemd service to start/stop the Luna 2 Daemon Application.

cd /trinity/local/luna/
nohup /usr/local/bin/python3.10 luna.py 2>&1 > /dev/null &
# gunicorn -w 4 -b 0.0.0.0:7050 'luna:api' &