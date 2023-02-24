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
    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'],['tableref="controller"','controller.hostname="controller.cluster"'])
    if controller:
        ipaddress = controller[0]['ipaddress']
        serverport = controller[0]['serverport']
        access_code = 200
    else:
        environment = jinja2.Environment()
        template = environment.from_string('No Controller is available.')
        ipaddress, serverport = '', ''
        access_code = 404
    LOGGER.info(f'Boot API serving the {template}')
    return render_template(template, LUNA_CONTROLLER=ipaddress, LUNA_API_PORT=serverport), access_code


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
    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'],['tableref="controller"','controller.hostname="controller.cluster"'])
    if controller:
        ipaddress = controller[0]['ipaddress']
        serverport = controller[0]['serverport']
        access_code = 200
    else:
        environment = jinja2.Environment()
        template = environment.from_string('No Controller is available.')
        ipaddress, serverport = '', ''
        access_code = 404
    LOGGER.info(f'Boot API serving the {template}')
    return render_template(template, LUNA_CONTROLLER=ipaddress, LUNA_API_PORT=serverport), access_code


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
    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'],['tableref="controller"','controller.hostname="controller.cluster"'])
    if controller:
        ipaddress = controller[0]['ipaddress']
        serverport = controller[0]['serverport']
        access_code = 200
    else:
        environment = jinja2.Environment()
        template = environment.from_string('No Controller is available.')
        ipaddress, serverport = '', ''
        access_code = 404
    LOGGER.info(f'Boot API serving the {template}')
    return render_template(template, LUNA_CONTROLLER=ipaddress, LUNA_API_PORT=serverport), access_code


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
        'ipaddress'     : None,
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
    #Antoine
    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'],['tableref="controller"','controller.hostname="controller.cluster"'])
    if controller:
        data['ipaddress'] = controller[0]['ipaddress']
        data['serverport'] = controller[0]['serverport']
    nodeinterface = Database().get_record_join(['nodeinterface.nodeid','nodeinterface.interface','ipaddress.ipaddress','network.name as network','network.network as networkip','network.subnet'], ['network.id=ipaddress.networkid','ipaddress.tablerefid=nodeinterface.id'],['tableref="nodeinterface"',f"nodeinterface.macaddress='{mac}'"])
    if nodeinterface:
        data['nodeid'] = nodeinterface[0]['nodeid']
        data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
    if data['nodeid']:
        node = Database().get_record_join(['node.*','group.osimageid as grouposimageid'],['group.id=node.groupid'],[f'node.id={data["nodeid"]}'])
        if node:
            data['osimageid'] = node[0]['osimageid'] or node[0]['grouposimageid']
            data['nodename'] = node[0]['name']
#            data['nodehostname'] = node[0]['hostname']
            data['nodehostname'] = node[0]['name'] # + fqdn - pending
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
        LOGGER.info(f'template mac search data: {data}')
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
        'ipaddress'     : None,
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
    #Antoine
    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'],['tableref="controller"','controller.hostname="controller.cluster"'])
    if controller:
        data['ipaddress'] = controller[0]['ipaddress']
        data['serverport'] = controller[0]['serverport']

    # we probably have to cut the fqdn off of hostname?
    node = Database().get_record_join(['node.*','group.osimageid as grouposimageid'],['group.id=node.groupid'],[f'node.name="{hostname}"'])
    if node:
        data['osimageid'] = node[0]['osimageid'] or node[0]['grouposimageid']
        data['nodename'] = node[0]['name']
#        data['nodehostname'] = node[0]['hostname']
        data['nodehostname'] = node[0]['name'] # + fqdn ?
        data['nodeservice'] = node[0]['service']
        data['nodeid'] = node[0]['id']
    if data['nodeid']:
        #where = f' WHERE nodeid = {data["nodeid"]} AND interface = "BOOTIF";'
        #nodeinterface = Database().get_record(None, 'nodeinterface', where)
        nodeinterface = Database().get_record_join(['nodeinterface.nodeid','nodeinterface.interface','nodeinterface.macaddress','ipaddress.ipaddress','network.name as network','network.network as networkip','network.subnet'], ['network.id=ipaddress.networkid','ipaddress.tablerefid=nodeinterface.id'],['tableref="nodeinterface"',f"nodeinterface.nodeid='{data['nodeid']}'",f'nodeinterface.macaddress="{mac}"'])
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
            data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
        else:
            #uh oh... no bootif??
            data['nodeip'] = ''

    if data['osimageid']:
        osimage = Database().get_record(None, 'osimage', f' WHERE id = {data["osimageid"]}')
        if osimage:
            data['intrdfile'] = osimage[0]['initrdfile']
            data['kernelfile'] = osimage[0]['kernelfile']

    LOGGER.info(f"manual boot template date: [{data}]")

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
        'ipaddress'             : None,
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
    #Antoine
    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'],['tableref="controller"','controller.hostname="controller.cluster"'])
    if controller:
        data['ipaddress']   = controller[0]['ipaddress']
        data['serverport']  = controller[0]['serverport']
    node_details = Database().get_record_join(['node.*','group.osimageid as grouposimageid'],['group.id=node.groupid'],[f'node.name="{node}"'])
    if node_details:
        if node_details[0]['osimageid']:
            data['osimageid']       = node_details[0]['osimageid']
        else:
            data['osimageid']       = node_details[0]['grouposimageid']
        data['groupid']             = node_details[0]['groupid']
#        data['nodehostname']        = node_details[0]['hostname']
        data['nodehostname']        = node_details[0]['name'] # + fqdn
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
        nodeinterface = Database().get_record_join(['nodeinterface.nodeid','nodeinterface.interface','nodeinterface.macaddress','ipaddress.ipaddress','network.name as network','network.network as networkip','network.subnet'], ['network.id=ipaddress.networkid','ipaddress.tablerefid=nodeinterface.id'],['tableref="nodeinterface"',f"nodeinterface.nodeid='{data['nodeid']}'"])
        if nodeinterface:
            for nwkif in nodeinterface:
                data['interfaces'][nwkif['interface']] = {}
                node_nwk = f'{nwkif["ipaddress"]}/{nwkif["subnet"]}'
                netmask=Helper().get_netmask(node_nwk)
 
                data['interfaces'][nwkif['interface']]['interface'] = nwkif['interface']
                data['interfaces'][nwkif['interface']]['ipaddress'] = nwkif['ipaddress']
                data['interfaces'][nwkif['interface']]['network'] = node_nwk
                data['interfaces'][nwkif['interface']]['netmask'] = netmask
                data['interfaces'][nwkif['interface']]['networkname'] = nwkif['network']

    LOGGER.info(f"boot install data: [{data}]")
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
        LUNA_CONTROLLER         = data['ipaddress'],
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

