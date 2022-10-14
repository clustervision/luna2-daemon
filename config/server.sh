#!/bin/bash

# This File should be called via systemd service to start/stop the Luna 2 Daemon Application.
# INI Check; Sanity Checks

cd /trinity/local/luna/
# nohup /usr/local/bin/python3.10 luna.py 2>&1 > /dev/null &
gunicorn -w 4 -b 0.0.0.0:7050 --log-file ./log/gunicorn.log --log-level INFO --access-logfile ./log/gunicorn-access.log --error-logfile ./log/gunicorn-error.log 'luna:api' &
# nohup gunicorn -w 4 -b 0.0.0.0:7050 'luna:api' &