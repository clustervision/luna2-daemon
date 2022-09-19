#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File is a A Entry Point to Monitor the services.

"""

from common.constants import *
from flask import Blueprint, request, json
from utils.log import *
from utils.service import *

logger = Log.get_logger()
monitor_blueprint = Blueprint('monitor', __name__)


@monitor_blueprint.route("/monitor/service/<string:name>", methods=['GET'])
def monitor_service(token, name):
    action = "status"
    response, code = Service().luna_service(name, action)
    return json.dumps(response), code
