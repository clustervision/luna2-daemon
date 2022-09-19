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
# from common.validate_auth import *
from flask import Blueprint, request, json
from utils.log import *
from utils.database.database import *
from werkzeug.security import generate_password_hash,check_password_hash

logger = Log.get_logger()
auth_blueprint = Blueprint('auth', __name__)



@auth_blueprint.route("/register", methods=['GET'])
def register():
    data = request.get_json() 
    hashed_password = generate_password_hash(data['password'], method='sha256')

    new_user = Users(id=str(uuid.uuid4()), name=data['username'], password=hashed_password, admin=False)
    db.session.add(new_user) 
    db.session.commit()
    response = {'message': 'registered successfully'}
    code = 200
    return json.dumps(response), code


@auth_blueprint.route("/token", methods=['POST'])
def token():
    auth = request.get_json(force=True)
    if not auth or not auth["username"] or not auth["password"]:
        response = {'message' : 'login required'}
        code = 401
        return json.dumps(response), code
    select = "*"
    table = "user"
    where = [{"column": "username", "value": auth["username"]}]
    user = Database().get_record(select, table, where)
    if user:
        userID = user[0]["id"]
        password = user[0]["password"]
        if check_password_hash(password, auth["password"]):
            token = jwt.encode({'id': userID, 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=int(EXPIRY))}, SECRET_KEY, "HS256")
            response = {'token' : token}
            code = 200
            return json.dumps(response), code

    response = {'message' : 'could not verify'}
    code = 401
    return json.dumps(response), code
