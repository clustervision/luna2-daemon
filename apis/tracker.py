#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tracker related stuff only
"""

__author__      = 'Antoine Schonewile'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


from flask import Blueprint, json, request
from utils.log import Log
from utils.database import Database
from utils.helper import Helper
from common.validate_auth import token_required
from common.constant import CONSTANT
from time import sleep,time
from random import randint
from utils.filter import Filter
from utils.tracker import Tracker

LOGGER = Log.get_logger()
tracker_blueprint = Blueprint('tracker', __name__)


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON MAY 4 2023
@tracker_blueprint.route('/announce', methods=['GET'])
##@token_required
def tracker_announce_get():
    """
    Input - 
    Process - 
    Output - 
    """
    access_code = 404

    request_data,ret = Filter().validate_input(request.args.to_dict())
    remote_ip=request.environ['REMOTE_ADDR']
    response,ret=Tracker().announce(request_data,remote_ip)
    LOGGER.debug(f"response = {response}, ret = [{ret}]")
    if ret:
        return response
    else:
        return f"{repsonse}\n", access_code


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON MAY 4 2023
@tracker_blueprint.route('/scrape', methods=['GET'])
##@token_required
def tracker_scrape_get():
    """
    Input - 
    Process - 
    Output - 
    """
    access_code = 404

#    request_data,ret = Filter().validate_input(request.args.to_dict())
    hashes,ret=Filter().validate_input(request.args.getlist('info_hash'))
    response,ret=Tracker().scrape(hashes)
    LOGGER.debug(f"response = {response}, ret = [{ret}]")
    if ret:
        return response
    else:
        return f"{repsonse}\n", access_code


