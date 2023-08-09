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


from flask import Blueprint, render_template, render_template_string
from utils.log import Log
from common.validate_input import validate_name
from common.validate_auth import token_required
from base.boot import Boot

LOGGER = Log.get_logger()
boot_blueprint = Blueprint('boot', __name__, template_folder='../templates')


@boot_blueprint.route('/boot', methods=['GET'])
def boot():
    """
    This route will provide the default boot template
    Input - None
    Process - Via jinja2 filled data in template templ_boot_ipxe.cfg
    Output - templ_boot_ipxe.cfg
    """
    access_code=404
    status, response = Boot().default()
    if status is True:
        access_code=200
    else:
        access_code=404
        return response, access_code
    return render_template(
        response['template'],
        LUNA_CONTROLLER     = response['LUNA_CONTROLLER'],
        LUNA_API_PORT       = response['LUNA_API_PORT'],
        WEBSERVER_PORT      = response['WEBSERVER_PORT'],
        LUNA_API_PROTOCOL   = response['LUNA_API_PROTOCOL'],
        WEBSERVER_PROTOCOL  = response['WEBSERVER_PROTOCOL'],
        NODES               = response['NODES'],
        AVAILABLE_NODES     = response['AVAILABLE_NODES'],
        GROUPS              = response['GROUPS']
    ), access_code


@boot_blueprint.route('/boot/short', methods=['GET'])
def boot_short():
    """
    Input - None
    Process - Via jinja2 filled data in template templ_boot_ipxe_short.cfg
    Output - templ_boot_ipxe_short.cfg
    """
    access_code=404
    status, response = Boot().boot_short()
    if status is True:
        access_code=200
    else:
        access_code=404
        return response, access_code
    return render_template(
        response['template'],
        LUNA_CONTROLLER     = response['LUNA_CONTROLLER'],
        LUNA_API_PORT       = response['LUNA_API_PORT'],
        WEBSERVER_PORT      = response['WEBSERVER_PORT'],
        LUNA_API_PROTOCOL   = response['LUNA_API_PROTOCOL'],
        WEBSERVER_PROTOCOL  = response['WEBSERVER_PROTOCOL']
    ), access_code


@boot_blueprint.route('/boot/disk', methods=['GET'])
def boot_disk():
    """
    Input - None
    Process - Via jinja2 filled data in template templ_boot_disk.cfg
    Output - templ_boot_disk.cfg
    """
    access_code=404
    status, response = Boot().boot_disk()
    if status is True:
        access_code=200
    else:
        access_code=404
        return response, access_code
    return render_template(
        response['template'],
        LUNA_CONTROLLER     = response['LUNA_CONTROLLER'],
        LUNA_API_PORT       = response['LUNA_API_PORT']
    ), access_code


@boot_blueprint.route('/boot/search/mac/<string:mac>', methods=['GET'])
def boot_search_mac(mac=None):
    """
    Input - MacID
    Process - Discovery on MAC address, server will lookup the MAC if SNMP
    port-detection has been enabled
    Output - iPXE Template
    """
    access_code=404
    status, data = Boot().discover_mac(mac)
    if status is True:
        access_code=200
    else:
        access_code=404
        return data, access_code
    return render_template(
            data['template'],
            LUNA_CONTROLLER     = data['ipaddress'],
            LUNA_API_PORT       = data['serverport'],
            LUNA_API_PROTOCOL   = data['protocol'],
            WEBSERVER_PORT      = data['webserver_port'],
            WEBSERVER_PROTOCOL  = data['webserver_protocol'],
            NODE_MAC_ADDRESS    = data['mac'],
            OSIMAGE_INITRDFILE  = data['initrdfile'],
            OSIMAGE_KERNELFILE  = data['kernelfile'],
            NODE_NAME           = data['nodename'],
            NODE_HOSTNAME       = data['nodehostname'],
            NODE_SERVICE        = data['nodeservice'],
            NODE_IPADDRESS      = data['nodeip']
        ), access_code


@boot_blueprint.route('/boot/manual/group/<string:groupname>/<string:mac>', methods=['GET'])
def boot_manual_group(groupname=None, mac=None):
    """
    Input - Group
    Process - pick first available node in the chosen group,
            or create one if there is none available.
    Output - iPXE Template
    """
    access_code=404
    status, data = Boot().discover_group_mac(groupname, mac)
    if status is True:
        access_code=200
    else:
        access_code=404
        return data, access_code
    return render_template(
        data['template'],
        LUNA_CONTROLLER     = data['ipaddress'],
        LUNA_API_PORT       = data['serverport'],
        LUNA_API_PROTOCOL   = data['protocol'],
        WEBSERVER_PORT      = data['webserver_port'],
        WEBSERVER_PROTOCOL  = data['webserver_protocol'],
        NODE_MAC_ADDRESS    = data['mac'],
        OSIMAGE_INITRDFILE   = data['initrdfile'],
        OSIMAGE_KERNELFILE  = data['kernelfile'],
        NODE_NAME           = data['nodename'],
        NODE_HOSTNAME       = data['nodehostname'],
        NODE_SERVICE        = data['nodeservice'],
        NODE_IPADDRESS      = data['nodeip']
    ), access_code


@boot_blueprint.route('/boot/manual/hostname/<string:hostname>/<string:mac>', methods=['GET'])
def boot_manual_hostname(hostname=None, mac=None):
    """
    Input - Hostname
    Process - Discovery on hostname, server will lookup the MAC
    if SNMP port-detection has been enabled
    Output - iPXE Template
    """
    access_code=404
    status, data = Boot().discover_hostname_mac(hostname, mac)
    if status is True:
        access_code=200
    else:
        access_code=404
        return data, access_code
    return render_template(
        data['template'],
        LUNA_CONTROLLER     = data['ipaddress'],
        LUNA_API_PORT       = data['serverport'],
        LUNA_API_PROTOCOL   = data['protocol'],
        WEBSERVER_PORT      = data['webserver_port'],
        WEBSERVER_PROTOCOL  = data['webserver_protocol'],
        NODE_MAC_ADDRESS    = data['mac'],
        OSIMAGE_INITRDFILE   = data['initrdfile'],
        OSIMAGE_KERNELFILE  = data['kernelfile'],
        NODE_NAME           = data['nodename'],
        NODE_HOSTNAME       = data['nodehostname'],
        NODE_SERVICE        = data['nodeservice'],
        NODE_IPADDRESS      = data['nodeip']
    ), access_code


@boot_blueprint.route('/boot/install/<string:node>', methods=['GET'])
@token_required
@validate_name
def boot_install(node=None):
    """
    Input - NodeID or node name
    Process - Call the installation script for this node.
    Output - Success or failure
    """
    access_code=404
    status, data = Boot().install(node)
    if status is True:
        access_code=200
    else:
        access_code=404
        return data, access_code
    return render_template_string(
        data['template_data'],
        LUNA_CONTROLLER         = data['ipaddress'],
        LUNA_API_PORT           = data['serverport'],
        LUNA_API_PROTOCOL       = data['protocol'],
        WEBSERVER_PORT          = data['webserver_port'],
        WEBSERVER_PROTOCOL      = data['webserver_protocol'],
        NODE_HOSTNAME           = data['nodehostname'],
        NODE_NAME               = data['nodename'],
        LUNA_OSIMAGE            = data['osimagename'],
        LUNA_DISTRIBUTION       = data['distribution'],
        LUNA_IMAGEFILE          = data['imagefile'],
        LUNA_FILE               = data['imagefile'],
        LUNA_SELINUX_ENABLED    = data['selinux'],
        LUNA_SETUPBMC           = data['setupbmc'],
        LUNA_BMC                = data['bmc'],
        LUNA_BOOTLOADER         = data['localinstall'],
        LUNA_LOCALINSTALL       = data['localinstall'],
        LUNA_UNMANAGED_BMC_USERS= data['unmanaged_bmc_users'],
        LUNA_INTERFACES         = data['interfaces'],
        LUNA_PRESCRIPT          = data['prescript'],
        LUNA_PARTSCRIPT         = data['partscript'],
        LUNA_POSTSCRIPT         = data['postscript'],
        PROVISION_METHOD        = data['provision_method'],
        PROVISION_FALLBACK      = data['provision_fallback'],
        NAME_SERVER             = data['name_server'],
        DOMAIN_SEARCH           = data['domain_search'],
        NTP_SERVER              = data['ntp_server'],
        LUNA_TOKEN              = data['jwt_token']
    ), access_code
