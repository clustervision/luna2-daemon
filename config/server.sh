#!/bin/bash

# This File should be called via systemd service to start/stop the Luna 2 Daemon Application.

cd /luna2-daemon/
nohup /usr/local/bin/python3.10 luna.py 2>&1 > /dev/null &