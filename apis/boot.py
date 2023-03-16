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
from utils.service import Service
import concurrent.futures

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
    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'],['tableref="controller"','controller.hostname="controller"'])
    if controller:
        ipaddress = controller[0]['ipaddress']
        serverport = controller[0]['serverport']
        webserverport = serverport
        if 'WEBSERVER' in CONSTANT.keys():
           if 'PORT' in CONSTANT['WEBSERVER']:
               webserverport = CONSTANT['WEBSERVER']['PORT']

        nodes,availnodes=[],[]
        allnodes = Database().get_record(None, 'node')
        mostnodes = Database().get_record_join(['node.name','nodeinterface.macaddress'], ['nodeinterface.nodeid=node.id'], ["nodeinterface.interface='BOOTIF'"])  # BOOTIF is not entirely true but for now it will do. pending
        allnodes+=mostnodes
        checked={}
        if allnodes:
            for node in allnodes:
                if node['name'] not in checked:
                    checked.append(node['name'])
                    nodes.append(node['name'])
                    if not node['macaddress']:
                        availnodes.append(node['name'])

        access_code = 200
    else:
        environment = jinja2.Environment()
        template = environment.from_string('No Controller is available.')
        ipaddress, serverport = '', ''
        access_code = 404
    LOGGER.info(f'Boot API serving the {template}')
    return render_template(template, LUNA_CONTROLLER=ipaddress, LUNA_API_PORT=serverport, WEBSERVER_PORT=webserverport, NODES=nodes, AVAILABLE_NODES=availnodes), access_code


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
    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'],['tableref="controller"','controller.hostname="controller"'])
    if controller:
        ipaddress = controller[0]['ipaddress']
        serverport = controller[0]['serverport']
        webserverport = serverport
        if 'WEBSERVER' in CONSTANT.keys():
           if 'PORT' in CONSTANT['WEBSERVER']:
               webserverport = CONSTANT['WEBSERVER']['PORT']
        access_code = 200
    else:
        environment = jinja2.Environment()
        template = environment.from_string('No Controller is available.')
        ipaddress, serverport = '', ''
        access_code = 404
    LOGGER.info(f'Boot API serving the {template}')
    return render_template(template, LUNA_CONTROLLER=ipaddress, LUNA_API_PORT=serverport, WEBSERVER_PORT=webserverport), access_code


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
    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'],['tableref="controller"','controller.hostname="controller"'])
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
        'initrdfile'    : None,
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
    #LOGGER.info(f"BOOT/SEARCH/MAC received for {mac}")
    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'],['tableref="controller"','controller.hostname="controller"'])
    if controller:
        data['ipaddress'] = controller[0]['ipaddress']
        data['serverport'] = controller[0]['serverport']
        data['webserverport'] = data['serverport']
        if 'WEBSERVER' in CONSTANT.keys():
           if 'PORT' in CONSTANT['WEBSERVER']:
               data['webserverport'] = CONSTANT['WEBSERVER']['PORT']
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
            if ('kernelfile' in osimage[0]) and (osimage[0]['kernelfile']):
                data['kernelfile'] = f"{osimage[0]['name']}-{osimage[0]['kernelfile']}"
            elif ('kernelversion' in osimage[0]) and (osimage[0]['kernelversion']):
                data['kernelfile'] = f"{osimage[0]['name']}-vmlinuz-{osimage[0]['kernelversion']}"

            if ('initrdfile' in osimage[0]) and (osimage[0]['initrdfile']):
                data['initrdfile'] = f"{osimage[0]['name']}-{osimage[0]['initrdfile']}"
            elif ('kernelversion' in osimage[0]) and (osimage[0]['kernelversion']):
                data['initrdfile'] = f"{osimage[0]['name']}-initramfs-{osimage[0]['kernelversion']}"
            
    if None not in data.values():
        access_code = 200
        Helper().update_nodestate(data["nodeid"], "installer.discovery")
        # reintroduced below section as if we serve files through e.g. nginx, we won't update anything
        row = [{"column": "status", "value": "installer.discovery"}]
        where = [{"column": "id", "value": data['nodeid']}]
        Database().update('node', row, where)
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
        WEBSERVER_PORT      = data['webserverport'],
        NODE_MAC_ADDRESS    = mac,
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
    Process - pick first available node in the choosen group, or create one if there is none available.
    Output - iPXE Template
    """

    template = 'templ_nodeboot.cfg'
    data = {
        'nodeid'        : None,
        'osimageid'     : None,
        'ipaddress'     : None,
        'serverport'    : None,
        'initrdfile'    : None,
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
    networkname=None # used below
    network=None     # used below

    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress','network.name as networkname'], ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],['tableref="controller"','controller.hostname="controller"'])
    if controller:
        data['ipaddress'] = controller[0]['ipaddress']
        data['serverport'] = controller[0]['serverport']
        data['webserverport'] = data['serverport']
        networkname=controller[0]['networkname']
        if 'WEBSERVER' in CONSTANT.keys():
           if 'PORT' in CONSTANT['WEBSERVER']:
               data['webserverport'] = CONSTANT['WEBSERVER']['PORT']

    list1=Database().get_record_join(['node.*','group.name as groupname','nodeinterface.interface','nodeinterface.macaddress'],['nodeinterface.nodeid=node.id','group.id=node.groupid'])
    list2=Database().get_record_join(['node.*','group.name as groupname'],['group.id=node.groupid'])
    list=list1+list2

    ips=[]
    if networkname:
        network = Database().get_record_join(['ipaddress.ipaddress','network.network','network.subnet'], ['network.id=ipaddress.networkid'], [f"network.name='{networkname}'"])
        if network:
            for ip in network:
                ips.append(ip['ipaddress'])

    hostname=None # we use it further down below.
    checked={}
    if not list:
        # we have no spare or free nodes in here.
        pass
    else:
        for node in list:
            if node['name'] not in checked:
                checked.append(node['name'])
                if 'interface' in node and 'macaddress' in node and not node['macaddress']:
                    # mac is empty. candidate!
                    hostname=node['name']
                    break
                elif not 'interface' in node:
                    # node is there but no interface. we'll take it!
                    hostname=node['name']
#TWAN
                    # we need to pick the currect network in a smart way. we assume the default network.
                    avail_ip=Helper().get_available_ip(network['network'],network['subnet'],taken_ips)
                    result,mesg = Config().node_interface_config(node['id'],'BOOTIF',mac)  # boot if not sufficient/ pending
                    if result:
                        result,mesg = Config().node_interface_ipaddress_config(node['id'],'BOOTIF',avail_ip,networkname)
                    break

    if not hostname:
        # we bail out
        environment = jinja2.Environment()
        template = environment.from_string('No Node is available for this group.')
        access_code = 404
        return template,access_code

    node = Database().get_record_join(['node.*','group.osimageid as grouposimageid'],['group.id=node.groupid'],[f'node.name="{hostname}"'])
    if node:
        data['osimageid'] = node[0]['osimageid'] or node[0]['grouposimageid']
        data['nodename'] = node[0]['name']
#        data['nodehostname'] = node[0]['hostname']
        data['nodehostname'] = node[0]['name'] # + fqdn ?
        data['nodeservice'] = node[0]['service']
        data['nodeid'] = node[0]['id']

    if data['nodeid']:
        nodeinterface_check = Database().get_record_join(['nodeinterface.nodeid as nodeid','nodeinterface.interface'], 
                                                         ['nodeinterface.nodeid=node.id'],
                                                         [f'nodeinterface.macaddress="{mac}"'])
        if nodeinterface_check:
            # this means there is already a node with this mac. let's first check if it's our own.
            if nodeinterface_check[0]['nodeid'] != data['nodeid']:
                # we are NOT !!! though we shouldn't, we will remove the other node's MAC and assign this mac to us.
                # note to other developers: We hard assign a node's IP address (hard config inside image/node) we must be careful - Antoine
                LOGGER.info(f"Warning: node with id {nodeinterface_check[0]['nodeid']} will have its MAC cleared and node {hostname} with id {data['nodeid']} will use MAC {mac}")
                row = [{"column": "macaddress", "value": ""}]
                where = [
                    {"column": "nodeid", "value": nodeinterface_check[0]['nodeid']},
                    {"column": "interface", "value": "BOOTIF"}
                    ]
                result_if=Database().update('nodeinterface', row, where)
                row = [{"column": "macaddress", "value": mac}]
                where = [
                    {"column": "nodeid", "value": data["nodeid"]},
                    {"column": "interface", "value": "BOOTIF"}
                    ]
                result_if=Database().update('nodeinterface', row, where)

        queue_id = Helper().add_task_to_queue('dhcp:restart','service','__internal__')
        if queue_id:
            next_id = Helper().next_task_in_queue('service')
            if queue_id == next_id:
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                executor.submit(Service().service_mother,'dhcp','restart','__internal__')
                executor.shutdown(wait=False)
                #Service().service_mother('dhcp','restart','__internal__')
        else: # fallback, worst case
            response, code = Service().luna_service('dhcp', 'restart')

        nodeinterface = Database().get_record_join(['nodeinterface.nodeid','nodeinterface.interface','nodeinterface.macaddress','ipaddress.ipaddress','network.name as network','network.network as networkip','network.subnet'], 
                                                   ['network.id=ipaddress.networkid','ipaddress.tablerefid=nodeinterface.id'],
                                                   ['tableref="nodeinterface"',f"nodeinterface.nodeid='{data['nodeid']}'",f'nodeinterface.macaddress="{mac}"'])
        if nodeinterface:
            data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
        else:
            #uh oh... no bootif??
            data['nodeip'] = ''

    if data['osimageid']:
        osimage = Database().get_record(None, 'osimage', f' WHERE id = {data["osimageid"]}')
        if osimage:
            if ('kernelfile' in osimage[0]) and (osimage[0]['kernelfile']):
                data['kernelfile'] = f"{osimage[0]['name']}-{osimage[0]['kernelfile']}"
            elif ('kernelversion' in osimage[0]) and (osimage[0]['kernelversion']):
                data['kernelfile'] = f"{osimage[0]['name']}-vmlinuz-{osimage[0]['kernelversion']}"  # RHEL convention. needs revision to allow for distribution switch. pending

            if ('initrdfile' in osimage[0]) and (osimage[0]['initrdfile']):
                data['initrdfile'] = f"{osimage[0]['name']}-{osimage[0]['initrdfile']}"
            elif ('kernelversion' in osimage[0]) and (osimage[0]['kernelversion']):
                data['initrdfile'] = f"{osimage[0]['name']}-initramfs-{osimage[0]['kernelversion']}"

    LOGGER.info(f"manual boot template data: [{data}]")

    if None not in data.values():
        access_code = 200
        Helper().update_nodestate(data["nodeid"], "installer.discovery")
        # reintroduced below section as if we serve files through e.g. nginx, we won't update anything
        row = [{"column": "status", "value": "installer.discovery"}]
        where = [{"column": "id", "value": data['nodeid']}]
        Database().update('node', row, where)
    else:
        environment = jinja2.Environment()
        template = environment.from_string('No Node is available for this mac address.')
        access_code = 404
    LOGGER.info(f'Boot API serving the {template}')
    return render_template(
        template,
        LUNA_CONTROLLER     = data['ipaddress'],
        LUNA_API_PORT       = data['serverport'],
        WEBSERVER_PORT      = data['webserverport'],
        NODE_MAC_ADDRESS    = mac,
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

    template = 'templ_nodeboot.cfg'
    data = {
        'nodeid'        : None,
        'osimageid'     : None,
        'ipaddress'     : None,
        'serverport'    : None,
        'initrdfile'    : None,
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
    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'],['tableref="controller"','controller.hostname="controller"'])
    if controller:
        data['ipaddress'] = controller[0]['ipaddress']
        data['serverport'] = controller[0]['serverport']
        data['webserverport'] = data['serverport']
        if 'WEBSERVER' in CONSTANT.keys():
           if 'PORT' in CONSTANT['WEBSERVER']:
               data['webserverport'] = CONSTANT['WEBSERVER']['PORT']

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
        we_need_dhcpd_restart=False
        nodeinterface_check = Database().get_record_join(['nodeinterface.nodeid as nodeid','nodeinterface.interface'], 
                                                         ['nodeinterface.nodeid=node.id'],
                                                         [f'nodeinterface.macaddress="{mac}"'])
        if nodeinterface_check:
            # this means there is already a node with this mac. let's first check if it's our own.
            if nodeinterface_check[0]['nodeid'] != data['nodeid']:
                # we are NOT !!! though we shouldn't, we will remove the other node's MAC and assign this mac to us.
                # note to other developers: We hard assign a node's IP address (hard config inside image/node) we must be careful - Antoine
                LOGGER.info(f"Warning: node with id {nodeinterface_check[0]['nodeid']} will have its MAC cleared and node {hostname} with id {data['nodeid']} will use MAC {mac}")
                row = [{"column": "macaddress", "value": ""}]
                where = [
                    {"column": "nodeid", "value": nodeinterface_check[0]['nodeid']},
                    {"column": "interface", "value": "BOOTIF"}
                    ]
                result_if=Database().update('nodeinterface', row, where)
                row = [{"column": "macaddress", "value": mac}]
                where = [
                    {"column": "nodeid", "value": data["nodeid"]},
                    {"column": "interface", "value": "BOOTIF"}
                    ]
                result_if=Database().update('nodeinterface', row, where)
                we_need_dhcpd_restart=True
        else:
            # we do not have anyone with this mac yet. we can safely move ahead.
            row = [{"column": "macaddress", "value": mac}]
            where = [
                {"column": "nodeid", "value": data["nodeid"]},
                {"column": "interface", "value": "BOOTIF"}
                ]
            result_if=Database().update('nodeinterface', row, where)
            we_need_dhcpd_restart=True

        if we_need_dhcpd_restart is True:
            queue_id = Helper().add_task_to_queue('dhcp:restart','service','__internal__')
            if queue_id:
                next_id = Helper().next_task_in_queue('service')
                if queue_id == next_id:
                    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                    executor.submit(Service().service_mother,'dhcp','restart','__internal__')
                    executor.shutdown(wait=False)
                    #Service().service_mother('dhcp','restart','__internal__')
            else: # fallback, worst case
                response, code = Service().luna_service('dhcp', 'restart')

        nodeinterface = Database().get_record_join(['nodeinterface.nodeid','nodeinterface.interface','nodeinterface.macaddress','ipaddress.ipaddress','network.name as network','network.network as networkip','network.subnet'], 
                                                   ['network.id=ipaddress.networkid','ipaddress.tablerefid=nodeinterface.id'],
                                                   ['tableref="nodeinterface"',f"nodeinterface.nodeid='{data['nodeid']}'",f'nodeinterface.macaddress="{mac}"'])
        if nodeinterface:
            data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
        else:
            #uh oh... no bootif??
            data['nodeip'] = ''

    if data['osimageid']:
        osimage = Database().get_record(None, 'osimage', f' WHERE id = {data["osimageid"]}')
        if osimage:
            if ('kernelfile' in osimage[0]) and (osimage[0]['kernelfile']):
                data['kernelfile'] = f"{osimage[0]['name']}-{osimage[0]['kernelfile']}"
            elif ('kernelversion' in osimage[0]) and (osimage[0]['kernelversion']):
                data['kernelfile'] = f"{osimage[0]['name']}-vmlinuz-{osimage[0]['kernelversion']}"  # RHEL convention. needs revision to allow for distribution switch. pending

            if ('initrdfile' in osimage[0]) and (osimage[0]['initrdfile']):
                data['initrdfile'] = f"{osimage[0]['name']}-{osimage[0]['initrdfile']}"
            elif ('kernelversion' in osimage[0]) and (osimage[0]['kernelversion']):
                data['initrdfile'] = f"{osimage[0]['name']}-initramfs-{osimage[0]['kernelversion']}"

    LOGGER.info(f"manual boot template data: [{data}]")

    if None not in data.values():
        access_code = 200
        Helper().update_nodestate(data["nodeid"], "installer.discovery")
        # reintroduced below section as if we serve files through e.g. nginx, we won't update anything
        row = [{"column": "status", "value": "installer.discovery"}]
        where = [{"column": "id", "value": data['nodeid']}]
        Database().update('node', row, where)
    else:
        environment = jinja2.Environment()
        template = environment.from_string('No Node is available for this mac address.')
        access_code = 404
    LOGGER.info(f'Boot API serving the {template}')
    return render_template(
        template,
        LUNA_CONTROLLER     = data['ipaddress'],
        LUNA_API_PORT       = data['serverport'],
        WEBSERVER_PORT      = data['webserverport'],
        NODE_MAC_ADDRESS    = mac,
        OSIMAGE_INITRDFILE   = data['initrdfile'],
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
    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'],['tableref="controller"','controller.hostname="controller"'])
    if controller:
        data['ipaddress']   = controller[0]['ipaddress']
        data['serverport']  = controller[0]['serverport']
        data['webserverport'] = data['serverport']
        if 'WEBSERVER' in CONSTANT.keys():
           if 'PORT' in CONSTANT['WEBSERVER']:
               data['webserverport'] = CONSTANT['WEBSERVER']['PORT']
    node_details = Database().get_record_join(['node.*','group.osimageid as grouposimageid'],['group.id=node.groupid'],[f'node.name="{node}"'])
    if node_details:
        if node_details[0]['osimageid']:
            data['osimageid']       = node_details[0]['osimageid']
        else:
            data['osimageid']       = node_details[0]['grouposimageid']
        data['groupid']             = node_details[0]['groupid']
        data['nodename']            = node_details[0]['name']
#        data['nodehostname']        = node_details[0]['hostname']
        data['nodehostname']        = node_details[0]['name'] # + fqdn
        data['nodeid']              = node_details[0]['id']
#        data['unmanaged_bmc_users'] = node_details[0]['unmanaged_bmc_users']
#        data['setupbmc']            = Helper().bool_revert(node_details[0]['setupbmc'])
#        data['localinstall']        = node_details[0]['localinstall']
#        data['prescript']           = node_details[0]['prescript']
#        data['partscript']          = node_details[0]['partscript']
#        data['postscript']          = node_details[0]['postscript']
#        data['netboot']             = node_details[0]['netboot']
#        data['bootmenu']            = node_details[0]['bootmenu']

        items={
           'prescript':'',
           'partscript':"mount -t tmpfs tmpfs /sysroot",
           'postscript':"echo 'tmpfs / tmpfs defaults 0 0' >> /sysroot/etc/fstab",
           'setupbmc':False,
           'netboot':False,
           'localinstall':False,
           'bootmenu':False,
           'provisioninterface':'BOOTIF',
           'unmanaged_bmc_users': '' }

        for item in items.keys():
            data[item] = node_details[0][item]

    if data['groupid']:
        group = Database().get_record(None, 'group', f' WHERE id = {data["groupid"]}')
        if group:
            # below section shows what's configured for the node, or the group, or a default fallback
 
            for item in items.keys():
               if item in data and item in group[0] and group[0][item] and not data[item]:
                   if isinstance(items[item], bool):
                       group[0][item] = str(Helper().make_bool(group[0][item]))
                   data[item] = data[item] or group[0][item] or str(items[item])
               else:
                   if isinstance(items[item], bool):
                       data[item] = str(Helper().make_bool(data[item]))
                   data[item] = data[item] or str(items[item])

#        if group:
#            if data['localinstall'] is None:
#                data['localinstall'] = group[0]['localinstall']
#            if data['unmanaged_bmc_users'] is None:
#                data['unmanaged_bmc_users'] = group[0]['unmanaged_bmc_users']
            
    if data['unmanaged_bmc_users'] is None:
        data['unmanaged_bmc_users'] = ''

#    if data['localinstall'] is None:
#        LOGGER.error('localinstall is not set')
#    else:
#        data['localinstall'] = Helper().bool_revert(data['localinstall'])
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
        WEBSERVER_PORT          = data['webserverport'],
        NODE_HOSTNAME           = data['nodehostname'],
        NODE_NAME               = data['nodename'],
        LUNA_OSIMAGE            = data['osimagename'],
        LUNA_TORRENT            = data['tarball'],  # has to be changed into torrent??
        LUNA_TARBALL            = data['tarball'],
        LUNA_FILE               = data['tarball'],
        LUNA_SELINUX_ENABLED    = data['selinux'],
        LUNA_SETUPBMC           = data['setupbmc'],
        LUNA_BMC                = "empty", # has to contain stuff related to BMC general config like channels e.d.
        LUNA_BOOTLOADER         = data['localinstall'],
        LUNA_LOCALINSTALL       = data['localinstall'],
        LUNA_UNMANAGED_BMC_USERS= data['unmanaged_bmc_users'],
        LUNA_INTERFACES         = data['interfaces'],
        LUNA_PRESCRIPT          = data['prescript'],
        LUNA_PARTSCRIPT         = data['partscript'],
        LUNA_POSTSCRIPT         = data['postscript']
    ), access_code

