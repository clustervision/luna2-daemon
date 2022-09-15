import os
import json
from common.constants import *
from common.validate_auth import *
from flask import Blueprint, request
from utils.log import *
from utils.service import *

logger = Log.get_logger()
monitor_blueprint = Blueprint('monitor', __name__)


@monitor_blueprint.route("/<string:token>/monitor/service/<string:name>", methods=['GET'])
@login_required
def monitor_service(token, name):
    action = "status"
    response, code = Service().luna_service(name, action)
    return json.dumps(response), code
