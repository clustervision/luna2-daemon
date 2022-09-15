import os
import json
from common.constants import *
from common.validate_auth import *
from flask import Blueprint, request
from utils.log import *

logger = Log.get_logger()
boot_blueprint = Blueprint('boot', __name__)


@boot_blueprint.route("/<string:token>/boot", methods=['GET'])
@login_required
def boot(token):
    logger.error("This is Boot API.")
    response = {"message": "This is Boot API."}
    code = 200
    return json.dumps(response), code


@boot_blueprint.route("/<string:token>/boot/search/mac/<string:mac>", methods=['GET'])
@login_required
def boot_search_mac(token, mac=None):
    if mac:
        logger.info("This is Boot Search API MACID is. {}".format(mac))
        response = {"message": "This is Boot Search API MACID is. {}".format(mac)}
        code = 200
    else:
        logger.error("MacID is Missing.")
        response = {"message": "MacID is Missing."}
        code = 200
    return json.dumps(response), code


@boot_blueprint.route("/<string:token>/boot/install/<string:node>", methods=['GET'])
@login_required
def boot_install(token, node=None):
    if node:
        logger.info("This is Boot Install API NodeID is: {}".format(node))
        response = {"message": "This is Boot Install API NodeID is: {}".format(node)}
        code = 200
    else:
        logger.error("NodeID is Missing.")
        response = {"message": "NodeID is Missing."}
        code = 200
    return json.dumps(response), code
