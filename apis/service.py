#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File Manage the Services, such as DHCP as dhcpd and DNS as named.

"""

from common.constants import *
from common.validate_auth import *
from flask import current_app, Blueprint, request, json
from utils.log import *
from utils.service import *

logger = Log.get_logger()
service_blueprint = Blueprint('service', __name__)

@service_blueprint.route("/service/<string:name>/<string:action>", methods=['POST'])
@token_required
def service(name, action):
    response, code = Service().luna_service(name, action)
    return json.dumps(response), code


@service_blueprint.route("/service/test/<string:name>", methods=['GET'])
@validate_access
def service_test(name, **kwargs):
    access = "anonymous"
    if "access" in kwargs:
        access = "admin"
    # for key, value in kwargs.items():
    #     print(value)
    #     if key == "access" and value == "admin":
    #         access = "admin"
    print(name)
    print(access)
    return access