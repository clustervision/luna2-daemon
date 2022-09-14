#!/usr/bin/env python3

import os
import sys
import logging
import configparser
from flask import  Flask, request, url_for, json, send_file
# from utils.log import *
from utils.constants import *
from utils.helper import *
from utils.service import *
from utils.files import *

# Log().init_log(LEVEL)
# log.init_log(LEVEL)
# Log().luna_logging("test", "debug")
# log_init = Log()
# print(log_init)
# # logs = Log().luna_logging("test", LEVEL)
# print(logs)

api = Flask(__name__)


@api.route("/<string:token>/boot", methods=['GET', 'POST'])
def boot(token):
    result = {"message": "This is Boot API."}
    return result, 200


@api.route("/<string:token>/config", methods=['GET', 'POST'])
def config(token):
    result = {"message": "This is Config API"}
    return result, 200


@api.route("/<string:token>/config/node/<string:node>", methods=['GET', 'POST'])
def confignode(token, node):
    result = {"message": "This is Config Node API, Node is: "+node}
    return result, 200


@api.route("/<string:token>/config/node/<string:id>", methods=['GET', 'POST'])
def confignodeid(token, id):
    result = {"message": "This is Config ID API, ID is : "+id}
    return result, 200


@api.route("/<string:token>/files/", methods=['GET'], defaults={'filename': None})
@api.route("/<string:token>/files/<string:filename>", methods=['GET'])
def files(token, filename=None):
    # luna_logging(token, "info")
    if filename:
        filepath = Files().check_file(filename)
        if filepath:
            return send_file(filepath, as_attachment=True)
        else:
            response = "File {}, is not present.".format(filename)
            code = 200
            return json.dumps(response), code
    else:
        filelist = Files().list_files()
        if filelist:
            return filelist
        else:
            response = "Nothing is present."
            code = 200
            return json.dumps(response), code


@api.route("/<string:token>/service/<string:name>/<string:action>", methods=['GET'])
def service(token, name, action):
    response, code = Service().luna_service(name, action)
    return json.dumps(response), code


@api.errorhandler(404)
def page_not_found(e):
    response = {"message": "Route Not Found"}
    return json.dumps(response), 404


if __name__ == "__main__":
    api.run(host=SERVERIP, port=SERVERPORT, debug=True)