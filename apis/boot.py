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


from flask import Blueprint, render_template, abort
from utils.log import Log
from utils.database import Database
from utils.helper import Helper
from common.constant import CONSTANT
import jinja2

LOGGER = Log.get_logger()
boot_blueprint = Blueprint('boot', __name__, template_folder='../templates')

@boot_blueprint.route('/boot', methods=['GET'])
def boot():
    """
    Input - None
    Process - Via jinja2 filled data in template templ_boot_ipxe.cfg
    Output - templ_boot_ipxe.cfg
    """
    template = 'templ_boot_ipxe.cfg'
    check_template = Helper().checkjinja(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}')
    if not check_template:
        abort(404, 'Empty')
    where = ' WHERE hostname = "controller.cluster"'
    controller = Database().get_record(None, 'controller', where)
    if controller:
        ipaddr = controller[0]['ipaddr']
        serverport = controller[0]['srverport']
        access_code = 200
    else:
        environment = jinja2.Environment()
        template = environment.from_string('No Controller is available.')
        ipaddr, serverport = '', ''
        access_code = 404
    LOGGER.info(f'Boot API serving the {template}')
    return render_template(template, LUNA_CONTROLLER=ipaddr, LUNA_API_PORT=serverport), access_code


# ################### ---> Experiment to compare the logic

# @boot_blueprint.route('/bootexperimental', methods=['GET'])
# def bootexperimental():
#     """
#     Input - None
#     Process - Via jinja2 filled data in template templ_boot_ipxe.cfg
#     Output - templ_boot_ipxe.cfg
#     """
#     template = 'templ_boot_ipxe.cfg'
#     LOGGER.info(f'Boot API serving the {template}')
#     check_template = Helper().checkjinja(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}')
#     if not check_template:
#         abort(404, 'Empty')
#     variables = Helper().get_template_vars(template)
#     LOGGER.info(variables)
#     locals().update(variables)
#     return render_template(template, **locals()), 200

# ################### ---> Experiment to compare the logic


@boot_blueprint.route('/boot/short', methods=['GET'])
def boot_short():
    """
    Input - None
    Process - Via jinja2 filled data in template templ_boot_ipxe_short.cfg
    Output - templ_boot_ipxe_short.cfg
    """
    template = 'templ_boot_ipxe_short.cfg'
    check_template = Helper().checkjinja(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}')
    if not check_template:
        abort(404, 'Empty')
    where = ' WHERE hostname = "controller.cluster"'
    controller = Database().get_record(None, 'controller', where)
    if controller:
        ipaddr = controller[0]['ipaddr']
        serverport = controller[0]['srverport']
        access_code = 200
    else:
        environment = jinja2.Environment()
        template = environment.from_string('No Controller is available.')
        ipaddr, serverport = '', ''
        access_code = 404
    LOGGER.info(f'Boot API serving the {template}')
    return render_template(template, LUNA_CONTROLLER=ipaddr, LUNA_API_PORT=serverport), access_code


@boot_blueprint.route('/boot/disk', methods=['GET'])
def boot_disk():
    """
    Input - None
    Process - Via jinja2 filled data in template templ_boot_disk.cfg
    Output - templ_boot_disk.cfg
    """
    template = 'templ_boot_disk.cfg'
    check_template = Helper().checkjinja(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}')
    if not check_template:
        abort(404, 'Empty')
    where = ' WHERE hostname = "controller.cluster"'
    controller = Database().get_record(None, 'controller', where)
    if controller:
        ipaddr = controller[0]['ipaddr']
        serverport = controller[0]['srverport']
        access_code = 200
    else:
        environment = jinja2.Environment()
        template = environment.from_string('No Controller is available.')
        ipaddr, serverport = '', ''
        access_code = 404
    LOGGER.info(f'Boot API serving the {template}')
    return render_template(template, LUNA_CONTROLLER=ipaddr, LUNA_API_PORT=serverport), access_code


@boot_blueprint.route('/boot/search/mac/<string:mac>', methods=['GET'])
def boot_search_mac(mac=None):
    """
    Input - MacID
    Process - Discovery on MAC address, server will lookup the MAC if SNMP
    port-detection has been enabled
    Output - iPXE Template
    """
    template = 'templ_nodeboot.cfg'
    data = {
        'nodeid'        : None,
        'osimageid'     : None,
        'ipaddress      : None,
        'serverport'    : None,
        'intrdfile'     : None,
        'kernelfile'    : None,
        'nodename'      : None,
        'nodehostname'  : None,
        'nodeservice'   : None,
        'nodeip'        : None
    }
    check_template = Helper().checkjinja(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}')
    if not check_template:
        abort(404, 'Empty')
#    where = ' WHERE hostname = "controller.cluster"'
#    controller = Database().get_record(None, 'controller', where)
    #Antoine
    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'],['tableref="controller"',f"controller.name='{controller}'"])
    if controller:
        data['ipaddress'] = controller[0]['ipaddress']
        data['serverport'] = controller[0]['serverport']
#    nodeinterface = Database().get_record(None, 'nodeinterface', f' WHERE macaddress = "{mac}"')
    nodeinterface = Database().get_record_join(['nodeinterface.nodeid','nodeinterface.interface','ipaddress.ipaddress','network.name as network','network.network as iprange','network.subnet'], ['network.id=ipaddress.networkid','ipaddress.tablerefid=nodeinterface.id'],['tableref="nodeinterface"',f"nodeinterface.macaddress='{mac}'"])
    if nodeinterface:
        data['nodeid'] = nodeinterface[0]['nodeid']
#        where = f' WHERE id = "{nodeinterface[0]["networkid"]}"'
#        nwk = Database().get_record(None, 'network', where)
#        data['nodeip'] = Helper().get_network(nodeinterface[0]['ipaddress'], nwk[0]['subnet'])
#        subnet = data['nodeip'].split('/')
#        subnet = subnet[1]
        iprange,subnet=nodeinterface[0]['iprange'].split('/')
        if (not subnet) and nodeinterface[0]['subnet']:
            subnet=nodeinterface[0]['subnet']
        data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{subnet}'
    if data['nodeid']:
        node = Database().get_record(None, 'node', f' WHERE id = {data["nodeid"]}')
        if node:
            data['osimageid'] = node[0]['osimageid']
            data['nodename'] = node[0]['name']
            data['nodehostname'] = node[0]['hostname']
            data['nodeservice'] = node[0]['service']
    if data['osimageid']:
        osimage = Database().get_record(None, 'osimage', f' WHERE id = {data["osimageid"]}')
        if osimage:
            data['intrdfile'] = osimage[0]['initrdfile']
            data['kernelfile'] = osimage[0]['kernelfile']

    if None not in data.values():
        access_code = 200
        Helper().update_nodestate(data["nodeid"], "installer.discovery")
        # row = [{"column": "status", "value": "installer.discovery"}]
        # where = [{"column": "id", "value": data["nodeid"]}]
        # Database().update('node', row, where)
    else:
        environment = jinja2.Environment()
        template = environment.from_string('No Node is available for this mac address.')
        access_code = 404
    LOGGER.info(f'Boot API serving the {template}')
    return render_template(
        template,
        LUNA_CONTROLLER     = data['ipaddress'],
        LUNA_API_PORT       = data['serverport'],
        NODE_MAC_ADDRESS    = mac,
        OSIMAGE_INTRDFILE   = data['intrdfile'],
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

    template = 'templ_nodeboot.cfg'
    data = {
        'nodeid'        : None,
        'osimageid'     : None,
        'ipaddress      : None,
        'serverport'    : None,
        'intrdfile'     : None,
        'kernelfile'    : None,
        'nodename'      : None,
        'nodehostname'  : None,
        'nodeservice'   : None,
        'nodeip'        : None
    }
    check_template = Helper().checkjinja(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}')
    if not check_template:
        abort(404, 'Empty')
#    where = ' WHERE hostname = "controller.cluster"'
#    controller = Database().get_record(None, 'controller', where)
    #Antoine
    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'],['tableref="controller"',f"controller.name='{controller}'"])
    if controller:
        data['ipaddress'] = controller[0]['ipaddress']
        data['serverport'] = controller[0]['serverport']

    node = Database().get_record(None, 'node', f' WHERE name = "{hostname}"')
    if node:
        data['osimageid'] = node[0]['osimageid']
        data['nodename'] = node[0]['name']
        data['nodehostname'] = node[0]['hostname']
        data['nodeservice'] = node[0]['service']
        data['nodeid'] = node[0]['id']
    if data['nodeid']:
        #where = f' WHERE nodeid = {data["nodeid"]} AND interface = "BOOTIF";'
        #nodeinterface = Database().get_record(None, 'nodeinterface', where)
        nodeinterface = Database().get_record_join(['nodeinterface.nodeid','nodeinterface.interface','nodeinterface.macaddress','ipaddress.ipaddress','network.name as network','network.network as iprange','network.subnet'], ['network.id=ipaddress.networkid','ipaddress.tablerefid=nodeinterface.id'],['tableref="nodeinterface"',f"nodeinterface.nodeid='{data['nodeid']}'",'nodeinterface.interface="BOOTIF"'])
        if nodeinterface:
#            row = [{"column": "macaddress", "value": nodeinterface[0]['macaddress']}]
#            # not sure if below is really needed.....
#            where = [
#                {"column": "nodeid", "value": data["nodeid"]},
#                {"column": "interface", "value": "BOOTIF"}
#                ]
#            Database().update('nodeinterface', row, where)
#            where = f' WHERE nodeid = {data["nodeid"]} AND interface = "BOOTIF";'
#            nodeinterface = Database().get_record(None, 'nodeinterface', where)
#        where = f' WHERE id = "{nodeinterface[0]["networkid"]}"'
#        nwk = Database().get_record(None, 'network', where)
#        data['nodeip'] = Helper().get_network(nodeinterface[0]['ipaddress'], nwk[0]['subnet'])
#        subnet = data['nodeip'].split('/')
#        subnet = subnet[1]
        iprange,subnet=nodeinterface[0]['iprange'].split('/')
        if (not subnet) and nodeinterface[0]['subnet']:
            subnet=nodeinterface[0]['subnet']
        data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{subnet}'

    if data['osimageid']:
        osimage = Database().get_record(None, 'osimage', f' WHERE id = {data["osimageid"]}')
        if osimage:
            data['intrdfile'] = osimage[0]['initrdfile']
            data['kernelfile'] = osimage[0]['kernelfile']

    if None not in data.values():
        access_code = 200
        Helper().update_nodestate(data["nodeid"], "installer.discovery")
        # row = [{"column": "status", "value": "installer.discovery"}]
        # where = [{"column": "id", "value": data["nodeid"]}]
        # Database().update('node', row, where)
    else:
        environment = jinja2.Environment()
        template = environment.from_string('No Node is available for this mac address.')
        access_code = 404
    LOGGER.info(f'Boot API serving the {template}')
    return render_template(
        template,
        LUNA_CONTROLLER     = data['ipaddress'],
        LUNA_API_PORT       = data['serverport'],
        NODE_MAC_ADDRESS    = mac,
        OSIMAGE_INTRDFILE   = data['intrdfile'],
        OSIMAGE_KERNELFILE  = data['kernelfile'],
        NODE_NAME           = data['nodename'],
        NODE_HOSTNAME       = data['nodehostname'],
        NODE_SERVICE        = data['nodeservice'],
        NODE_IPADDRESS      = data['nodeip']
    ), access_code


@boot_blueprint.route('/boot/install/<string:node>', methods=['GET'])
def boot_install(node=None):
    """
    Input - NodeID or node name
    Process - Call the installation script for this node.
    Output - Success or failure
    """
    data = {
        'osimageid'             : None,
        'groupid'               : None,
        'nodeid'                : None,
        'ipaddr'                : None,
        'serverport'            : None,
        'nodehostname'          : None,
        'osimagename'           : None,
        'tarball'               : None,
        'selinux'               : None,
        'setupbmc'              : None,
        'localinstall'          : None,
        'unmanaged_bmc_users'   : None,
        'interfaces'            : {}
    }
    template = 'templ_install.cfg'
    check_template = Helper().checkjinja(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}')
    if not check_template:
        abort(404, 'Empty')

    cluster = Database().get_record(None, 'cluster', None)
    if cluster:
        data['selinux']      = Helper().bool_revert(cluster[0]['security'])
        where = ' WHERE hostname = "controller.cluster"'
    controller = Database().get_record(None, 'controller', where)
    if controller:
        data['ipaddr']      = controller[0]['ipaddr']
        data['serverport']  = controller[0]['srverport']
    node_details = Database().get_record(None, 'node', f' WHERE name = "{node}"')
    if node:
        data['osimageid']           = node_details[0]['osimageid']
        data['groupid']             = node_details[0]['groupid']
        data['nodehostname']        = node_details[0]['hostname']
        data['nodeid']              = node_details[0]['id']
        data['setupbmc']            = Helper().bool_revert(node_details[0]['setupbmc'])
        data['localinstall']        = node_details[0]['localinstall']
        data['unmanaged_bmc_users'] = node_details[0]['unmanaged_bmc_users']

    if data['groupid']:
        group = Database().get_record(None, 'group', f' WHERE id = {data["groupid"]}')
        if group:
            if data['localinstall'] is None:
                data['localinstall'] = group[0]['localinstall']
            if data['unmanaged_bmc_users'] is None:
                data['unmanaged_bmc_users'] = group[0]['unmanaged_bmc_users']
    if data['unmanaged_bmc_users'] is None:
        data['unmanaged_bmc_users'] = ''
    if data['localinstall'] is None:
        LOGGER.error('localinstall is not set')
    else:
        data['localinstall'] = Helper().bool_revert(data['localinstall'])
    if data['osimageid']:
        osimage = Database().get_record(None, 'osimage', f' WHERE id = {data["osimageid"]}')
        if osimage:
            data['osimagename'] = osimage[0]['name']
            data['tarball'] = osimage[0]['tarball']

    if data['nodeid']:
        where = f' WHERE nodeid = {data["nodeid"]};'
        nodeinterface = Database().get_record(None, 'nodeinterface', where)
        if nodeinterface:
            for nwkif in nodeinterface:
                data['interfaces'][nwkif['interface']] = {}
                where = f' WHERE id = "{nwkif["networkid"]}"'
                nwk = Database().get_record(None, 'network', where)
                node_nwk = Helper().get_network(nwkif['ipaddress'], nwk[0]['subnet'])
                subnet = node_nwk.split('/')
                subnet = subnet[1]
                node_nwk = f'{nwkif["ipaddress"]}/{subnet}'
                data['interfaces'][nwkif['interface']]['interface'] = nwkif['interface']
                data['interfaces'][nwkif['interface']]['ip'] = nwkif['ipaddress']
                data['interfaces'][nwkif['interface']]['network'] = node_nwk
                data['interfaces'][nwkif['interface']]['netmask'] = nwk[0]['subnet']
                data['interfaces'][nwkif['interface']]['networkname'] = nwk[0]['name']

    if None not in data.values():
        access_code = 200
        Helper().update_nodestate(data["nodeid"], "installer.downloaded")
    else:
        environment = jinja2.Environment()
        template = environment.from_string('No Node is available for this mac address.')
        access_code = 500
    LOGGER.info(data)
    return render_template(
        template,
        LUNA_CONTROLLER         = data['ipaddr'],
        LUNA_API_PORT           = data['serverport'],
        LUNA_HOSTNAME           = data['nodehostname'],
        LUNA_OSIMAGE            = data['osimagename'],
        LUNA_FILE               = data['tarball'],
        LUNA_SELINUX_ENABLED    = data['selinux'],
        LUNA_BMCSETUP           = data['setupbmc'],
        LUNA_BOOTLOADER         = data['localinstall'],
        LUNA_LOCALINSTALL       = data['localinstall'],
        LUNA_UNMANAGED_BMC_USERS= data['unmanaged_bmc_users'],
        LUNA_INTERFACES         = data['interfaces']
    ), access_code
