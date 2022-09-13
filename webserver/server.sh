#!/bin/bash

cd /luna2-daemon/webserver/
nohup /usr/local/bin/python3.10 server.py 2>&1 > /dev/null &