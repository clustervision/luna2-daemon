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
from flask import Blueprint, request, render_template, url_for, session, redirect
from utils.log import *
from utils.database.database import *
import hashlib

logger = Log.get_logger()
admin_blueprint = Blueprint('admin', __name__, template_folder='../web/pages/', static_url_path='', static_folder='../web/static/')

"""
Input - username and password
Process - Validate the username and password from the conf file. On the success, create a token, which is valid for Exipy time mentioned in conf. 
Output - Token.
"""
@admin_blueprint.route("/admin", methods=['GET','POST'])
def login():
    Template = "login.html"
    if request.method == 'POST':
        if request.values.get('username'):
            username = request.values.get('username')
        else:
            response = {'message' : "Username is required to Login."}
            return render_template(Template, response=response), 401
        if request.values.get('password'):
            password = request.values.get('password')
            passwordHash = hashlib.md5(password.encode())
            passwordHash = passwordHash.hexdigest()
        else:
            response = {'message' : "Password is required to Login."}
            return render_template(Template, response=response), 401
        select = "*"
        table = "user"
        where = [{"column": "username", "value": username}]
        user = Database().get_record(select, table, where)
        if user:
            userID = user[0]["id"]
            password = user[0]["password"]
            if passwordHash == password:
                Template = "dashboard.html"
                return redirect(url_for('admin.dashboard'))
                # return render_template(Template), 200
            else:
                response = {'message' : "Incorrect Password Supplied."}
                return render_template(Template, response=response), 401
        else:
            response = {'message' : "Incorrect Username Supplied."}
            return render_template(Template, response=response), 401
    else:
        return render_template(Template, response=None), 200


# @admin_blueprint.before_request
# def check_logedin():
#     if not 'id' in session:
#         return redirect(url_for('admin')), 200

@admin_blueprint.route("/getaccess", methods=['GET','POST'])
def getaccess():
    Template = "getaccess.html"
    return render_template(Template, response=None), 200

@admin_blueprint.route("/dashboard", methods=['GET','POST'])
def dashboard():
    Template = "dashboard.html"
    return render_template(Template, response=None), 200