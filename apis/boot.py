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
from utils.config import Config
import hashlib
import datetime
import jwt
from common.validate_auth import token_required

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
        protocol = CONSTANT['API']['PROTOCOL']
        webserverport = serverport
        webserverprotocol = protocol
        if 'WEBSERVER' in CONSTANT.keys():
           if 'PORT' in CONSTANT['WEBSERVER']:
               webserverport = CONSTANT['WEBSERVER']['PORT']
           if 'PROTOCOL' in CONSTANT['WEBSERVER']:
               webserverprotocol = CONSTANT['WEBSERVER']['PROTOCOL']

        nodes,availnodes=[],[]
        allnodes = Database().get_record(None, 'node')
        mostnodes = Database().get_record_join(['node.name','nodeinterface.macaddress'], ['nodeinterface.nodeid=node.id'], ["nodeinterface.interface='BOOTIF'"])  # BOOTIF is not entirely true but for now it will do. pending
        allnodes=mostnodes+allnodes
        checked=[]
        if allnodes:
            for node in allnodes:
                if node['name'] not in checked:
                    checked.append(node['name'])
                    nodes.append(node['name'])
                    if (not 'macaddress' in node) or (not node['macaddress']):
                        availnodes.append(node['name'])

        groups=[]
        allgroups=Database().get_record_join(['group.name'], ['osimage.id=group.osimageid'])
        if allgroups:
            for group in allgroups:
                groups.append(group['name'])

        access_code = 200
    else:
        environment = jinja2.Environment()
        template = environment.from_string('No Controller is available.')
        ipaddress, serverport = '', ''
        access_code = 404
    LOGGER.info(f'Boot API serving the {template}')
    return render_template(template, LUNA_CONTROLLER=ipaddress, LUNA_API_PORT=serverport, WEBSERVER_PORT=webserverport, LUNA_API_PROTOCOL=protocol, WEBSERVER_PROTOCOL=webserverprotocol, NODES=nodes, AVAILABLE_NODES=availnodes, GROUPS=groups), access_code


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
        protocol = CONSTANT['API']['PROTOCOL']
        webserverprotocol = protocol
        webserverport = serverport
        if 'WEBSERVER' in CONSTANT.keys():
           if 'PORT' in CONSTANT['WEBSERVER']:
               webserverport = CONSTANT['WEBSERVER']['PORT']
           if 'PROTOCOL' in CONSTANT['WEBSERVER']:
               webserverprotocol = CONSTANT['WEBSERVER']['PROTOCOL']
        access_code = 200
    else:
        environment = jinja2.Environment()
        template = environment.from_string('No Controller is available.')
        ipaddress, serverport = '', ''
        access_code = 404
    LOGGER.info(f'Boot API serving the {template}')
    return render_template(template, LUNA_CONTROLLER=ipaddress, LUNA_API_PORT=serverport, WEBSERVER_PORT=webserverport, LUNA_API_PROTOCOL=protocol, WEBSERVER_PROTOCOL=webserverprotocol), access_code


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
    data['protocol'] = CONSTANT['API']['PROTOCOL']
    data['webserverprotocol'] = data['protocol']
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
           if 'PROTOCOL' in CONSTANT['WEBSERVER']:
               data['webserverprotocol'] = CONSTANT['WEBSERVER']['PROTOCOL']
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
        LUNA_API_PROTOCOL   = data['protocol'],
        WEBSERVER_PORT      = data['webserverport'],
        WEBSERVER_PROTOCOL  = data['webserverprotocol'],
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
    data['protocol'] = CONSTANT['API']['PROTOCOL']
    data['webserverprotocol'] = data['protocol']
    check_template = Helper().checkjinja(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}')
    if not check_template:
        abort(404, 'Empty')
    #Antoine
    networkname=None # used below
    network=None     # used below
    createnode_ondemand = True

    # get controller and cluster info
    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress','network.name as networkname'], ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],['tableref="controller"','controller.hostname="controller"'])
    if controller:
        data['ipaddress'] = controller[0]['ipaddress']
        data['serverport'] = controller[0]['serverport']
        data['webserverport'] = data['serverport']
        if 'WEBSERVER' in CONSTANT.keys():
           if 'PORT' in CONSTANT['WEBSERVER']:
               data['webserverport'] = CONSTANT['WEBSERVER']['PORT']
           if 'PROTOCOL' in CONSTANT['WEBSERVER']:
               data['webserverprotocol'] = CONSTANT['WEBSERVER']['PROTOCOL']
        networkname=controller[0]['networkname']
        cluster=Database().get_record(None,'cluster',f" WHERE id='{controller[0]['clusterid']}'")
        if cluster and 'createnode_ondemand' in cluster[0]:
            createnode_ondemand=Helper().bool_revert(cluster[0]['createnode_ondemand'])

    # clear mac if it already exists. let's check
    nodeinterface_check = Database().get_record_join(['nodeinterface.nodeid as nodeid','nodeinterface.interface'], 
                                                     ['nodeinterface.nodeid=node.id'],
                                                     [f'nodeinterface.macaddress="{mac}"'])
    if nodeinterface_check:
        # this means there is already a node with this mac.
        # though we shouldn't, we will remove the other node's MAC so we can proceed
        LOGGER.warning(f"node with id {nodeinterface_check[0]['nodeid']} will have its MAC cleared and this <to be declared>-node  will use MAC {mac}")
        row = [{"column": "macaddress", "value": ""}]
        where = [{"column": "macaddress", "value": mac}]
        result_if=Database().update('nodeinterface', row, where)

    # then we fetch a list of all nodes that we have, with or without interface config
    list1=Database().get_record_join(['node.*','group.name as groupname','group.provision_interface','nodeinterface.interface','nodeinterface.macaddress'],['nodeinterface.nodeid=node.id','group.id=node.groupid'])
    list2=Database().get_record_join(['node.*','group.name as groupname'],['group.id=node.groupid'])
    list=list1+list2

    # general group info and details. needed below
    groupdetails=Database().get_record(None,'group',f" WHERE name='{groupname}'")
    provision_interface='BOOTIF'
    if groupdetails and 'provision_interface' in groupdetails[0] and groupdetails[0]['provision_interface']:
        provision_interface=str(groupdetails[0]['provision_interface'])

    # things we have to set if we 'clone' or create a node
    items={
       'setupbmc':False,
       'netboot':False,
       'localinstall':False,
       'bootmenu':False,
       'service':False,
       'localboot':False,
    }

    # first we generate a list of taken ips. we might need it later
    ips=[]
    if networkname:
        network = Database().get_record_join(['ipaddress.ipaddress','network.network','network.subnet'], ['network.id=ipaddress.networkid'], [f"network.name='{networkname}'"])
        if network:
            for ip in network:
                ips.append(ip['ipaddress'])

    hostname=None # we use it further down below.
    checked=[]
    if (not list) or (createnode_ondemand is True):
        # we have no spare or free nodes in here -or- we create one on demand.
        newdata={}
        if list2:
            # we fetch the node with highest 'number' - sort
            names=[]
            for node in list2:
                names.append(node['name'])
            names.sort(reverse=True)
         
            example_node=names[0]
            ename=example_node.rstrip('0123456789')  # this assumes a convention like <name><number> as node name
            enumber=example_node[len(ename):]
            if ename and enumber:
                newenumber=str(int(enumber)+1)
                newenumber=newenumber.zfill(len(enumber))
                newdata['name'] = f"{ename}{newenumber}"
            elif ename:
                newenumber='001'
                newdata['name'] = f"{ename}{newenumber}"
            else:  # we have to create a name ourselves
                newdata['name'] = f"{groupname}001"
        else: # we have to create a name ourselves
            newdata['name'] = f"{groupname}001"

        LOGGER.info(f"Group boot intelligence: we came up with the following node name: [{newdata['name']}]")

        # we kinda already do this further down... but i leave it here as it makes sense
        if groupdetails:
            newdata['groupid']=groupdetails[0]['id']

        for item in items:
            if list2 and item in list2[0] and list2[0][item]:  # we copy from another node. not sure if this is really correct. pending
                newdata[item] = list2[0][item]
                if isinstance(items[item], bool):
                    newdata[item] = str(Helper().make_bool(newdata[item]))
            else:
                newdata[item] = items[item]
            if (not newdata[item]) and (item not in items):
                del newdata[item]
        row = Helper().make_rows(newdata)
        nodeid = Database().insert('node', row)

        if nodeid:
            hostname=newdata['name']
            # we need to pick the currect network in a smart way. we assume the default network, the network where controller is in.
            # HOWEVER: we do not copy/create network if options. it's a bit tedious so we leave it here for now as pending. -Antoine
            avail_ip=Helper().get_available_ip(network[0]['network'],network[0]['subnet'],ips)
            result,mesg = Config().node_interface_config(nodeid,provision_interface,mac)
            if result:
                result,mesg = Config().node_interface_ipaddress_config(nodeid,provision_interface,avail_ip,networkname)
            Service().queue('dns','restart')

    else:
        # we already have some nodes in the list. let's see if we can re-use
        for node in list:
            if node['name'] not in checked:
                checked.append(node['name'])
                if 'interface' in node and 'macaddress' in node and not node['macaddress']:
                    # mac is empty. candidate!
                    hostname=node['name']
                    result,mesg = Config().node_interface_config(node['id'],provision_interface,mac)
                    break
                elif not 'interface' in node:
                    # node is there but no interface. we'll take it!
                    hostname=node['name']
                    # we need to pick the currect network in a smart way. we assume the default network where controller is in as well
                    avail_ip=Helper().get_available_ip(network[0]['network'],network[0]['subnet'],ips)
                    result,mesg = Config().node_interface_config(node['id'],provision_interface,mac)
                    if result:
                        result,mesg = Config().node_interface_ipaddress_config(node['id'],provision_interface,avail_ip,networkname)
                        Service().queue('dns','restart')
                    break

    if not hostname:
        # we bail out because we could not re-use a node or create one. something above did not work out.
        environment = jinja2.Environment()
        template = environment.from_string('No Node is available for this group.')
        access_code = 404
        return template,access_code

    # we update the groupid of the node. this is actually only really needed if we re-use a node (unassigned)
    if groupdetails:
        row = [{"column": "groupid", "value": groupdetails[0]['id']}]
        where = [{"column": "name", "value": hostname}]
        Database().update('node', row, where)

    # below here is almost identical to a manual node selection boot -------------------------------------------

    node = Database().get_record_join(['node.*','group.osimageid as grouposimageid'],['group.id=node.groupid'],[f'node.name="{hostname}"'])
    if node:
        data['osimageid'] = node[0]['osimageid'] or node[0]['grouposimageid']
        data['nodename'] = node[0]['name']
#        data['nodehostname'] = node[0]['hostname']
        data['nodehostname'] = node[0]['name'] # + fqdn ?
        data['nodeservice'] = node[0]['service']
        data['nodeid'] = node[0]['id']

    if data['nodeid']:

        Service().queue('dhcp','restart')

        nodeinterface = Database().get_record_join(['nodeinterface.nodeid','nodeinterface.interface','nodeinterface.macaddress','ipaddress.ipaddress','network.name as network','network.network as networkip','network.subnet'], 
                                                   ['network.id=ipaddress.networkid','ipaddress.tablerefid=nodeinterface.id'],
                                                   ['tableref="nodeinterface"',f"nodeinterface.nodeid='{data['nodeid']}'",f'nodeinterface.macaddress="{mac}"'])
        if nodeinterface:
            data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
        else:
            #uh oh... no bootif??
            data['nodeip'] = None

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

    LOGGER.info(f"manual group boot template data: [{data}]")

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
        LUNA_API_PROTOCOL   = data['protocol'],
        WEBSERVER_PORT      = data['webserverport'],
        WEBSERVER_PROTOCOL  = data['webserverprotocol'],
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
    data['protocol'] = CONSTANT['API']['PROTOCOL']
    data['webserverprotocol'] = data['protocol']
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
           if 'PROTOCOL' in CONSTANT['WEBSERVER']:
               data['webserverprotocol'] = CONSTANT['WEBSERVER']['PROTOCOL']

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
                    {"column": "interface", "value": nodeinterface_check[0]['interface']}
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
            Service().queue('dhcp','restart')

        nodeinterface = Database().get_record_join(['nodeinterface.nodeid','nodeinterface.interface','nodeinterface.macaddress','ipaddress.ipaddress','network.name as network','network.network as networkip','network.subnet'], 
                                                   ['network.id=ipaddress.networkid','ipaddress.tablerefid=nodeinterface.id'],
                                                   ['tableref="nodeinterface"',f"nodeinterface.nodeid='{data['nodeid']}'",f'nodeinterface.macaddress="{mac}"'])
        if nodeinterface:
            data['nodeip'] = f'{nodeinterface[0]["ipaddress"]}/{nodeinterface[0]["subnet"]}'
        else:
            #uh oh... no bootif??
            data['nodeip'] = None

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

    LOGGER.info(f"manual node boot template data: [{data}]")

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
        LUNA_API_PROTOCOL   = data['protocol'],
        WEBSERVER_PORT      = data['webserverport'],
        WEBSERVER_PROTOCOL  = data['webserverprotocol'],
        NODE_MAC_ADDRESS    = mac,
        OSIMAGE_INITRDFILE   = data['initrdfile'],
        OSIMAGE_KERNELFILE  = data['kernelfile'],
        NODE_NAME           = data['nodename'],
        NODE_HOSTNAME       = data['nodehostname'],
        NODE_SERVICE        = data['nodeservice'],
        NODE_IPADDRESS      = data['nodeip']
    ), access_code


@boot_blueprint.route('/boot/install/<string:node>', methods=['GET'])
@token_required
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
        'interfaces'            : {},
        'bmc'                   : {}
    }
    data['protocol'] = CONSTANT['API']['PROTOCOL']
    data['webserverprotocol'] = data['protocol']
    template = 'templ_install.cfg'
    check_template = Helper().checkjinja(f'{CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{template}')
    if not check_template:
        abort(404, 'Empty')

    cluster = Database().get_record(None, 'cluster', None)
    if cluster:
        data['selinux']      = Helper().bool_revert(cluster[0]['security'])
        data['cluster_provision_method']   = cluster[0]['provision_method']
        data['cluster_provision_fallback'] = cluster[0]['provision_fallback']
    #Antoine
    controller = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id'],['tableref="controller"','controller.hostname="controller"'])
    if controller:
        data['ipaddress']   = controller[0]['ipaddress']
        data['serverport']  = controller[0]['serverport']
        data['webserverport'] = data['serverport']
        if 'WEBSERVER' in CONSTANT.keys():
           if 'PORT' in CONSTANT['WEBSERVER']:
               data['webserverport'] = CONSTANT['WEBSERVER']['PORT']
           if 'PROTOCOL' in CONSTANT['WEBSERVER']:
               data['webserverprotocol'] = CONSTANT['WEBSERVER']['PROTOCOL']
    node_details = Database().get_record_join(['node.*','group.osimageid as grouposimageid','group.name as groupname','group.bmcsetupid as groupbmcsetupid'],['group.id=node.groupid'],[f'node.name="{node}"'])
    if node_details:
        # ---
        if node_details[0]['osimageid']:
            data['osimageid']       = node_details[0]['osimageid']
        else:
            data['osimageid']       = node_details[0]['grouposimageid']
        # ---
        if node_details[0]['bmcsetupid']:
            data['bmcsetupid']       = node_details[0]['bmcsetupid']
        else:
            data['bmcsetupid']       = node_details[0]['groupbmcsetupid']
        # ---
        data['groupid']             = node_details[0]['groupid']
        data['groupname']           = node_details[0]['groupname']
        data['nodename']            = node_details[0]['name']
        data['nodehostname']        = node_details[0]['name'] # + fqdn further below
        data['nodeid']              = node_details[0]['id']
        data['provision_method']    = node_details[0]['provision_method']
        data['provision_fallback']  = node_details[0]['provision_fallback']

        items={
           'prescript':'',
           'partscript':"bW91bnQgLXQgdG1wZnMgdG1wZnMgL3N5c3Jvb3QK",
           'postscript':"ZWNobyAndG1wZnMgLyB0bXBmcyBkZWZhdWx0cyAwIDAnID4+IC9zeXNyb290L2V0Yy9mc3RhYgo=",
           'setupbmc':False,
           'netboot':False,
           'localinstall':False,
           'bootmenu':False,
           'provision_interface':'BOOTIF',
           'unmanaged_bmc_users': 'skip',
           'provision_method': data['cluster_provision_method'],
           'provision_fallback': data['cluster_provision_fallback'] }

        for item in items.keys():
            data[item] = node_details[0][item]
            if isinstance(items[item], bool):
                data[item] = Helper().make_bool(data[item])

    if data['setupbmc'] is True and data['bmcsetupid']:
        bmcsetup = Database().get_record(None, 'bmcsetup', f" WHERE id = {data['bmcsetupid']}")
        if bmcsetup:
            data['bmc']={}
            data['bmc']['userid']=bmcsetup[0]['userid']
            data['bmc']['username']=bmcsetup[0]['username']
            data['bmc']['password']=bmcsetup[0]['password']
            data['bmc']['netchannel']=bmcsetup[0]['netchannel']
            data['bmc']['mgmtchannel']=bmcsetup[0]['mgmtchannel']
            data['unmanaged_bmc_users']=bmcsetup[0]['unmanaged_bmc_users']
        else:
            data['setupbmc']=False

    if data['groupid']:
        group = Database().get_record(None, 'group', f' WHERE id = {data["groupid"]}')
        if group:
            # below section shows what's configured for the node, or the group, or a default fallback
 
            for item in items.keys():
               if item in data and item in group[0] and group[0][item] and not str(data[item]):
                   # we check if we have data filled. if not (meaning node does not have that info) we verify if the group has it and if so, we fill it
                   if isinstance(items[item], bool):
                       group[0][item] = Helper().make_bool(group[0][item])
                   data[item] = data[item] or group[0][item] or items[item]
               elif str(data[item]) and data[item] is not None:
                   pass
               else:
                   # if anything else fails we use the fallback
                   if isinstance(items[item], bool):
                       data[item] = Helper().make_bool(data[item])
                   data[item] = items[item]

    if data['osimageid']:
        osimage = Database().get_record(None, 'osimage', f' WHERE id = {data["osimageid"]}')
        if osimage:
            data['osimagename'] = osimage[0]['name']
            data['tarball'] = osimage[0]['tarball']
            data['torrent'] = osimage[0]['torrent']
            data['distribution'] = osimage[0]['distribution'].lower() or 'redhat'

    if data['nodeid']:
        nodeinterface = Database().get_record_join(['nodeinterface.nodeid','nodeinterface.interface','nodeinterface.macaddress','nodeinterface.options','ipaddress.ipaddress','network.name as network','network.network as networkip','network.subnet','network.gateway','network.id as networkid'], ['network.id=ipaddress.networkid','ipaddress.tablerefid=nodeinterface.id'],['tableref="nodeinterface"',f"nodeinterface.nodeid='{data['nodeid']}'"])
        if nodeinterface:
            for nwkif in nodeinterface:
                node_nwk = f'{nwkif["ipaddress"]}/{nwkif["subnet"]}'
                netmask=Helper().get_netmask(node_nwk)
                if nwkif['interface'] == 'BMC': 
                    # we configure bmc stuff here and no longer in template. big advantage is that we can have different networks/interface-names for different h/w, drivers, subnets, networks, etc
                    if 'bmc' in data.keys():
                        data['bmc']['ipaddress'] = nwkif['ipaddress']
                        data['bmc']['netmask'] = netmask
                        data['bmc']['gateway'] = nwkif['gateway'] or '0.0.0.0'  # <---- not ipv6 compliant! pending
                else:
                    # regular nic
                    data['interfaces'][nwkif['interface']] = {}
                    data['interfaces'][nwkif['interface']]['interface'] = nwkif['interface']
                    data['interfaces'][nwkif['interface']]['ipaddress'] = nwkif['ipaddress']
                    data['interfaces'][nwkif['interface']]['network'] = node_nwk
                    data['interfaces'][nwkif['interface']]['netmask'] = netmask
                    data['interfaces'][nwkif['interface']]['networkname'] = nwkif['network']
                    data['interfaces'][nwkif['interface']]['gateway'] = nwkif['gateway']
                    data['interfaces'][nwkif['interface']]['options'] = nwkif['options'] or ""
                    if nwkif['interface'] == data['provision_interface'] and nwkif['network']: # if it is my prov interf then it will get that domain as a FQDN.
                        data['nodehostname'] = data['nodename'] + '.' + nwkif['network']

    LOGGER.info(f"boot install data: [{data}]")
    if None not in data.values():
        access_code = 200
        Helper().update_nodestate(data["nodeid"], "installer.downloaded")
    else:
        environment = jinja2.Environment()
        template = environment.from_string('No Node is available for this mac address.')
        access_code = 500

    jwt_token=None
    try:
        api_key = CONSTANT['API']['SECRET_KEY']
        api_expiry = datetime.timedelta(minutes=int(CONSTANT['API']['EXPIRY']))
        api_expiry = datetime.timedelta(minutes=int(60))
        expiry_time = datetime.datetime.utcnow() + api_expiry
        jwt_token = jwt.encode({'id': 0, 'exp': expiry_time}, api_key, 'HS256')
    except Exception as exp:
        LOGGER.info(f"Token creation error: {exp}")

    return render_template(
        template,
        LUNA_CONTROLLER         = data['ipaddress'],
        LUNA_API_PORT           = data['serverport'],
        LUNA_API_PROTOCOL       = data['protocol'],
        WEBSERVER_PORT          = data['webserverport'],
        WEBSERVER_PROTOCOL      = data['webserverprotocol'],
        NODE_HOSTNAME           = data['nodehostname'],
        NODE_NAME               = data['nodename'],
        LUNA_OSIMAGE            = data['osimagename'],
        LUNA_DISTRIBUTION       = data['distribution'],
        LUNA_TORRENT            = data['torrent'],
        LUNA_TARBALL            = data['tarball'],
        LUNA_FILE               = data['tarball'],
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
        LUNA_TOKEN              = jwt_token
    ), access_code


