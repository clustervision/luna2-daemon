#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This file is the entry point for provisioning
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'


from flask import Blueprint, json, render_template, abort
from utils.log import Log
from utils.database import Database
from utils.helper import Helper
from common.constant import CONSTANT

LOGGER = Log.get_logger()
boot_blueprint = Blueprint('boot', __name__, template_folder='../templates')


@boot_blueprint.route('/boot', methods=['GET'])
def boot():
    """
    Input - None
    Process - Via jinja2 filled data in template templ_boot_ipxe.cfg
    Output - templ_boot_ipxe.cfg
    """
    nodes = ['node001', 'node002', 'node003', 'node004']
    data = {'protocol': 'http', 'server_ip': '10.141.255.254', 'server_port': '7051', 'nodes': nodes}
    template = 'templ_boot_ipxe.cfg'
    LOGGER.info(f'Boot API Serving the {template}')
    check_template = Helper().checkjinja(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}')
    if not check_template:
        abort(404, 'Empty')
    return render_template(template, p=data), 200


@boot_blueprint.route('/boot/short', methods=['GET'])
def boot_short():
    """
    Input - None
    Process - Via jinja2 filled data in template templ_boot_ipxe_short.cfg
    Output - templ_boot_ipxe_short.cfg
    """
    nodes = ['node001', 'node002', 'node003', 'node004']
    data = {'protocol': 'http', 'server_ip': '10.141.255.254', 'server_port': '7051', 'nodes': nodes}
    template = 'templ_boot_ipxe_short.cfg'
    LOGGER.info(f'Boot API Serving the {template}')
    check_template = Helper().checkjinja(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}')
    if not check_template:
        abort(404, 'Empty')
    return render_template(template, p=data), 200


@boot_blueprint.route('/boot/disk', methods=['GET'])
def boot_disk():
    """
    Input - None
    Process - Via jinja2 filled data in template templ_boot_disk.cfg
    Output - templ_boot_disk.cfg
    """
    nodes = ['node001', 'node002', 'node003', 'node004']
    data = {'protocol': 'http', 'server_ip': '10.141.255.254', 'server_port': '7051', 'nodes': nodes}
    template = 'templ_boot_disk.cfg'
    LOGGER.info(f'Boot API Serving the {template}')
    check_template = Helper().checkjinja(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}')
    if not check_template:
        abort(404, 'Empty')
    return render_template(template, p=data), 200


@boot_blueprint.route('/boot/search/mac/<string:mac>', methods=['GET'])
def boot_search_mac(mac=None):
    """
    Input - MacID
    Process - Discovery on MAC address, server will lookup the MAC if SNMP
    port-detection has been enabled
    Output - iPXE Template
    """
    data = {"protocol": "http", "server_ip": "10.141.255.254", "server_port": "7051", "nodes": None}
    node = Database().get_record(None, 'node', f' WHERE macaddr = "{mac}"')
    # TODO: Switch Configuration Needs to be checked before response
    if not node:
        LOGGER.debug(f'Mac Address {mac} Not Found.')
        abort(404, "Empty")
    # row = [{"column": "status", "value": "installer.discovery"}]
    # where = [{"column": "id", "value": node[0]["id"]}]
    # Database().update('node', row, where)
    template = 'templ_nodeboot.cfg'
    LOGGER.info(f'Boot API Serving the {template}')
    check_template = Helper().checkjinja(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}')
    if not check_template:
        abort(404, 'Empty')
    return render_template(template, p=data), 200


@boot_blueprint.route('/boot/manual/hostname/<string:hostname>', methods=['GET'])
def boot_manual_hostname(hostname=None):
    """
    Input - Hostname
    Process - Discovery on hostname, server will lookup the MAC
    if SNMP port-detection has been enabled
    Output - iPXE Template
    """
    data = {'protocol': 'http', 'server_ip': '10.141.255.254', 'server_port': '7051', 'service': '0'}
    node = Database().get_record(None, 'node', f' WHERE hostname = "{hostname}"')
    # TOODO: Switch Configuration Needs to be checked before response
    if not node:
        LOGGER.debug(f'Hostname {hostname} Not Found.')
        abort(404, "Empty")
    if node[0]['service'] is True:
        data['service'] = '1'
    template = 'templ_nodeboot.cfg'
    LOGGER.info(f'Node Found with Hostname {hostname}.')
    check_template = Helper().checkjinja(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}')
    if not check_template:
        abort(404, 'Empty')
    return render_template(template, p=data), 200

@boot_blueprint.route('/boot/install/<string:node>', methods=['GET'])
def boot_install(node=None):
    """
    Input - NodeID or node name
    Process - Call the installation script for this node.
    Output - Success or failure
    """
    # TODO: If debug mode enabled not to serve
    row = [{'column': 'status', 'value': 'installer.downloaded'}]
    where = [{"column": 'name', 'value': node}]
    install = Database().update('node', row, where)
    if install or CONSTANT['LOGGER']['LEVEL'].lower() == 'debug':
        LOGGER.info(f'Installation Script is Started For NodeID: {node}')
        response = {'message': f'Installation Script is Started For  NodeID: {node}'}
        code = 200
    else:
        LOGGER.error(f'Not Able To Find The NodeID: {node}')
        response = {'message': f'Not Able To Find The NodeID: {node}'}
        code = 404
    return json.dumps(response), code
