#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File is a wrapper for the TOKEN verification.
Correct Token Should be supplied to access any Luna 2 API.

"""
from common.constants import *
from functools import wraps
from flask import abort

def login_required(f):
    @wraps(f)
    def login(**kwargs):
        if not kwargs['token'] == TOKEN:
            abort(401)
        return f(**kwargs)
    return login