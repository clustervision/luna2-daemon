import os
import json
from common.constants import *
from common.validate_auth import *
from flask import Blueprint, request
from utils.log import *
from utils.service import *

logger = Log.get_logger()
service_blueprint = Blueprint('service', __name__)


@service_blueprint.route("/<string:token>/service/<string:name>/<string:action>", methods=['GET'])
@login_required
def service(token, name, action):
    response, code = Service().luna_service(name, action)
    return json.dumps(response), code
