#!/usr/bin/env python3

import os
import logging
import sys
import configparser
from dotenv import load_dotenv
from flask import request, url_for, Flask, json

load_dotenv('config/.env', override=False)
token = os.getenv('TOKEN')
serverip = os.getenv('SERVERIP')
serverport = os.getenv('RESTSERVERPORT')

configParser = configparser.RawConfigParser()
configParser.read('config/config.ini')
SERVICEFILE = configParser.get("FILES", "service_file") 

api = Flask(__name__)


@api.route("/<string:token>/boot", methods=['GET', 'POST'])
def boot(token):
    result = {"message": "This is Boot API. Service File is -> {} and service port is {}".format(SERVICEFILE, serverport)}
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


@api.errorhandler(404)
def page_not_found(e):
    result = {"message": "Route Not Found"}
    return result, 404


if __name__ == "__main__":
    api.run(host=serverip, port=serverport, debug=True)