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
from flask import Blueprint, request, json
from utils.log import *
from utils.service import *

logger = Log.get_logger()
service_blueprint = Blueprint('service', __name__)


@service_blueprint.route("/<string:token>/service/<string:name>/<string:action>", methods=['GET'])
@login_required
def service(token, name, action):
    response, code = Service().luna_service(name, action)
    return json.dumps(response), code
