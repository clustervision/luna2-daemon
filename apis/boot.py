import os
import json
from common.constants import *
from common.validate_auth import *
from flask import Blueprint, request
from utils.log import *

logger = Log.get_logger()

boot_blueprint = Blueprint('boot', __name__)

@boot_blueprint.route("/<string:token>/boot/", methods=['GET', 'POST'])
# @boot_blueprint.route("/<string:token>/boot/", methods=['GET', 'POST'], defaults={'filename': None})
# @boot_blueprint.route("/<string:token>/boot/", methods=['GET', 'POST'], defaults={'filename': None})
@login_required
def boot(token):
    logger.error("This is Boot API.")
    logger.debug("This is Boot API.")
    # Log.luna_logging("This is Boot API.", LEVEL)
    response = {"message": "This is Boot API."}
    code = 200
    return json.dumps(response), code
