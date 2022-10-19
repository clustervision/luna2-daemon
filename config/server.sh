#!/bin/bash

# This File should be called via systemd service to start/stop the Luna 2 Daemon Application.

cd /trinity/local/luna/
nohup gunicorn --config /trinity/local/luna/config/server.py 'luna:api' &