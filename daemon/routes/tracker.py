#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tracker related stuff only
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


from flask import Blueprint, request
from utils.log import Log
from base.tracker import Tracker
# from common.validate_auth import token_required
from common.validate_input import input_filter, validate_name

LOGGER = Log.get_logger()
tracker_blueprint = Blueprint('tracker', __name__)


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON MAY 4 2023
@tracker_blueprint.route('/announce', methods=['GET'])
# @token_required
@input_filter(checks=None, skip=['info_hash', 'peer_id'], json=False)
def tracker_announce_get():
    """
    Input - 
    Process - 
    Output - 
    """
    request_data = request.args.to_dict()
    remote_ip = request.environ['REMOTE_ADDR']
    response_list = Tracker().announce(request_data, remote_ip)
    return response_list


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON MAY 4 2023
@tracker_blueprint.route('/scrape', methods=['GET'])
# @token_required
@input_filter(checks=None, skip='info_hash', json=False)
def tracker_scrape_get():
    """
    Input - 
    Process - 
    Output - 
    """
    hashes = request.args.getlist('info_hash')
    response_list = Tracker().scrape(hashes)
    return response_list


