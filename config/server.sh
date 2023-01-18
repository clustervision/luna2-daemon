#!/bin/bash

# This File should be called via systemd service to start/stop the Luna 2 Daemon Application.

cd /trinity/local/luna/
# if [[ "$1" = "reload" ]]; then
# 	gunicorn --config /trinity/local/luna/config/gunicorn.py --reload 'luna:api' &
# else
# 	gunicorn --config /trinity/local/luna/config/gunicorn.py 'luna:api' &
# fi  
# nohup gunicorn --config /trinity/local/luna/config/gunicorn.py 'luna:api' >/dev/null 2>&1
# /usr/local/bin/gunicorn --config /trinity/local/luna/config/gunicorn.py 'luna:api' &
gunicorn --config /trinity/local/luna/config/gunicorn.py 'luna:api'
# nohup gunicorn --config config/gunicorn.py luna:api >/dev/null 2>&1