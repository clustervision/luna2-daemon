#!/bin/bash

cd /luna2-daemon/
nohup /usr/local/bin/python3.10 luna.py 2>&1 > /dev/null &