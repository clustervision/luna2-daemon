#!/usr/bin/env python3
"""
This File is use for authentication purpose.

"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

import jwt
import hashlib
import datetime
from flask import Blueprint, request, json
from utils.log import *
from utils.database import *

logger = Log.get_logger()
auth_blueprint = Blueprint('auth', __name__)



        # select = "*"
        # table = "user"
        # where = [{"column": "username", "value": auth["username"]}]
        # user = Database().get_record(select, table, where)
        # if user:
        #     userID = user[0]["id"]
        #     password = user[0]["password"]
        #     if check_password_hash(password, auth["password"]):
        #         token = jwt.encode({'id': userID, 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=int(EXPIRY))}, SECRET_KEY, "HS256")
        #         response = {'token' : token}
        #         code = 200
        #         return json.dumps(response), code



"""
Input - username and password
Process - Validate the username and password from the conf file.
  On the success, create a token, which is valid for expiry time mentioned in configuration.
Output - Token.
"""
@auth_blueprint.route("/token", methods=['POST'])
def token():
    username, password = "", ""
    auth = request.get_json(force=True)
    if not auth:
        logger.error("Login Required")
        response = {"message" : "Login Required"}
        code = 401
    if "username" not in auth:
        logger.error("Username Is Required")
        response = {"message" : "Login Required"}
        code = 401
    else:
        username = auth["username"]
    if "password" not in auth:
        logger.error("Password Is Required")
        response = {"message" : "Login Required"}
        code = 401
    else:
        password = auth["password"]

    if USERNAME != username:
        logger.info("Username {} Not belongs to INI.".format(username))
        table = "user"
        where = " WHERE username = '{}' AND roleid = '1'".format(username)
        user = Database().get_record(None, table, where)
        if user:
            UserID = user[0]["id"]
            UserPassword = user[0]["password"]
            if UserPassword == hashlib.md5(password.encode()).hexdigest():
                token = jwt.encode({'id': UserID, 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=int(EXPIRY))}, SECRET_KEY, "HS256")
                logger.debug("Login Token generated Successfully, Token {}".format(token))
                response = {'token' : token}
                code = 200
                return json.dumps(response), code
            else:
                logger.warning("Incorrect Password {} for the user {}.".format(password, username))
                response = {"message" : 'Incorrect Password {} for the user {}.'.format(password, username)}
                code = 401
        else:
            logger.error("User {} Is Not Exists.".format(username))
            response = {"message" : "User {} Is Not Exists.".format(username)}
            code = 401
    else:
        if PASSWORD != password:
            logger.warning("Incorrect Password {}, Kindly check the INI.".format(password))
            response = {"message" : 'Incorrect Password {}, Kindly check the INI.'.format(password)}
            code = 401
        else:
            # Creating Token via JWT with default id =1, expiry time and Secret Key from conf file, and algo Sha 256
            token = jwt.encode({'id': 0, 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=int(EXPIRY))}, SECRET_KEY, "HS256")
            logger.debug("Login Token generated Successfully, Token {}".format(token))
            response = {"token" : token}
            code = 201
    return json.dumps(response), code
