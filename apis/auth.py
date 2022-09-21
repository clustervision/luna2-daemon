#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File is use for authentication purpose.

"""
import jwt
import datetime

from common.constants import *
from flask import Blueprint, request, json
from utils.log import *
from utils.database.database import *
from werkzeug.security import generate_password_hash,check_password_hash

logger = Log.get_logger()
auth_blueprint = Blueprint('auth', __name__)


"""
/token will receive JSON dict of username and password.
Valdate from luna.conf and generate a token with JWT
"""
@auth_blueprint.route("/token", methods=['POST'])
def token():
    auth = request.get_json(force=True)
    if not auth or not auth["username"] or not auth["password"]:
        logger.error("Login Required")
        response = {"message" : "Login Required"}
        code = 401
    if USERNAME != auth["username"]:
        logger.warning("Incorrect Username {}".format(auth["username"]))
        response = {"message" : "Incorrect Username {}".format(auth["username"])}
        code = 401
    else:
        if PASSWORD != auth["password"]:
            logger.warning("Incorrect Password {}".format(auth["password"]))
            response = {"message" : 'Incorrect Password {}'.format(auth["password"])}
            code = 401
        else:
            token = jwt.encode({'id': 1, 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=1)}, SECRET_KEY, "HS256")
            logger.info("Login Token generated Successfully, Token {}".format(token))
            response = {"token" : token}
            code = 200
    return json.dumps(response), code
