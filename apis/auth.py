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
from flask import Blueprint, request, json
from utils.log import *

logger = Log.get_logger()
auth_blueprint = Blueprint('auth', __name__)


"""
Input - username and password
Process - Validate the username and password from the conf file. On the success, create a token, which is valid for Exipy time mentioned in conf. 
Output - Token.
"""
@auth_blueprint.route("/token", methods=['POST'])
def token():
    auth = request.get_json(force=True)
    if not auth or not auth["username"] or not auth["password"]:
        logger.error("Login Required")
        response = {"message" : "Login Required"}
        code = 401
    print(HOST)
    print(USERNAME)
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
            # Creating Token via JWT with default id =1, expiry time and Secret Key from conf file, and algo Sha 256
            token = jwt.encode({'id': 1, 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=int(EXPIRY))}, SECRET_KEY, "HS256")
            logger.debug("Login Token generated Successfully, Token {}".format(token))
            response = {"token" : token}
            code = 201
    return json.dumps(response), code