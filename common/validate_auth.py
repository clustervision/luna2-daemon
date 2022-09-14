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