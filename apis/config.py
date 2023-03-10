#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This File is a A Entry Point of Every Configuration Related Activity.
###@token_required is a Wrapper Method to Validate the POST API. It contains
arguments and keyword arguments Of The API
"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

from flask import Blueprint, request, json
from utils.database import Database
from utils.log import Log
from utils.helper import Helper
from common.validate_auth import token_required
from common.constant import CONFIGFILE
from random import randint
from time import sleep,time
from os import getpid
import concurrent.futures
from utils.osimage import OsImage
from utils.config import Config

LOGGER = Log.get_logger()
config_blueprint = Blueprint('config', __name__)

############################# Node configuration #############################

@config_blueprint.route('/config/node', methods=['GET'])
###@token_required
def config_node():
    """
    Input - None
    Output - Return the list of nodes.
    """
    # ---------------------------- NOTE NOTE NOTE ---------------------------
    # we need two queries as a join is great but not holy. as soon as we know the absolute minimum/mandatory field/attributes for a node we can finetune
    # this is also for the other functions/methods/or_whatever_you_call_These_in_python down below. it needs updating or finetuning. pending. -Antoine
    # -----------------------------------------------------------------------
    nodes = Database().get_record(None, 'node', None)
    nodesfull = Database().get_record_join(['node.*','group.name AS group','osimage.name AS osimage'], ['group.id=node.groupid','osimage.id=group.osimageid'])
    nodes+=nodesfull
    if nodes:
        response = {'config': {'node': {} }}
        for node in nodes:
            node_name = node['name']
            nodeid = node['id']
#            if node['bmcsetupid']:
#                node['bmcsetup'] = Database().getname_byid('bmcsetup', node['bmcsetupid'])
#            if node['groupid']:
#                node['group'] = Database().getname_byid('group', node['groupid'])
#            if node['osimageid']:
#                node['osimage'] = Database().getname_byid('osimage', node['osimageid'])
            if node['switchid']:
                node['switch'] = Database().getname_byid('switch', node['switchid'])
            # del node['name']
            del node['id']
            del node['bmcsetupid']
            del node['groupid']
            del node['osimageid']
            del node['switchid']
            node['bootmenu'] = Helper().bool_revert(node['bootmenu'])
            node['localboot'] = Helper().bool_revert(node['localboot'])
            node['localinstall'] = Helper().bool_revert(node['localinstall'])
            node['netboot'] = Helper().bool_revert(node['netboot'])
            node['service'] = Helper().bool_revert(node['service'])
            node['setupbmc'] = Helper().bool_revert(node['setupbmc'])
            node_interface = Database().get_record_join(['nodeinterface.interface','ipaddress.ipaddress','nodeinterface.macaddress','network.name as network'], ['network.id=ipaddress.networkid','ipaddress.tablerefid=nodeinterface.id'],['tableref="nodeinterface"',f"nodeinterface.nodeid='{nodeid}'"])
            if node_interface:
                node['interfaces'] = []
                for interface in node_interface:
                    node['interfaces'].append(interface)
            response['config']['node'][node_name] = node
        LOGGER.info('Provided list of all nodes.')
        access_code = 200
    else:
        LOGGER.error('No nodes are available.')
        response = {'message': 'No nodes are available.'}
        access_code = 404
    LOGGER.info(f"my response: [{response}]")
    return json.dumps(response), access_code


@config_blueprint.route('/config/node/<string:name>', methods=['GET'])
###@token_required
def config_node_get(name=None):
    """
    Input - None
    Output - Return the node information.
    """
    nodes = Database().get_record(None, 'node', f' WHERE name = "{name}"')
    nodefull = Database().get_record_join(['node.*',
                                           'group.name AS group',
                                           'osimage.name AS group_osimage',
                                           'group.bmcsetupid AS group_bmcsetupid',
                                           'group.prescript AS group_prescript',
                                           'group.partscript AS group_partscript',
                                           'group.postscript AS group_postscript',
                                           'group.netboot AS group_netboot',
                                           'group.localinstall AS group_localinstall',
                                           'group.bootmenu AS group_bootmenu',
                                           'group.provisioninterface AS group_provisioninterface'], ['group.id=node.groupid','osimage.id=group.osimageid'],f"node.name='{name}'")
    nodes[0].update(nodefull[0])
    node=nodes[0]
    if node:
        response = {'config': {'node': {} }}
        nodename = node['name']
        nodeid = node['id']

        if node['bmcsetupid']:
            node['bmcsetup'] = Database().getname_byid('bmcsetup', node['bmcsetupid'])
        elif node['group_bmcsetupid']:
            node['bmcsetup']= Database().getname_byid('bmcsetup', node['group_bmcsetupid']) + f" ({node['group']})"
        del node['group_bmcsetupid']

        if node['osimageid']:
            node['osimage'] = Database().getname_byid('osimage', node['osimageid'])
        elif node['group_osimage']:
            node['osimage']=node['group_osimage']+f" ({node['group']})"
        del node['group_osimage']

        if node['switchid']:
            node['switch'] = Database().getname_byid('switch', node['switchid'])

        # below section shows what's configured for the node, or the group, or a default fallback

        items={
           'prescript':'<empty>',
           'partscript':'<empty>',
           'postscript':'<empty>',
           'netboot':False,
           'localinstall':False,
           'bootmenu':False,
           'provisioninterface':'BOOTIF'}

        for item in items.keys():
           if 'group_'+item in node and node['group_'+item] and not node[item]:
               if isinstance(items[item], bool):
                   node['group_'+item] = str(Helper().make_bool(node['group_'+item]))
               node['group_'+item] += f" ({node['group']})"
               node[item] = node[item] or node['group_'+item] or str(items[item]+' (default)')
           else:
               if isinstance(items[item], bool):
                   node[item] = str(Helper().make_bool(node[item]))
               node[item] = node[item] or str(items[item]+' (default)')
           if 'group_'+item in node:
               del node['group_'+item]

        del node['id']
        del node['bmcsetupid']
        del node['groupid']
        del node['osimageid']
        del node['switchid']
        node['service'] = Helper().make_bool(node['service'])
        node['setupbmc'] = Helper().make_bool(node['setupbmc'])
        node['localboot'] = Helper().make_bool(node['localboot'])

        node_interface = Database().get_record_join(['nodeinterface.interface','ipaddress.ipaddress','nodeinterface.macaddress','network.name as network'], ['network.id=ipaddress.networkid','ipaddress.tablerefid=nodeinterface.id'],['tableref="nodeinterface"',f"nodeinterface.nodeid='{nodeid}'"])
        if node_interface:
            node['interfaces'] = []
            for interface in node_interface:
                interfacename,*_ = (node['provisioninterface'].split(' ')+[None]) # we skim off parts that we added for clarity in above section (e.g. (default)). also works if there's no additional info
                if interface['interface'] == interfacename and interface['network']: # if it is my prov interf then it will get that domain as a FQDN.
                    node['hostname'] = nodename + '.' + interface['network']
                node['interfaces'].append(interface)
        response['config']['node'][nodename] = node
        LOGGER.info('Provided list of all nodes.')
        access_code = 200
    else:
        LOGGER.error(f'Node {name} is not available.')
        response = {'message': f'Node {name} is not available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route('/config/node/<string:name>', methods=['POST'])
@token_required
def config_node_post(name=None):
    """
    Input - Node name
    Process - Create or update the groups.
    Output - Node information.
    """
    data = {}
    create, update = False, False

    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        if 'node' not in request_data['config'].keys():
            response = {'message': 'Bad Request.'}
            access_code = 400
            return json.dumps(response), access_code

        data = request_data['config']['node'][name]
        node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if node:
            nodeid = node[0]['id']
            if 'newnodename' in data:  # is mentioned as newhostname in design documents!
                nodename_new = data['newnodename']
                where = f' WHERE `name` = "{nodename_new}"'
                newnode_check = Database().get_record(None, 'node', where)
                if newnode_check:
                    response = {'message': f'{nodename_new} already present in database.'}
                    access_code = 400
                    return json.dumps(response), access_code
                else:
                    data['name'] = data['newnodename']
                    del data['newnodename']
            update = True
            if 'bootmenu' in data:
                data['bootmenu'] = Helper().bool_revert(data['bootmenu'])
            if 'localboot' in data:
                data['localboot'] = Helper().bool_revert(data['localboot'])
            if 'localinstall' in data:
                data['localinstall'] = Helper().bool_revert(data['localinstall'])
            if 'netboot' in data:
                data['netboot'] = Helper().bool_revert(data['netboot'])
            if 'service' in data:
                data['service'] = Helper().bool_revert(data['service'])
            if 'setupbmc' in data:
                data['setupbmc'] = Helper().bool_revert(data['setupbmc'])
        else:
            if 'newnodename' in data:
                response = {'message': f'{nodename_new} is not allwoed while creating a new node.'}
                access_code = 400
                return json.dumps(response), access_code
            if 'bootmenu' in data:
                data['bootmenu'] = Helper().bool_revert(data['bootmenu'])
            else:
                data['bootmenu'] = 0
            if 'localboot' in data:
                data['localboot'] = Helper().bool_revert(data['localboot'])
            else:
                data['localboot'] = 0
            if 'localinstall' in data:
                data['localinstall'] = Helper().bool_revert(data['localinstall'])
            else:
                data['localinstall'] = 0
            if 'netboot' in data:
                data['netboot'] = Helper().bool_revert(data['netboot'])
            else:
                data['netboot'] = 0
            if 'service' in data:
                data['service'] = Helper().bool_revert(data['service'])
            else:
                data['service'] = 0
            if 'setupbmc' in data:
                data['setupbmc'] = Helper().bool_revert(data['setupbmc'])
            else:
                data['setupbmc'] = 0
            create = True

        if 'bmcsetup' in data:
            bmc_name = data['bmcsetup']
            del data['bmcsetup']
            data['bmcsetupid'] = Database().getid_byname('bmcsetup', bmc_name)
        if 'group' in data:
            group_name = data['group']
            del data['group']
            data['groupid'] = Database().getid_byname('group', group_name)
        if 'osimage' in data:
            osimage_name = data['osimage']
            del data['osimage']
            data['osimageid'] = Database().getid_byname('osimage', osimage_name)
        if 'switch' in data:
            switch_name = data['switch']
            del data['switch']
            data['switchid'] = Database().getid_byname('switch', switch_name)

        if 'interfaces' in data:
            interfaces = data['interfaces']
            del data['interfaces']

        node_columns = Database().get_columns('node')
        columns_check = Helper().checkin_list(data, node_columns)
        if columns_check:
            if update:
                where = [{"column": "id", "value": nodeid}]
                row = Helper().make_rows(data)
                Database().update('node', row, where)
                response = {'message': f'Node {name} updated successfully.'}
                access_code = 204
            if create:
                data['name'] = name
                row = Helper().make_rows(data)
                nodeid = Database().insert('node', row)
                response = {'message': f'Node {name} created successfully.'}
                access_code = 201
            if interfaces:
                access_code = 204
                for interface in interfaces:
                    # Antoine
                    interface_name = interface['interface']
                    macaddress,network=None,None
                    if 'macaddress' in interface.keys():
                        macaddress=interface['macaddress']
                    result,mesg = Config().node_interface_config(nodeid,interface_name,macaddress)
                    if result and 'ipaddress' in interface.keys():
                        ipaddress=interface['ipaddress']
                        if 'network' in interface.keys():
                            network=interface['network']
                        result,mesg = Config().node_interface_ipaddress_config(nodeid,interface_name,ipaddress,network)

                    if result is False:
                        response = {'message': f"{mesg}"}
                        access_code = 500
                        return json.dumps(response), access_code

        else:
            response = {'message': 'Bad Request; Columns are incorrect.'}
            access_code = 400
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route('/config/node/<string:name>/_delete', methods=['GET'])
@token_required
def config_node_delete(name=None):
    """
    Input - Node Name
    Process - Delete the Node and it's interfaces.
    Output - Success or Failure.
    """
    node = Database().get_record(None, 'node', f' WHERE `name` = "{name}"')
    if node:
        nodeid=node[0]['id']
        Database().delete_row('node', [{"column": "name", "value": name}])
        ipaddress = Database().get_record_join(['ipaddress.id'], ['ipaddress.tablerefid=nodeinterface.id'], ['tableref="nodeinterface"',f"nodeinterface.nodeid='{nodeid}'"])
        if ipaddress:
            for ip in ipaddress:
                Database().delete_row('ipaddress', [{"column": "id", "value": ip['id']}])
        Database().delete_row('nodeinterface', [{"column": "nodeid", "value": nodeid}])
        Database().delete_row('nodesecrets', [{"column": "nodeid", "value": nodeid}])
        response = {'message': f'Node {name} with all its interfaces removed.'}
        access_code = 204
    else:
        response = {'message': f'Node {name} not present in database.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route('/config/node/<string:name>/interfaces', methods=['GET'])
###@token_required
def config_node_get_interfaces(name=None):
    """
    Input - Node Name
    Process - Fetch the Node Interface List.
    Output - Node Interface List.
    """
    node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
    if node:
        response = {'config': {'node': {name: {'interfaces': [] } } } }
        nodeid = node[0]['id']
        node_interfaces = Database().get_record_join(['network.name as network','nodeinterface.macaddress','nodeinterface.interface','ipaddress.ipaddress'], ['ipaddress.tablerefid=nodeinterface.id','network.id=ipaddress.networkid'], ['tableref="nodeinterface"',f"nodeinterface.nodeid='{nodeid}'"])
        if node_interfaces:
            my_interface = []
            for interface in node_interfaces:
                my_interface.append(interface)
                response['config']['node'][name]['interfaces'] = my_interface

            LOGGER.info(f'Returned group {name} with details.')
            access_code = 200
        else:
            LOGGER.error(f'Node {name} dont have any interface.')
            response = {'message': f'Node {name} dont have any interface.'}
            access_code = 404
    else:
        LOGGER.error('No nodes are available.')
        response = {'message': 'No nodes are available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/node/<string:name>/interfaces", methods=['POST'])
@token_required
def config_node_post_interfaces(name=None):
    """
    Input - Node Name
    Process - Create Or Update The Node Interface.
    Output - Node Interface.
    """
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if node:
            nodeid = node[0]['id']


            if 'interfaces' in request_data['config']['node'][name]:
                for interface in request_data['config']['node'][name]['interfaces']:
                    # Antoine
                    interface_name = interface['interface']
                    macaddress,network=None,None
                    if 'macaddress' in interface.keys():
                        macaddress=interface['macaddress']
                    result,mesg = Config().node_interface_config(nodeid,interface_name,macaddress)
                    if result and 'ipaddress' in interface.keys():
                        ipaddress=interface['ipaddress']
                        if 'network' in interface.keys():
                            network=interface['network']
                        result,mesg = Config().node_interface_ipaddress_config(nodeid,interface_name,ipaddress,network)

                    if result is False:
                        response = {'message': f"{mesg}"}
                        access_code = 500
                    else :
                        response = {'message': 'Interface updated.'}
                        access_code = 204
            else:
                LOGGER.error('Kindly provide the interface.')
                response = {'message': 'Kindly provide the interface.'}
                access_code = 404
        else:
            LOGGER.error(f'Node {name} is not available.')
            response = {'message': f'Node {name} is not available.'}
            access_code = 404
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route("/config/node/<string:name>/interfaces/<string:interface>", methods=['GET'])
###@token_required
def config_node_interface_get(name=None, interface=None):
    """
    Input - Node Name & Interface Name
    Process - Get the Node Interface.
    Output - Success or Failure.
    """
    node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
    if node:
        response = {'config': {'node': {name: {'interfaces': [] } } } }
        nodeid = node[0]['id']
        node_interfaces = Database().get_record_join(['network.name as network','nodeinterface.macaddress','nodeinterface.interface','ipaddress.ipaddress'], ['ipaddress.tablerefid=nodeinterface.id','network.id=ipaddress.networkid'], ['tableref="nodeinterface"',f"nodeinterface.nodeid='{nodeid}'"])
        if node_interfaces:
            my_interface = []
            for interface in node_interfaces:
                my_interface.append(interface)
                response['config']['node'][name]['interfaces'] = my_interface

            LOGGER.info(f'Returned group {name} with details.')
            access_code = 200
        else:
            LOGGER.error(f'Node {name} dont have {interface} interface.')
            response = {'message': f'Node {name} dont have {interface} interface.'}
            access_code = 404
    else:
        LOGGER.error('Node is not available.')
        response = {'message': 'Node is not available.'}
        access_code = 404
    return json.dumps(response), access_code



@config_blueprint.route("/config/node/<string:name>/interfaces/<string:interface>/_delete", methods=['GET'])
@token_required
def config_node_delete_interface(name=None, interface=None):
    """
    Input - Node Name & Interface Name
    Process - Delete the Node Interface.
    Output - Success or Failure.
    """
    node = Database().get_record(None, 'node', f' WHERE `name` = "{name}"')
    if node:
        nodeid = node[0]['id']
        where = f' WHERE `interface` = "{interface}" AND `nodeid` = "{nodeid}"'
        node_interface = Database().get_record_join(['nodeinterface.id as ifid','ipaddress.id as ipid'], ['ipaddress.tablerefid=nodeinterface.id'], ['tableref="nodeinterface"',f"nodeinterface.nodeid='{nodeid}'",f"nodeinterface.interface='{interface}'"])
        if node_interface:
            where = [{"column": "id", "value": node_interface[0]['ipid']}]
            Database().delete_row('ipaddress', where)
            where = [{"column": "id", "value": node_interface[0]['ifid']}]
            Database().delete_row('nodeinterface', where)
            response = {'message': f'Node {name} interface {interface} removed successfully.'}
            access_code = 204
        else:
            response = {'message': f'Node {name} interface {interface} not present in database.'}
            access_code = 404
    else:
        response = {'message': f'Node {name} not present in database.'}
        access_code = 404
    return json.dumps(response), access_code

############################# Group configuration #############################

@config_blueprint.route("/config/group", methods=['GET'])
###@token_required
def config_group():
    """
    Input - Group Name
    Process - Fetch the Group information.
    Output - Group Info.
    """
    groups = Database().get_record(None, 'group', None)
    if groups:
        response = {'config': {'group': {} }}
        for grp in groups:
            grpname = grp['name']
            grpid = grp['id']
            where = f' WHERE groupid = "{grpid}"'
            grp_interface = Database().get_record(None, 'groupinterface', where)
            if grp_interface:
                grp['interfaces'] = []
                for ifx in grp_interface:
                    ifx['network'] = Database().getname_byid('network', ifx['networkid'])
                    del ifx['groupid']
                    del ifx['id']
                    del ifx['networkid']
                    grp['interfaces'].append(ifx)
            del grp['id']
            # del grp['name']
            grp['bmcsetup'] = Helper().bool_revert(grp['bmcsetup'])
            grp['netboot'] = Helper().bool_revert(grp['netboot'])
            grp['localinstall'] = Helper().bool_revert(grp['localinstall'])
            grp['bootmenu'] = Helper().bool_revert(grp['bootmenu'])
            grp['osimage'] = Database().getname_byid('osimage', grp['osimageid'])
            del grp['osimageid']
            if grp['bmcsetupid']:
                grp['bmcsetupname'] = Database().getname_byid('bmcsetup', grp['bmcsetupid'])
            del grp['bmcsetupid']
            response['config']['group'][grpname] = grp
        LOGGER.info('Provided list of all groups with details.')
        access_code = 200
    else:
        LOGGER.error('No group is available.')
        response = {'message': 'No group is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/group/<string:name>", methods=['GET'])
###@token_required
def config_group_get(name=None):
    """
    Input - Group Name
    Process - Fetch the Group information.
    Output - Group Info.
    """
    groups = Database().get_record(None, 'group', f' WHERE name = "{name}"')
    if groups:
        response = {'config': {'group': {} }}
        for grp in groups:
            grpname = grp['name']
            grpid = grp['id']
            where = f' WHERE groupid = "{grpid}"'
            grp_interface = Database().get_record(None, 'groupinterface', where)
            if grp_interface:
                grp['interfaces'] = []
                for ifx in grp_interface:
                    ifx['network'] = Database().getname_byid('network', ifx['networkid'])
                    del ifx['groupid']
                    del ifx['id']
                    del ifx['networkid']
                    grp['interfaces'].append(ifx)
            del grp['id']
            # del grp['name']
            grp['bmcsetup'] = Helper().bool_revert(grp['bmcsetup'])
            grp['netboot'] = Helper().bool_revert(grp['netboot'])
            grp['localinstall'] = Helper().bool_revert(grp['localinstall'])
            grp['bootmenu'] = Helper().bool_revert(grp['bootmenu'])
            grp['osimage'] = Database().getname_byid('osimage', grp['osimageid'])
            del grp['osimageid']
            if grp['bmcsetupid']:
                grp['bmcsetupname'] = Database().getname_byid('bmcsetup', grp['bmcsetupid'])
            del grp['bmcsetupid']
            response['config']['group'][grpname] = grp
        LOGGER.info(f'Returned Group {name} with Details.')
        access_code = 200
    else:
        LOGGER.error('No group is available.')
        response = {'message': 'No group is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/group/<string:name>", methods=['POST'])
###@token_required
def config_group_post(name=None):
    """
    Input - Group ID or Name
    Process - Create Or Update The Groups.
    Output - Group Information.
    """
    data = {}
    create, update = False, False

    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['group'][name]
        grp = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if grp:
            grpid = grp[0]['id']
            if 'newgroupname' in data:
                newgrpname = data['newgroupname']
                where = f' WHERE `name` = "{newgrpname}"'
                checknewgrp = Database().get_record(None, 'group', where)
                if checknewgrp:
                    response = {'message': f'{newgrpname} Already present in database.'}
                    access_code = 400
                    return json.dumps(response), access_code
                else:
                    data['name'] = data['newgroupname']
                    del data['newgroupname']
            update = True
            if 'bmcsetup' in data:
                data['bmcsetup'] = Helper().bool_revert(data['bmcsetup'])
            if 'netboot' in data:
                data['netboot'] = Helper().bool_revert(data['netboot'])
            if 'localinstall' in data:
                data['localinstall'] = Helper().bool_revert(data['localinstall'])
            if 'bootmenu' in data:
                data['bootmenu'] = Helper().bool_revert(data['bootmenu'])
        else:
            if 'newgroupname' in data:
                response = {'message': f'{newgrpname} is not allwoed while creating a new group.'}
                access_code = 400
                return json.dumps(response), access_code
            if 'bmcsetup' in data:
                data['bmcsetup'] = Helper().bool_revert(data['bmcsetup'])
            else:
                data['bmcsetup'] = 0
            if 'netboot' in data:
                data['netboot'] = Helper().bool_revert(data['netboot'])
            else:
                data['netboot'] = 0
            if 'localinstall' in data:
                data['localinstall'] = Helper().bool_revert(data['localinstall'])
            else:
                data['localinstall'] = 0
            if 'bootmenu' in data:
                data['bootmenu'] = Helper().bool_revert(data['bootmenu'])
            else:
                data['bootmenu'] = 0
            create = True
        if 'bmcsetupname' in data:
            bmcname = data['bmcsetupname']
            data['bmcsetupid'] = Database().getid_byname('bmcsetup', data['bmcsetupname'])
            if data['bmcsetupid']:
                del data['bmcsetupname']
            else:
                response = {'message': f'BMC Setup {bmcname} does not exist.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'osimage' in data:
            osname = data['osimage']
            del data['osimage']
            data['osimageid'] = Database().getid_byname('osimage', osname)
        if not data['bmcsetupid']:
            response = {'message': f'BMC Setup {osname} does not exist.'}
            access_code = 400
            return json.dumps(response), access_code
        if 'interfaces' in data:
            newinterface = data['interfaces']
            del data['interfaces']

        grpcolumns = Database().get_columns('group')
        columncheck = Helper().checkin_list(data, grpcolumns)
        if columncheck:
            if update:
                where = [{"column": "id", "value": grpid}]
                row = Helper().make_rows(data)
                Database().update('group', row, where)
                response = {'message': f'Group {name} updated.'}
                access_code = 204
            if create:
                data['name'] = name
                row = Helper().make_rows(data)
                grpid = Database().insert('group', row)
                response = {'message': f'Group {name} created.'}
                access_code = 201
            if newinterface:
                for ifx in newinterface:
                    network = Database().getid_byname('network', ifx['network'])
                    if network is None:
                        response = {'message': f'Bad Request; Network {network} not exist.'}
                        access_code = 400
                        return json.dumps(response), access_code
                    else:
                        ifx['networkid'] = network
                        ifx['groupid'] = grpid
                        del ifx['network']
                    ifx['interfacename'] =  ifx['interface']
                    del ifx['interface']
                    ifname = ifx['interfacename']
                    grp_clause = f'groupid = "{grpid}"'
                    network_clause = f'networkid = "{network}"'
                    interface_clause = f'interfacename = "{ifname}"'
                    where = f' WHERE {grp_clause} AND {network_clause} AND {interface_clause}'
                    check_interface = Database().get_record(None, 'groupinterface', where)
                    if not check_interface:
                        row = Helper().make_rows(ifx)
                        result = Database().insert('groupinterface', row)
                        LOGGER.info(f'Interface created => {result} .')

        else:
            response = {'message': 'Bad Request; Columns are incorrect.'}
            access_code = 400
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route("/config/group/<string:name>/_delete", methods=['GET'])
###@token_required
def config_group_delete(name=None):
    """
    Input - Group Name
    Process - Delete the Group and it's interfaces.
    Output - Success or Failure.
    """
    group = Database().get_record(None, 'group', f' WHERE `name` = "{name}"')
    if group:
        Database().delete_row('group', [{"column": "name", "value": name}])
        Database().delete_row('groupinterface', [{"column": "groupid", "value": group[0]['id']}])
        Database().delete_row('groupsecrets', [{"column": "groupid", "value": group[0]['id']}])
        response = {'message': f'Group {name} with all its interfaces removed.'}
        access_code = 204
    else:
        response = {'message': f'Group {name} not present in database.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/group/<string:name>/interfaces", methods=['GET'])
###@token_required
def config_group_get_interfaces(name=None):
    """
    Input - Group Name
    Process - Fetch the Group Interface List.
    Output - Group Interface List.
    """
    groups = Database().get_record(None, 'group', f' WHERE name = "{name}"')
    if groups:
        response = {'config': {'group': {name: {'interfaces': [] } } } }
        for grp in groups:
            groupname = grp['name']
            groupid = grp['id']
            where = f' WHERE groupid = "{groupid}"'
            grp_interface = Database().get_record(None, 'groupinterface', where)
            if grp_interface:
                grp_interfaces = []
                for ifx in grp_interface:
                    ifx['network'] = Database().getname_byid('network', ifx['networkid'])
                    del ifx['groupid']
                    del ifx['id']
                    del ifx['networkid']
                    grp_interfaces.append(ifx)
                response['config']['group'][groupname]['interfaces'] = grp_interfaces
            else:
                LOGGER.error(f'Group {name} dont have any interface.')
                response = {'message': f'Group {name} dont have any interface.'}
                access_code = 404
        LOGGER.info(f'Returned group {name} with details.')
        access_code = 200
    else:
        LOGGER.error('No group is available.')
        response = {'message': 'No group is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/group/<string:name>/interfaces", methods=['POST'])
###@token_required
def config_group_post_interfaces(name=None):
    """
    Input - Group Name
    Process - Create Or Update The Group Interface.
    Output - Group Interface.
    """
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        grp = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if grp:
            grpid = grp[0]['id']
            if 'interfaces' in request_data['config']['group'][name]:
                for ifx in request_data['config']['group'][name]['interfaces']:
                    network = Database().getid_byname('network', ifx['network'])
                    if network is None:
                        response = {'message': f'Bad Request; Network {network} not exist.'}
                        access_code = 400
                        return json.dumps(response), access_code
                    else:
                        ifx['networkid'] = network
                        ifx['groupid'] = grpid
                        del ifx['network']
                    interfacename = ifx['interfacename']
                    grp_clause = f'groupid = "{grpid}"'
                    network_clause = f'networkid = "{network}"'
                    interface_clause = f'interfacename = "{interfacename}"'
                    where = f' WHERE {grp_clause} AND {network_clause} AND {interface_clause}'
                    interface_check = Database().get_record(None, 'groupinterface', where)
                    if not interface_check:
                        row = Helper().make_rows(ifx)
                        Database().insert('groupinterface', row)
                    response = {'message': 'Interface updated.'}
                    access_code = 204
            else:
                LOGGER.error('Kindly provide the interface.')
                response = {'message': 'Kindly provide the interface.'}
                access_code = 404
        else:
            LOGGER.error('No group is available.')
            response = {'message': 'No group is available.'}
            access_code = 404
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route("/config/group/<string:name>/interfaces/<string:interface>/_delete", methods=['GET'])
@token_required
def config_group_delete_interface(name=None, interface=None):
    """
    Input - Group Name & Interface Name
    Process - Delete the Group Interface.
    Output - Success or Failure.
    """
    group = Database().get_record(None, 'group', f' WHERE `name` = "{name}"')
    if group:
        groupid = group[0]['id']
        where = f' WHERE `interfacename` = "{interface}" AND `groupid` = "{groupid}"'
        group_interface = Database().get_record(None, 'groupinterface', where)
        if group_interface:
            where = [{"column": "id", "value": group_interface[0]['id']}]
            Database().delete_row('groupinterface', where)
            response = {'message': f'Group {name} interface {interface} removed.'}
            access_code = 204
        else:
            response = {'message': f'Group {name} interface {interface} not present in database.'}
            access_code = 404
    else:
        response = {'message': f'Group {name} not present in database.'}
        access_code = 404
    return json.dumps(response), access_code

############################# OSimage configuration #############################

@config_blueprint.route("/config/osimage", methods=['GET'])
def config_osimage():
    """
    Input - OS Image ID or Name
    Process - Fetch the OS Image information.
    Output - OSImage Info.
    """
    osimages = Database().get_record(None, 'osimage', None)
    if osimages:
        response = {'config': {'osimage': {} }}
        for image in osimages:
            image_name = image['name']
            del image['id']
            # del image['name']
            response['config']['osimage'][image_name] = image
        LOGGER.info('Provided list of all osimages with details.')
        access_code = 200
    else:
        LOGGER.error('No OS Image is available.')
        response = {'message': 'No OS Image is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/osimage/<string:name>", methods=['GET'])
def config_osimage_get(name=None):
    """
    Input - OS Image ID or Name
    Process - Fetch the OS Image information.
    Output - OSImage Info.
    """
    osimages = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
    if osimages:
        response = {'config': {'osimage': {} }}
        for image in osimages:
            del image['id']
            # del image['name']
            response['config']['osimage'][name] = image
        LOGGER.info(f'Returned OS Image {name} with details.')
        access_code = 200
    else:
        LOGGER.error('No OS Image is available.')
        response = {'message': 'No OS Image is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/osimage/<string:name>", methods=['POST'])
@token_required
def config_osimage_post(name=None):
    """
    Input - OS Image Name
    Process - Create or Update the OS Image information.
    Output - OSImage Info.
    """
    data = {}
    create, update = False, False
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['osimage'][name]
        image = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
        if image:
            imageid = image[0]['id']
            if 'newosimage' in data:
                newosname = data['newosimage']
                where = f' WHERE `name` = "{newosname}"'
                newoscheck = Database().get_record(None, 'osimage', where)
                if newoscheck:
                    response = {'message': f'{newosname} Already present in database.'}
                    access_code = 400
                    return json.dumps(response), access_code
                else:
                    data['name'] = data['newosimage']
                    del data['newosimage']
            update = True
        else:
            if 'newosimage' in data:
                newosname = data['newosimage']
                where = f' WHERE `name` = "{newosname}"'
                newoscheck = Database().get_record(None, 'osimage', where)
                if newoscheck:
                    response = {'message': f'{newosname} Already present in database.'}
                    access_code = 400
                    return json.dumps(response), access_code
                else:
                    data['name'] = data['newosimage']
                    del data['newosimage']
                create = True
            else:
                response = {'message': 'Kindly pass the new OS Image name.'}
                access_code = 400
                return json.dumps(response), access_code

        osimagecolumns = Database().get_columns('osimage')
        columncheck = Helper().checkin_list(data, osimagecolumns)
        if columncheck:
            if update:
                where = [{"column": "id", "value": imageid}]
                row = Helper().make_rows(data)
                Database().update('osimage', row, where)
                response = {'message': f'OS Image {name} updated.'}
                access_code = 204
            if create:
                data['name'] = name
                row = Helper().make_rows(data)
                Database().insert('osimage', row)
                response = {'message': f'OS Image {name} created.'}
                access_code = 201
        else:
            response = {'message': 'Bad Request; Columns are incorrect.'}
            access_code = 400
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route("/config/osimage/<string:name>/_delete", methods=['GET'])
@token_required
def config_osimage_delete(name=None):
    """
    Input - OS Image ID or Name
    Process - Delete the OS Image.
    Output - Success or Failure.
    """
    osimage = Database().get_record(None, 'osimage', f' WHERE `name` = "{name}"')
    if osimage:
        Database().delete_row('osimage', [{"column": "name", "value": name}])
        response = {'message': f'OS Image {name} removed.'}
        access_code = 204
    else:
        response = {'message': f'OS Image {name} not present in database.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/osimage/<string:name>/_clone", methods=['POST'])
@token_required
def config_osimage_clone(name=None):
    """
    Input - OS Image Name
    Process - Clone OS Image information.
    Output - OSImage Info.
    """
    data = {}
    create = False
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['osimage'][name]
        image = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
        if image:
            if 'newosimage' in data:
                newosname = data['newosimage']
                where = f' WHERE `name` = "{newosname}"'
                checknewos = Database().get_record(None, 'osimage', where)
                if checknewos:
                    response = {'message': f'{newosname} Already present in database.'}
                    access_code = 400
                    return json.dumps(response), access_code
                else:
                    data['name'] = data['newosimage']
                    del data['newosimage']
                    create = True
            else:
                response = {'message': 'Kindly pass the new OS Image name.'}
                access_code = 400
                return json.dumps(response), access_code
        else:
            response = {'message': f'OS Image {name} not present in the database.'}
            access_code = 400
            return json.dumps(response), access_code

        osimagecolumns = Database().get_columns('osimage')
        columncheck = Helper().checkin_list(data, osimagecolumns)
        if columncheck:
            if create:
                row = Helper().make_rows(data)
                Database().insert('osimage', row)
                response = {'message': f'OS Image {name} cloned to {newosname}.'}
                access_code = 201
        else:
            response = {'message': 'Bad Request; Columns are incorrect.'}
            access_code = 400
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
    return json.dumps(response), access_code



@config_blueprint.route("/config/osimage/<string:name>/_pack", methods=['GET'])
@token_required
def config_osimage_pack(name=None):
    """
    Input - OS Image ID or Name
    Process - Manually Pack the OS Image.
    Output - Success or Failure.
    """

    code=500
    response= {"message": f'OS image {name} packing failed. No sign of life of spawned thread.'}

    #Antoine
    request_id=str(time())+str(randint(1001,9999))+str(getpid())

    queue_id = Helper().add_task_to_queue(f'pack_n_tar_osimage:{name}','osimage',request_id)
    if not queue_id:
        LOGGER.info(f"config_osimage_pack GET cannot get queue_id")
        response= {"message": f'OS image {name} pack queuing failed.'}
        return json.dumps(response), code
 
    LOGGER.info(f"config_osimage_pack GET added task to queue: {queue_id}")
    Helper().insert_mesg_in_status(request_id,"luna",f"queued pack osimage {name} with queue_id {queue_id}")

    next_id = Helper().next_task_in_queue('osimage')
    if queue_id == next_id:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        executor.submit(OsImage().pack_n_tar_mother,name,request_id)
        executor.shutdown(wait=False)
#        OsImage().pack_n_tar_mother(name,request_id)

    # we should check after a few seconds if there is a status update for us.
    # if so, that means mother is taking care of things

    sleep(1)
    status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
    if status:
        code=200
        response = {"message": "osimage pack for {name} queued", "request_id": request_id}
    LOGGER.info(f"my repsonse [{response}]")
    return json.dumps(response), code



@config_blueprint.route("/config/osimage/<string:name>/kernel", methods=['POST'])
@token_required
def config_osimage_kernel_post(name=None):
    """
    Input - OS Image Name
    Process - Manually change kernel version.
    Output - Kernel Version.
    """
    data = {}
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['osimage'][name]
        image = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
        if image:
            # imageid = image[0]['id']
            osimagecolumns = Database().get_columns('osimage')
            columncheck = Helper().checkin_list(data, osimagecolumns)
            if columncheck:
                requestcheck = Helper().pack(name)
                print(f'REQUESTCHECK=======>> {requestcheck}')
                # where = [{"column": "id", "value": imageid}]
                # row = Helper().make_rows(data)
                # result = Database().update('osimage', row, where)
                response = {'message': f'OS Image {name} Kernel updated.'}
                access_code = 204
            else:
                response = {'message': 'Bad Request; Columns are incorrect.'}
                access_code = 400
        else:
            response = {'message': f'OS Image {name} dose not exist.'}
            access_code = 400
            return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
    return json.dumps(response), access_code


############################# Cluster configuration #############################


@config_blueprint.route("/config/cluster", methods=['GET'])
###@token_required
def config_cluster():
    """
    Input - None
    Process - Fetch The Cluster Information.
    Output - Cluster Information.
    """
    cluster = Database().get_record(None, 'cluster', None)
    if cluster:
        clusterid = cluster[0]['id']
        del cluster[0]['id']
        if cluster[0]['debug']:
            cluster[0]['debug'] = True
        else:
            cluster[0]['debug'] = False
        if cluster[0]['security']:
            cluster[0]['security'] = True
        else:
            cluster[0]['security'] = False
        response = {'config': {'cluster': cluster[0] }}
        controllers = Database().get_record_join(['controller.*','ipaddress.ipaddress'], ['ipaddress.tablerefid=controller.id','cluster.id=controller.clusterid'], ['tableref="controller"',f'cluster.id="{clusterid}"'])
        for controller in controllers:
            del controller['id']
            del controller['clusterid']
            controller['luna_config'] = CONFIGFILE
            response['config']['cluster'][controller['hostname']] = controller
            access_code = 200
    else:
        LOGGER.error('No cluster is available.')
        response = {'message': 'No cluster is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/cluster", methods=['POST'])
@token_required
def config_cluster_post():
    """
    Input - None
    Process - Fetch The Cluster Information.
    Output - Cluster Information.
    """
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['cluster']
        clustercolumns = Database().get_columns('cluster')
        clustercheck = Helper().checkin_list(data, clustercolumns)
        if clustercheck:
            cluster = Database().get_record(None, 'cluster', None)
            if cluster:
                where = [{"column": "id", "value": cluster[0]['id']}]
                row = Helper().make_rows(data)
                Database().update('cluster', row, where)
                response = {'message': 'Cluster updated.'}
                access_code = 204
            else:
                response = {'message': 'Bad Request; No cluster is available to update.'}
                access_code = 400
        else:
            response = {'message': 'Bad Request; Columns are incorrect.'}
            access_code = 400
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
    return json.dumps(response), 200


############################# BMC setup configuration #############################

@config_blueprint.route("/config/bmcsetup", methods=['GET'])
###@token_required
def config_bmcsetup():
    """
    Input - None
    Process - Fetch The list of configured settings.
    Output - List Of BMC Setup.
    """
    bmcsetup = Database().get_record(None, 'bmcsetup', None)
    if bmcsetup:
        response = {'config': {'bmcsetup': {} }}
        for bmc in bmcsetup:
            bmcname = bmc['name']
            # del bmc['name']
            del bmc['id']
            response['config']['bmcsetup'][bmcname] = bmc
        access_code = 200
    else:
        LOGGER.error('No BMC Setup is available.')
        response = {'message': 'No BMC Setup is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/bmcsetup/<string:bmcname>", methods=['GET'])
###@token_required
def config_bmcsetup_get(bmcname=None):
    """
    Input - BMC Setup ID or Name
    Process - Fetch The BMC Setup information.
    Output - BMC Setup Information.
    """
    bmcsetup = Database().get_record(None, 'bmcsetup', f' WHERE name = "{bmcname}"')
    if bmcsetup:
        response = {'config': {'bmcsetup': {} }}
        for bmc in bmcsetup:
            name = bmc['name']
            # del bmc['name']
            del bmc['id']
            response['config']['bmcsetup'][name] = bmc
        access_code = 200
    else:
        LOGGER.error('No BMC Setup is available.')
        response = {'message': 'No BMC Setup is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/bmcsetup/<string:bmcname>", methods=['POST'])
@token_required
def config_bmcsetup_post(bmcname=None):
    """
    Input - BMC Setup ID or Name
    Process - Create or Update BMC Setup information.
    Output - Success or Failure.
    """
    data = {}
    create, update = False, False
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['bmcsetup'][bmcname]
        data['name'] = bmcname
        bmc = Database().get_record(None, 'bmcsetup', f' WHERE `name` = "{bmcname}"')
        if bmc:
            bmcid = bmc[0]['id']
            if 'newbmcname' in request_data['config']['bmcsetup'][bmcname]:
                data['name'] = data['newbmcname']
                del data['newbmcname']
            update = True
        else:
            create = True
        bmccolumns = Database().get_columns('bmcsetup')
        columncheck = Helper().checkin_list(data, bmccolumns)
        row = Helper().make_rows(data)
        if columncheck:
            if create:
                Database().insert('bmcsetup', row)
                response = {'message': 'BMC Setup created.'}
                access_code = 201
            if update:
                where = [{"column": "id", "value": bmcid}]
                Database().update('bmcsetup', row, where)
                response = {'message': 'BMC Setup updated.'}
                access_code = 204
        else:
            response = {'message': 'Bad Request; Columns are incorrect.'}
            access_code = 400
            return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(data), access_code


@config_blueprint.route("/config/bmcsetup/<string:bmcname>/_clone", methods=['POST'])
@token_required
def config_bmcsetup_clone(bmcname=None):
    """
    Input - BMC Setup ID or Name
    Process - Fetch BMC Setup and Credentials.
    Output - BMC Name And Credentials.
    """
    data = {}
    create = False
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['bmcsetup'][bmcname]
        if 'newbmcname' in data:
            data['name'] = data['newbmcname']
            newbmc = data['newbmcname']
            del data['newbmcname']
        else:
            response = {'message': 'Kindly provide the new bmc name.'}
            access_code = 400
            return json.dumps(response), access_code
        checkbmc = Database().get_record(None, 'bmcsetup', f' WHERE `name` = "{bmcname}"')
        if checkbmc:
            checnewkbmc = Database().get_record(None, 'bmcsetup', f' WHERE `name` = "{newbmc}"')
            if checnewkbmc:
                response = {'message': f'{newbmc} Already present in database.'}
                access_code = 400
                return json.dumps(response), access_code
            else:
                create = True
        else:
            response = {'message': f'{bmcname} not present in database.'}
            access_code = 400
            return json.dumps(response), access_code
        bmccolumns = Database().get_columns('bmcsetup')
        columncheck = Helper().checkin_list(data, bmccolumns)
        row = Helper().make_rows(data)
        if columncheck:
            if create:
                Database().insert('bmcsetup', row)
                response = {'message': 'BMC Setup created.'}
                access_code = 201
        else:
            response = {'message': 'Bad Request; Columns are incorrect.'}
            access_code = 400
            return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(data), access_code


@config_blueprint.route("/config/bmcsetup/<string:bmcname>/_delete", methods=['GET'])
@token_required
def config_bmcsetup_delete(bmcname=None):
    """
    Input - BMC Setup ID or Name
    Process - Delete The BMC Setup Credentials.
    Output - Success or Failure.
    """
    bmc = Database().get_record(None, 'bmcsetup', f' WHERE `name` = "{bmcname}"')
    if bmc:
        Database().delete_row('bmcsetup', [{"column": "name", "value": bmcname}])
        response = {'message': 'BMC Setup removed.'}
        access_code = 204
    else:
        response = {'message': f'{bmcname} not present in the database.'}
        access_code = 404
    return json.dumps(response), access_code



############################# Switch configuration #############################

@config_blueprint.route("/config/switch", methods=['GET'])
###@token_required
def config_switch():
    """
    Input - None
    Process - Fetch The List Of Switches.
    Output - Switches.
    """
    switches = Database().get_record(None, 'switch', None)
    if switches:
        response = {'config': {'switch': { } }}
        for switch in switches:
            switchname = switch['name']
            response['config']['switch'][switchname] = switch
            #Antoine
            switch_ips = Database().get_record_join(['network.name as network','ipaddress.ipaddress'], ['ipaddress.tablerefid=switch.id','network.id=ipaddress.networkid'], ['tableref="switch"',f"tablerefid='{switch['id']}'"])
            if switch_ips:
                response['config']['switch'][switchname]['ipaddress'] = switch_ips[0]['ipaddress']
                response['config']['switch'][switchname]['network'] = switch_ips[0]['network']
        LOGGER.info(f'available Switches are {switches}.')
        access_code = 200
    else:
        LOGGER.error('No Switch is available.')
        response = {'message': 'No switch is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/switch/<string:switch>", methods=['GET'])
###@token_required
def config_switch_get(switch=None):
    """
    Input - Switch ID or Name
    Process - Fetch The Switch Information.
    Output - Switch Details.
    """
    switches = Database().get_record(None, 'switch', f' WHERE name = "{switch}"')
    if switches:
        response = {'config': {'switch': { } }}
        for switch in switches:
            switchname = switch['name']
            response['config']['switch'][switchname] = switch
            #Antoine
            switch_ips = Database().get_record_join(['network.name as network','ipaddress.ipaddress'], ['ipaddress.tablerefid=switch.id','network.id=ipaddress.networkid'], ['tableref="switch"',f"tablerefid='{switch['id']}'"])
            if switch_ips:
                response['config']['switch'][switchname]['ipaddress'] = switch_ips[0]['ipaddress']
                response['config']['switch'][switchname]['network'] = switch_ips[0]['network']
        LOGGER.info(f'available Switches are {switches}.')
        access_code = 200
    else:
        LOGGER.error('No switch is available.')
        response = {'message': 'No switch is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/switch/<string:switch>", methods=['POST'])
###@token_required
def config_switch_post(switch=None):
    """
    Input - Switch ID or Name
    Process - Fetch The Switch Information.
    Output - Switch Details.
    """
    network=False
    data = {}
    create, update = False, False
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['switch'][switch]
        data['name'] = switch
        checkswitch = Database().get_record(None, 'switch', f' WHERE `name` = "{switch}"')
        if checkswitch:
            switchid = checkswitch[0]['id']
            if 'newswitchname' in request_data['config']['switch'][switch]:
                data['name'] = data['newswitchname']
                del data['newswitchname']
            update = True
        else:
            create = True
        switchcolumns = Database().get_columns('switch')
        if 'ipaddress' in data.keys():
            ipaddress=data['ipaddress']
            del data['ipaddress']
        if 'network' in data.keys():
            network=data['network']
            del data['network']
        columncheck = Helper().checkin_list(data, switchcolumns)
        data = Helper().check_ip_exist(data)
        if data:
            row = Helper().make_rows(data)
            if columncheck:
                if create:
                    switchid=Database().insert('switch', row)
                    response = {'message': 'Switch created.'}
                    access_code = 201
                if update:
                    where = [{"column": "id", "value": switchid}]
                    Database().update('switch', row, where)
                    response = {'message': 'Switch updated.'}
                    access_code = 204
            else:
                response = {'message': 'Bad Request; Columns are incorrect.'}
                access_code = 400
        #Antoine
        # ----------- interface(s) update/create -------------
        result,mesg=Config().device_ipaddress_config(switchid,'switch',ipaddress,network)
        response = {'message': f"{mesg}"}

        if result is False:
            access_code=500
        return json.dumps(response), access_code

    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(data), access_code



@config_blueprint.route("/config/switch/<string:switch>/_clone", methods=['POST'])
###@token_required
def config_switch_clone(switch=None):
    """
    Input - Switch ID or Name
    Process - Delete The Switch.
    Output - Success or Failure.
    """
    data = {}
    create = False
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['switch'][switch]
        if 'newswitchname' in data:
            data['name'] = data['newswitchname']
            newswitchname = data['newswitchname']
            del data['newswitchname']
        else:
            response = {'message': 'Kindly provide the new switch name.'}
            access_code = 400
            return json.dumps(response), access_code
        checkswitch = Database().get_record(None, 'switch', f' WHERE `name` = "{newswitchname}"')
        if checkswitch:
            response = {'message': f'{newswitchname} already present in database.'}
            access_code = 400
            return json.dumps(response), access_code
        else:
            create = True
        if 'ipaddress' in data:
            del data['ipaddress']
        if 'network' in data:
            del data['network']
        switchcolumns = Database().get_columns('switch')
        columncheck = Helper().checkin_list(data, switchcolumns)
        data = Helper().check_ip_exist(data)
        if data:
            row = Helper().make_rows(data)
            if columncheck:
                if create:
                    Database().insert('switch', row)
                    response = {'message': 'Switch created.'}
                    access_code = 201
            else:
                response = {'message': 'Bad Request; Columns are incorrect.'}
                access_code = 400
                return json.dumps(response), access_code
        else:
            response = {'message': 'Bad Request; IP address already exist in the database.'}
            access_code = 400
            return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(data), access_code



@config_blueprint.route("/config/switch/<string:switch>/_delete", methods=['GET'])
###@token_required
def config_switch_delete(switch=None):
    """
    Input - Switch ID or Name
    Process - Delete The Switch.
    Output - Success or Failure.
    """
    checkswitch = Database().get_record(None, 'switch', f' WHERE `name` = "{switch}"')
    if checkswitch:
        Database().delete_row('ipaddress', [{"column": "tablerefid", "value": checkswitch[0]['id']},{"column": "tableref", "value": "switch"}])
        Database().delete_row('switch', [{"column": "id", "value": checkswitch[0]['id']}])
        response = {'message': 'Switch removed.'}
        access_code = 204
    else:
        response = {'message': f'{switch} not present in database.'}
        access_code = 404
    return json.dumps(response), access_code


############################# Other Devices configuration #############################


@config_blueprint.route("/config/otherdev", methods=['GET'])
###@token_required
def config_otherdev():
    """
    Input - None
    Process - Fetch The List Of Devices.
    Output - Devices.
    """
    devices = Database().get_record(None, 'otherdevices', None)
    if devices:
        response = {'config': {'otherdev': { } }}
        for device in devices:
            devicename = device['name']
            response['config']['otherdev'][devicename] = device
            #Antoine
            otherdev_ips = Database().get_record_join(['network.name as network','ipaddress.ipaddress'], ['ipaddress.tablerefid=otherdevices.id','network.id=ipaddress.networkid'], ['tableref="otherdevices"',f"tablerefid='{device['id']}'"])
            if otherdev_ips:
                response['config']['otherdev'][devicename]['ipaddress'] = otherdev_ips[0]['ipaddress']
                response['config']['otherdev'][devicename]['network'] = otherdev_ips[0]['network']
        LOGGER.info(f'available devices are {devices}.')
        access_code = 200
    else:
        LOGGER.error('No device is available.')
        response = {'message': 'No device is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/otherdev/<string:device>", methods=['GET'])
###@token_required
def config_otherdev_get(device=None):
    """
    Input - Device ID or Name
    Process - Fetch The List Of Devices.
    Output - Devices.
    """
    devices = Database().get_record(None, 'otherdevices', f' WHERE name = "{device}"')
    if devices:
        response = {'config': {'otherdev': { } }}
        for device in devices:
            devicename = device['name']
            response['config']['otherdev'][devicename] = device
            #Antoine
            otherdev_ips = Database().get_record_join(['network.name as network','ipaddress.ipaddress'], ['ipaddress.tablerefid=otherdevices.id','network.id=ipaddress.networkid'], ['tableref="otherdevices"',f"tablerefid='{device['id']}'"])
            if otherdev_ips:
                response['config']['otherdev'][devicename]['ipaddress'] = otherdev_ips[0]['ipaddress']
                response['config']['otherdev'][devicename]['network'] = otherdev_ips[0]['network']
        LOGGER.info(f'available Devices are {devices}.')
        access_code = 200
    else:
        LOGGER.error('No device is available.')
        response = {'message': 'No device is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/otherdev/<string:device>", methods=['POST'])
###@token_required
def config_otherdev_post(device=None):
    """
    Input - Device Name
    Output - Create or Update Device.
    """
    data = {}
    create, update = False, False
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['otherdev'][device]
        data['name'] = device
        checkdevice = Database().get_record(None, 'otherdevices', f' WHERE `name` = "{device}"')
        if checkdevice:
            deviceid = checkdevice[0]['id']
            if 'newotherdevname' in request_data['config']['otherdev'][device]:
                data['name'] = data['newotherdevname']
                del data['newotherdevname']
            update = True
        else:
            create = True
        devicecolumns = Database().get_columns('otherdevices')
        if 'ipaddress' in data.keys():
            ipaddress=data['ipaddress']
            del data['ipaddress']
        if 'network' in data.keys():
            network=data['network']
            del data['network']
        columncheck = Helper().checkin_list(data, devicecolumns)
        data = Helper().check_ip_exist(data)
        if data:
            row = Helper().make_rows(data)
            if columncheck:
                if create:
                    deviceid=Database().insert('otherdevices', row)
                    response = {'message': 'Device created.'}
                    access_code = 201
                if update:
                    where = [{"column": "id", "value": deviceid}]
                    Database().update('otherdevices', row, where)
                    response = {'message': 'Device updated.'}
                    access_code = 204
            else:
                response = {'message': 'Bad Request; Columns are incorrect.'}
                access_code = 400
                return json.dumps(response), access_code
        #Antoine
        # ----------- interface(s) update/create -------------
        result,mesg=Config().device_ipaddress_config(deviceid,'otherdevices',ipaddress,network)
        response = {'message': f"{mesg}"}

        if result is False:
            access_code=500
        return json.dumps(response), access_code

    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(data), access_code



@config_blueprint.route("/config/otherdev/<string:device>/_clone", methods=['POST'])
###@token_required
def config_otherdev_clone(device=None):
    """
    Input - Device ID or Name
    Output - Clone The Device.
    """
    data = {}
    create = False
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['otherdev'][device]
        if 'newotherdevname' in data:
            data['name'] = data['newotherdevname']
            newdevicename = data['newotherdevname']
            del data['newotherdevname']
        else:
            response = {'message': 'Kindly provide the new device name.'}
            access_code = 400
            return json.dumps(response), access_code
        where = f' WHERE `name` = "{newdevicename}"'
        checkdevice = Database().get_record(None, 'otherdevices', where)
        if checkdevice:
            response = {'message': f'{newdevicename} already present in database.'}
            access_code = 400
            return json.dumps(response), access_code
        else:
            create = True
        if 'ipaddress' in data:
            del data['ipaddress']
        if 'network' in data:
            del data['network']
        devicecolumns = Database().get_columns('otherdevices')
        columncheck = Helper().checkin_list(data, devicecolumns)
#        data = Helper().check_ip_exist(data)
        if data:
            row = Helper().make_rows(data)
            if columncheck:
                if create:
                    Database().insert('otherdevices', row)
                    response = {'message': 'Device cloned.'}
                    access_code = 201
            else:
                response = {'message': 'Bad Request; Columns are incorrect.'}
                access_code = 400
                return json.dumps(response), access_code
        else:
            response = {'message': 'Bad Request; IP address already exist in the database.'}
            access_code = 400
            return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(data), access_code



@config_blueprint.route("/config/otherdev/<string:device>/_delete", methods=['GET'])
###@token_required
def config_otherdev_delete(device=None):
    """
    Input - Device ID or Name
    Process - Delete The Device.
    Output - Success or Failure.
    """
    checkdevice = Database().get_record(None, 'otherdevices', f' WHERE `name` = "{device}"')
    if checkdevice:
        Database().delete_row('ipaddress', [{"column": "tablerefid", "value": checkdevice[0]['id']},{"column": "tableref", "value": "otherdevices"}])
        Database().delete_row('otherdevices', [{"column": "id", "value": checkdevice[0]['id']}])
        response = {'message': 'Device removed.'}
        access_code = 204
    else:
        response = {'message': f'{device} not present in database.'}
        access_code = 404
    return json.dumps(response), access_code


############################# Network configuration #############################


@config_blueprint.route("/config/network", methods=['GET'])
###@token_required
def config_network():
    """
    Input - None
    Process - Fetch The Network Information.
    Output - Network Information.
    """
    networks = Database().get_record(None, 'network', None)
    if networks:
        response = {'config': {'network': {} }}
        for nwk in networks:
            nwk['network'] = Helper().get_network(nwk['network'], nwk['subnet'])
            del nwk['id']
            del nwk['subnet']
            if not nwk['dhcp']:
                del nwk['dhcp_range_begin']
                del nwk['dhcp_range_end']
                nwk['dhcp'] = False
            else:
                nwk['dhcp'] = True
            response['config']['network'][nwk['name']] = nwk
        access_code = 200
    else:
        LOGGER.error('No networks is available.')
        response = {'message': 'No networks is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/network/<string:name>", methods=['GET'])
###@token_required
def config_network_get(name=None):
    """
    Input - Network Name
    Process - Fetch The Network Information.
    Output - Network Information.
    """
    networks = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
    if networks:
        response = {'config': {'network': {} }}
        for nwk in networks:
            nwk['network'] = Helper().get_network(nwk['network'], nwk['subnet'])
            del nwk['id']
            del nwk['subnet']
            if not nwk['dhcp']:
                del nwk['dhcp_range_begin']
                del nwk['dhcp_range_end']
                nwk['dhcp'] = False
            else:
                nwk['dhcp'] = True
            response['config']['network'][nwk['name']] = nwk
        access_code = 200
    else:
        LOGGER.error(f'Network {name} is not available.')
        response = {'message': f'Network {name} is not available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/network/<string:name>", methods=['POST'])
###@token_required
def config_network_post(name=None):
    """
    Input - Network Name
    Process - Create or Update Network information.
    Output - Success or Failure.
    """
    data = {}
    create, update = False, False
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['network'][name]
        data['name'] = name
        checknetwork = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
        if checknetwork:
            networkid = checknetwork[0]['id']
            if 'newnetname' in request_data['config']['network'][name]:
                newnetworkname = request_data['config']['network'][name]['newnetname']
                where = f' WHERE `name` = "{newnetworkname}"'
                checknewnetwork = Database().get_record(None, 'network', where)
                if checknewnetwork:
                    response = {'message': f'{newnetworkname} already present in database.'}
                    access_code = 400
                    return json.dumps(response), access_code
                else:
                    data['name'] = data['newnetname']
                    del data['newnetname']
            update = True
        else:
            create = True
        if 'network' in data:
            nwkip = Helper().check_ip(data['network'])
            if nwkip:
                nwkdetails = Helper().get_network_details(data['network'])
                data['network'] = nwkip
                data['subnet'] = nwkdetails['subnet']
            else:
                response = {'message': f'Incorrect network IP: {data["network"]}.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'gateway' in data:
            gwdetails = Helper().check_ip_range(data['gateway'], data['network']+'/'+data['subnet'])
            if not gwdetails:
                response = {'message': f'Incorrect gateway IP: {data["gateway"]}.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'ns_ip' in data:
            nsipdetails = Helper().check_ip_range(data['ns_ip'], data['network']+'/'+data['subnet'])
            if not nsipdetails:
                response = {'message': f'Incorrect NS IP: {data["ns_ip"]}.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'ntp_server' in data:
            subnet = data['network']+'/'+data['subnet']
            ntpdetails = Helper().check_ip_range(data['ntp_server'], subnet)
            if not ntpdetails:
                response = {'message': f'Incorrect NTP Server IP: {data["ntp_server"]}.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'dhcp' in data:
            if 'dhcp_range_begin' in data:
                #subnet = data['network']+'/'+data['subnet']
            # --------- we have to check if it is supplied er else get it from the DB
                dhcpstartdetails = Helper().check_ip_range(data['dhcp_range_begin'], subnet)
                if not dhcpstartdetails:
                    response = {'message': f'Incorrect dhcp start: {data["dhcp_range_begin"]}.'}
                    access_code = 400
                    return json.dumps(response), access_code
            else:
                response = {'message': 'DHCP start range is a required parameter.'}
                access_code = 400
                return json.dumps(response), access_code
            if 'dhcp_range_end' in data:
                subnet = data['network']+'/'+data['subnet']
                dhcpenddetails = Helper().check_ip_range(data['dhcp_range_end'], subnet)
                if not dhcpenddetails:
                    response = {'message': f'Incorrect dhcp end: {data["dhcp_range_end"]}.'}
                    access_code = 400
                    return json.dumps(response), access_code
            else:
                response = {'message': 'DHCP end range is a required parameter.'}
                access_code = 400
                return json.dumps(response), access_code
        else:
            data['dhcp'] = False
            data['dhcp_range_begin'] = ""
            data['dhcp_range_end'] = ""
        networkcolumns = Database().get_columns('network')
        columncheck = Helper().checkin_list(data, networkcolumns)
        row = Helper().make_rows(data)
        if columncheck:
            if create:
                Database().insert('network', row)
                response = {'message': 'Network created.'}
                access_code = 201
            if update:
                where = [{"column": "id", "value": networkid}]
                Database().update('network', row, where)
                response = {'message': 'Network updated.'}
                access_code = 204
        else:
            response = {'message': 'Bad Request; Columns are incorrect.'}
            access_code = 400
            return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(data), access_code


@config_blueprint.route("/config/network/<string:name>/_clone", methods=['POST'])
# ###@token_required
def config_network_clone(name=None):
    """
    Input - Network Name
    Process - Create or Update Network information.
    Output - Success or Failure.
    """
    data = {}
    create = False
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['network'][name]
        data['name'] = name
        checknetwork = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
        if checknetwork:
            if 'newnetname' in request_data['config']['network'][name]:
                newnetworkname = request_data['config']['network'][name]['newnetname']
                where = f' WHERE `name` = "{newnetworkname}"'
                checknewnetwork = Database().get_record(None, 'network', where)
                if checknewnetwork:
                    response = {'message': f'{newnetworkname} already present in database.'}
                    access_code = 400
                    return json.dumps(response), access_code
                else:
                    data['name'] = data['newnetname']
                    del data['newnetname']
            create = True
        else:
            response = {'message': f'Bad Request; Network {name} is not present in database.'}
            access_code = 400
            return json.dumps(response), access_code
        if 'network' in data:
            nwkip = Helper().check_ip(data['network'])
            if nwkip:
                nwkdetails = Helper().get_network_details(data['network'])
                data['network'] = nwkip
                data['subnet'] = nwkdetails['subnet']
            else:
                response = {'message': f'Incorrect network IP: {data["network"]}.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'gateway' in data:
            gwdetails = Helper().check_ip_range(data['gateway'], data['network']+'/'+data['subnet'])
            if not gwdetails:
                response = {'message': f'Incorrect gateway IP: {data["gateway"]}.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'ns_ip' in data:
            nsipdetails = Helper().check_ip_range(data['ns_ip'], data['network']+'/'+data['subnet'])
            if not nsipdetails:
                response = {'message': f'Incorrect NS IP: {data["ns_ip"]}.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'ntp_server' in data:
            subnet = data['network']+'/'+data['subnet']
            ntpdetails = Helper().check_ip_range(data['ntp_server'], subnet)
            if not ntpdetails:
                response = {'message': f'Incorrect NTP Server IP: {data["ntp_server"]}.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'dhcp' in data:
            if 'dhcp_range_begin' in data:
                subnet = data['network']+'/'+data['subnet']
                dhcpstartdetails = Helper().check_ip_range(data['dhcp_range_begin'], subnet)
                if not dhcpstartdetails:
                    response = {'message': f'Incorrect DHCP start: {data["dhcp_range_begin"]}.'}
                    access_code = 400
                    return json.dumps(response), access_code
            else:
                response = {'message': 'DHCP start range is a required parameter.'}
                access_code = 400
                return json.dumps(response), access_code
            if 'dhcp_range_end' in data:
                subnet = data['network']+'/'+data['subnet']
                dhcpenddetails = Helper().check_ip_range(data['dhcp_range_end'], subnet)
                if not dhcpenddetails:
                    response = {'message': f'Incorrect DHCP end: {data["dhcp_range_end"]}.'}
                    access_code = 400
                    return json.dumps(response), access_code
            else:
                response = {'message': 'DHCP end range is a required parameter.'}
                access_code = 400
                return json.dumps(response), access_code
        else:
            data['dhcp'] = False
            data['dhcp_range_begin'] = ""
            data['dhcp_range_end'] = ""
        networkcolumns = Database().get_columns('network')
        columncheck = Helper().checkin_list(data, networkcolumns)
        row = Helper().make_rows(data)
        if columncheck:
            if create:
                Database().insert('network', row)
                response = {'message': 'Network created.'}
                access_code = 201
        else:
            response = {'message': 'Bad Request; Columns are incorrect.'}
            access_code = 400
            return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(data), access_code


@config_blueprint.route("/config/network/<string:name>/_delete", methods=['GET'])
###@token_required
def config_network_delete(name=None):
    """
    Input - Network Name
    Process - Delete The Network.
    Output - Success or Failure.
    """
    network = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
    if network:
        Database().delete_row('network', [{"column": "name", "value": name}])
        response = {'message': 'Network removed.'}
        access_code = 204
    else:
        response = {'message': f'Network {name} not present in database.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/network/<string:name>/<string:ipaddr>", methods=['GET'])
###@token_required
def config_network_ip(name=None, ipaddr=None):
    """
    Input - Network Name And IP Address
    Process - Delete The Network.
    Output - Success or Failure.
    """
    network = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
    if network:
        ipdetails = Helper().check_ip_range(ipaddr, network[0]['network']+'/'+network[0]['subnet'])
        if ipdetails:
            checkip = Database().get_record(None, 'ipaddress', f' WHERE ipaddress = "{ipaddr}"; ')
            if checkip:
                response = {'config': {'network': {ipaddr: {'status': 'taken'} } } }
                access_code = 200
            else:
                response = {'config': {'network': {ipaddr: {'status': 'free'} } } }
                access_code = 200
        else:
            response = {'message': f'{ipaddr} is not in the range.'}
            access_code = 404
            return json.dumps(response), access_code
    else:
        response = {'message': f'Network {name} not present in database.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/network/<string:name>/_nextfreeip", methods=['GET'])
###@token_required
def config_network_nextip(name=None):
    """
    Input - Network Name
    Process - Find The Next Available IP on the Netwok.
    Output - Next Available IP on the Netwok.
    """

    response = {'message': f'Network {name} not present in database.'}
    access_code = 404

    #Antoine
    ips=[]
    avail=None
    network = Database().get_record_join(['ipaddress.ipaddress','network.id','network.network','network.subnet'], ['network.id=ipaddress.networkid'], [f"network.name='{name}'"])
    if network:
        for ip in network:
            ips.append(ip['ipaddress'])
    else:
        network = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')

    if network:
        access_code = 500
        response = {'message': f'Network {name} has no free addresses.'}
        ret=0
        max=10 # we try to ping for 10 ips, if none of these are free, something else is going on (read: rogue devices)....
        while(max>0 and ret!=1):
            avail=Helper().get_available_ip(network[0]['network'],network[0]['subnet'],ips)
            ips.append(avail)
            output,ret=Helper().runcommand(f"ping -w1 -c1 {avail}", True, 3)
            max-=1

    if avail:
        response = {'config': {'network': {name: {'nextip': avail} } } }

    if response:
        access_code = 200
    return json.dumps(response), access_code


############################# Secrets configuration #############################


@config_blueprint.route("/config/secrets", methods=['GET'])
###@token_required
def config_secrets_get():
    """
    Input - None
    Output - Return the List Of All Secrets.
    """
    nodesecrets = Database().get_record(None, 'nodesecrets', None)
    groupsecrets = Database().get_record(None, 'groupsecrets', None)
    if nodesecrets or groupsecrets:
        response = {'config': {'secrets': {} }}
        access_code = 200
    else:
        LOGGER.error('Secrets are not available.')
        response = {'message': 'Secrets are not available.'}
        access_code = 404
    if nodesecrets:
        response['config']['secrets']['node'] = {}
        for node in nodesecrets:
            nodename = Database().getname_byid('node', node['nodeid'])
            if nodename not in response['config']['secrets']['node']:
                response['config']['secrets']['node'][nodename] = []
            del node['nodeid']
            del node['id']
            node['content'] = Helper().decrypt_string(node['content'])
            response['config']['secrets']['node'][nodename].append(node)
    if groupsecrets:
        response['config']['secrets']['group'] = {}
        for group in groupsecrets:
            groupname = Database().getname_byid('group', group['groupid'])
            if groupname not in response['config']['secrets']['group']:
                response['config']['secrets']['group'][groupname] = []
            del group['groupid']
            del group['id']
            group['content'] = Helper().decrypt_string(group['content'])
            response['config']['secrets']['group'][groupname].append(group)
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/node/<string:name>", methods=['GET'])
###@token_required
def config_get_secrets_node(name=None):
    """
    Input - Node Name
    Output - Return the Node Secrets And Group Secrets for the Node.
    """
    node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
    if node:
        nodeid  = node[0]['id']
        groupid  = node[0]['groupid']
        nodesecrets = Database().get_record(None, 'nodesecrets', f' WHERE nodeid = "{nodeid}"')
        groupsecrets = Database().get_record(None, 'groupsecrets', f' WHERE groupid = "{groupid}"')
        if nodesecrets or groupsecrets:
            response = {'config': {'secrets': {} }}
            access_code = 200
        else:
            LOGGER.error(f'Secrets are not available for node {name}.')
            response = {'message': f'Secrets are not available for node {name}.'}
            access_code = 404
        if nodesecrets:
            response['config']['secrets']['node'] = {}
            for node in nodesecrets:
                nodename = Database().getname_byid('node', node['nodeid'])
                if nodename not in response['config']['secrets']['node']:
                    response['config']['secrets']['node'][nodename] = []
                del node['nodeid']
                del node['id']
                node['content'] = Helper().decrypt_string(node['content'])
                response['config']['secrets']['node'][nodename].append(node)
        if groupsecrets:
            response['config']['secrets']['group'] = {}
            for group in groupsecrets:
                groupname = Database().getname_byid('group', group['groupid'])
                if groupname not in response['config']['secrets']['group']:
                    response['config']['secrets']['group'][groupname] = []
                del group['groupid']
                del group['id']
                group['content'] = Helper().decrypt_string(group['content'])
                response['config']['secrets']['group'][groupname].append(group)
    else:
        LOGGER.error(f'Node {name} is not available.')
        response = {'message': f'Node {name} is not available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/node/<string:name>", methods=['POST'])
###@token_required
def config_post_secrets_node(name=None):
    """
    Input - Node Name & Payload
    Process - Create Or Update Node Secrets.
    Output - None.
    """
    data, = {}
    create, update = False, False
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['secrets']['node'][name]
        node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if node:
            nodeid = node[0]['id']
            if data:
                for secret in data:
                    secretname = secret['name']
                    where = f' WHERE nodeid = "{nodeid}" AND name = "{secretname}"'
                    secretdata = Database().get_record(None, 'nodesecrets', where)
                    if secretdata:
                        nodesecretcolumns = Database().get_columns('nodesecrets')
                        columncheck = Helper().checkin_list(secretdata[0], nodesecretcolumns)
                        if columncheck:
                            secretid = secretdata[0]['id']
                            secret['content'] = Helper().encrypt_string(secret['content'])
                            where = [
                                {"column": "id", "value": secretid},
                                {"column": "nodeid", "value": nodeid},
                                {"column": "name", "value": secretname}
                                ]
                            row = Helper().make_rows(secret)
                            Database().update('nodesecrets', row, where)
                            update = True
                    else:
                        secret['nodeid'] = nodeid
                        secret['content'] = Helper().encrypt_string(secret['content'])
                        row = Helper().make_rows(secret)
                        Database().insert('nodesecrets', row)
                        create = True
            else:
                LOGGER.error('Kindly provide at least one secret.')
                response = {'message': 'Kindly provide at least one secret.'}
                access_code = 404
        else:
            LOGGER.error(f'Node {name} is not available.')
            response = {'message': f'Node {name} is not available.'}
            access_code = 404

        if create is True and update is True:
            response = {'message': f'Node {name} Secrets created & updated.'}
            access_code = 201
        elif create is True and update is False:
            response = {'message': f'Node {name} Secret created.'}
            access_code = 201
        elif create is False and update is True:
            response = {'message': f'Node {name} Secret updated.'}
            access_code = 201
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/node/<string:name>/<string:secret>", methods=['GET'])
###@token_required
def config_get_node_secret(name=None, secret=None):
    """
    Input - Node Name & Secret Name
    Output - Return the Node Secret
    """
    node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
    if node:
        nodeid  = node[0]['id']
        where = f' WHERE nodeid = "{nodeid}" AND name = "{secret}"'
        secret_data = Database().get_record(None, 'nodesecrets', where)
        if secret_data:
            response = {'config': {'secrets': {'node': {name: [] } } } }
            access_code = 200
            del secret_data[0]['nodeid']
            del secret_data[0]['id']
            secret_data[0]['content'] = Helper().decrypt_string(secret_data[0]['content'])
            response['config']['secrets']['node'][name] = secret_data
        else:
            LOGGER.error(f'Secret {secret} is unavailable for node {name}.')
            response = {'message': f'Secret {secret} is unavailable for node {name}.'}
            access_code = 404
    else:
        LOGGER.error(f'Node {name} is not available.')
        response = {'message': f'Node {name} is not available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/node/<string:name>/<string:secret>", methods=['POST'])
###@token_required
def config_post_node_secret(name=None, secret=None):
    """
    Input - Node Name & Payload
    Process - Create Or Update Node Secrets.
    Output - None.
    """
    data = {}
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['secrets']['node'][name]
        node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if node:
            nodeid = node[0]['id']
            if data:
                secretname = data[0]['name']
                where = f' WHERE nodeid = "{nodeid}" AND name = "{secretname}"'
                secret_data = Database().get_record(None, 'nodesecrets', where)
                if secret_data:
                    nodesecretcolumns = Database().get_columns('nodesecrets')
                    columncheck = Helper().checkin_list(data[0], nodesecretcolumns)
                    if columncheck:
                        secretid = secret_data[0]['id']
                        data[0]['content'] = Helper().encrypt_string(data[0]['content'])
                        where = [
                            {"column": "id", "value": secretid},
                            {"column": "nodeid", "value": nodeid},
                            {"column": "name", "value": secretname}
                            ]
                        row = Helper().make_rows(data[0])
                        Database().update('nodesecrets', row, where)
                        response = {'message': f'Node {name} Secret {secret} updated.'}
                        access_code = 204
                else:
                    LOGGER.error(f'Node {name}, Secret {secret} is unavailable.')
                    response = {'message': f'Node {name}, Secret {secret} is unavailable.'}
                    access_code = 404
            else:
                LOGGER.error('Kindly provide at least one secret.')
                response = {'message': 'Kindly provide at least one secret.'}
                access_code = 404
        else:
            LOGGER.error(f'Node {name} is not available.')
            response = {'message': f'Node {name} is not available.'}
            access_code = 404
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/node/<string:name>/<string:secret>/_clone", methods=['POST'])
###@token_required
def config_clone_node_secret(name=None, secret=None):
    """
    Input - Node Name & Payload
    Process - Create Or Update Node Secrets.
    Output - None.
    """
    data = {}
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['secrets']['node'][name]
        node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if node:
            nodeid = node[0]['id']
            if data:
                secretname = data[0]['name']
                where = f' WHERE nodeid = "{nodeid}" AND name = "{secretname}"'
                secretdata = Database().get_record(None, 'nodesecrets', where)
                if secretdata:
                    if 'newsecretname' in data[0]:
                        newsecretname = data[0]['newsecretname']
                        del data[0]['newsecretname']
                        data[0]['nodeid'] = nodeid
                        data[0]['name'] = newsecretname
                        where = f' WHERE nodeid = "{nodeid}" AND name = "{newsecretname}"'
                        newsecretdata = Database().get_record(None, 'nodesecrets', where)
                        if newsecretdata:
                            LOGGER.error(f'Secret {newsecretname} already present.')
                            response = {'message': f'Secret {newsecretname} already present.'}
                            access_code = 404
                        else:
                            nodesecretcolumns = Database().get_columns('nodesecrets')
                            columncheck = Helper().checkin_list(data[0], nodesecretcolumns)
                            if columncheck:
                                data[0]['content'] = Helper().encrypt_string(data[0]['content'])
                                row = Helper().make_rows(data[0])
                                Database().insert('nodesecrets', row)
                                message = f'Node {name} Secret {secret} Cloned to {newsecretname}.'
                                response = {'message': message}
                                access_code = 204
                    else:
                        LOGGER.error('Kindly pass the new secret name.')
                        response = {'message': 'Kindly pass the new secret name.'}
                        access_code = 404
                else:
                    LOGGER.error(f'Node {name}, Secret {secret} is unavailable.')
                    response = {'message': f'Node {name}, Secret {secret} is unavailable.'}
                    access_code = 404
            else:
                LOGGER.error('Kindly provide at least one secret.')
                response = {'message': 'Kindly provide at least one secret.'}
                access_code = 404
        else:
            LOGGER.error(f'Node {name} is not available.')
            response = {'message': f'Node {name} is not available.'}
            access_code = 404
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/node/<string:name>/<string:secret>/_delete", methods=['GET'])
###@token_required
def config_node_secret_delete(name=None, secret=None):
    """
    Input - Node Name & Secret Name
    Output - Success or Failure
    """
    node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
    if node:
        nodeid  = node[0]['id']
        where = f' WHERE nodeid = "{nodeid}" AND name = "{secret}"'
        secret_data = Database().get_record(None, 'nodesecrets', where)
        if secret_data:
            where = [{"column": "nodeid", "value": nodeid}, {"column": "name", "value": secret}]
            Database().delete_row('nodesecrets', where)
            response = {'message': f'Secret {secret} deleted from node {name}.'}
            access_code = 204
        else:
            LOGGER.error(f'Secret {secret} is unavailable for node {name}.')
            response = {'message': f'Secret {secret} is unavailable for node {name}.'}
            access_code = 404
    else:
        LOGGER.error(f'Node {name} is not available.')
        response = {'message': f'Node {name} is not available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/group/<string:name>", methods=['GET'])
###@token_required
def config_get_secrets_group(name=None):
    """
    Input - Group Name
    Output - Return the Group Secrets.
    """
    group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
    if group:
        groupid  = group[0]['id']
        groupsecrets = Database().get_record(None, 'groupsecrets', f' WHERE groupid = "{groupid}"')
        if groupsecrets:
            response = {'config': {'secrets': {'group': {name: [] } } } }
            for grp in groupsecrets:
                del grp['groupid']
                del grp['id']
                grp['content'] = Helper().decrypt_string(grp['content'])
                response['config']['secrets']['group'][name].append(grp)
                access_code = 200
        else:
            LOGGER.error(f'Secrets are not available for group {name}.')
            response = {'message': f'Secrets are not available for group {name}.'}
            access_code = 404
    else:
        LOGGER.error(f'Group {name} is not available.')
        response = {'message': f'Group {name} is not available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/group/<string:name>", methods=['POST'])
###@token_required
def config_post_secrets_group(name=None):
    """
    Input - Group Name & Payload
    Process - Create Or Update Group Secrets.
    Output - None.
    """
    data = {}
    create, update = False, False
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['secrets']['group'][name]
        group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if group:
            groupid = group[0]['id']
            if data:
                for secret in data:
                    secretname = secret['name']
                    where = f' WHERE groupid = "{groupid}" AND name = "{secretname}"'
                    secretdata = Database().get_record(None, 'groupsecrets', where)
                    if secretdata:
                        grpsecretcolumns = Database().get_columns('groupsecrets')
                        columncheck = Helper().checkin_list(secretdata[0], grpsecretcolumns)
                        if columncheck:
                            secretid = secretdata[0]['id']
                            secret['content'] = Helper().encrypt_string(secret['content'])
                            where = [
                                {"column": "id", "value": secretid},
                                {"column": "groupid", "value": groupid},
                                {"column": "name", "value": secretname}
                                ]
                            row = Helper().make_rows(secret)
                            Database().update('groupsecrets', row, where)
                            update = True
                    else:
                        secret['groupid'] = groupid
                        secret['content'] = Helper().encrypt_string(secret['content'])
                        row = Helper().make_rows(secret)
                        Database().insert('groupsecrets', row)
                        create = True
            else:
                LOGGER.error('Kindly provide at least one secret.')
                response = {'message': 'Kindly provide at least one secret.'}
                access_code = 404
        else:
            LOGGER.error(f'Group {name} is not available.')
            response = {'message': f'Group {name} is not available.'}
            access_code = 404

        if create is True and update is True:
            response = {'message': f'Group {name} secrets created & updated.'}
            access_code = 204
        elif create is True and update is False:
            response = {'message': f'Group {name} secret created.'}
            access_code = 201
        elif create is False and update is True:
            response = {'message': f'Group {name} secret updated.'}
            access_code = 204
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/group/<string:name>/<string:secret>", methods=['GET'])
###@token_required
def config_get_group_secret(name=None, secret=None):
    """
    Input - Group Name & Secret Name
    Output - Return the Group Secret
    """
    group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
    if group:
        groupid  = group[0]['id']
        where = f' WHERE groupid = "{groupid}" AND name = "{secret}"'
        secretdata = Database().get_record(None, 'groupsecrets', where)
        if secretdata:
            response = {'config': {'secrets': {'group': {name: [] } } } }
            access_code = 200
            del secretdata[0]['groupid']
            del secretdata[0]['id']
            secretdata[0]['content'] = Helper().decrypt_string(secretdata[0]['content'])
            response['config']['secrets']['group'][name] = secretdata
        else:
            LOGGER.error(f'Secret {secret} is unavailable for group {name}.')
            response = {'message': f'Secret {secret} is unavailable for group {name}.'}
            access_code = 404
    else:
        LOGGER.error(f'Group {name} is not available.')
        response = {'message': f'Group {name} is not available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/group/<string:name>/<string:secret>", methods=['POST'])
###@token_required
def config_post_group_secret(name=None, secret=None):
    """
    Input - Group Name & Payload
    Process - Create Or Update Group Secrets.
    Output - None.
    """
    data = {}
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['secrets']['group'][name]
        group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if group:
            groupid = group[0]['id']
            if data:
                secretname = data[0]['name']
                where = f' WHERE groupid = "{groupid}" AND name = "{secretname}"'
                secretdata = Database().get_record(None, 'groupsecrets', where)
                if secretdata:
                    grpsecretcolumns = Database().get_columns('groupsecrets')
                    columncheck = Helper().checkin_list(data[0], grpsecretcolumns)
                    if columncheck:
                        secretid = secretdata[0]['id']
                        data[0]['content'] = Helper().encrypt_string(data[0]['content'])
                        where = [
                            {"column": "id", "value": secretid},
                            {"column": "groupid", "value": groupid},
                            {"column": "name", "value": secretname}
                            ]
                        row = Helper().make_rows(data[0])
                        Database().update('groupsecrets', row, where)
                        response = {'message': f'Group {name} secret {secret} updated.'}
                        access_code = 204
                else:
                    LOGGER.error(f'Group {name}, Secret {secret} is unavailable.')
                    response = {'message': f'Group {name}, secret {secret} is unavailable.'}
                    access_code = 404
            else:
                LOGGER.error('Kindly provide at least one secret.')
                response = {'message': 'Kindly provide at least one secret.'}
                access_code = 404
        else:
            LOGGER.error(f'Group {name} is not available.')
            response = {'message': f'Group {name} is not available.'}
            access_code = 404
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/group/<string:name>/<string:secret>/_clone", methods=['POST'])
###@token_required
def config_clone_group_secret(name=None, secret=None):
    """
    Input - Group Name & Payload
    Process - Clone Group Secrets.
    Output - None.
    """
    data = {}
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['secrets']['group'][name]
        group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if group:
            groupid = group[0]['id']
            if data:
                secretname = data[0]['name']
                where = f' WHERE groupid = "{groupid}" AND name = "{secretname}"'
                secretdata = Database().get_record(None, 'groupsecrets', where)
                if secretdata:
                    if 'newsecretname' in data[0]:
                        newsecretname = data[0]['newsecretname']
                        del data[0]['newsecretname']
                        data[0]['groupid'] = groupid
                        data[0]['name'] = newsecretname
                        where = f' WHERE groupid = "{groupid}" AND name = "{newsecretname}"'
                        newsecretdata = Database().get_record(None, 'groupsecrets', where)
                        if newsecretdata:
                            LOGGER.error(f'Secret {newsecretname} already present.')
                            response = {'message': f'Secret {newsecretname} already present.'}
                            access_code = 404
                        else:
                            grpsecretcolumns = Database().get_columns('groupsecrets')
                            columncheck = Helper().checkin_list(data[0], grpsecretcolumns)
                            if columncheck:
                                data[0]['content'] = Helper().encrypt_string(data[0]['content'])
                                row = Helper().make_rows(data[0])
                                Database().insert('groupsecrets', row)
                                message = f'Group {name} Secret {secret} cloned to {newsecretname}.'
                                response = {'message': message}
                                access_code = 204
                    else:
                        LOGGER.error('Kindly pass the new secret name.')
                        response = {'message': 'Kindly pass the new secret name.'}
                        access_code = 404
                else:
                    LOGGER.error(f'Group {name}, Secret {secret} is unavailable.')
                    response = {'message': f'Group {name}, Secret {secret} is unavailable.'}
                    access_code = 404
            else:
                LOGGER.error('Kindly provide at least one secret.')
                response = {'message': 'Kindly provide at least one secret.'}
                access_code = 404
        else:
            LOGGER.error(f'Group {name} is not available.')
            response = {'message': f'Group {name} is not available.'}
            access_code = 404
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route('/config/secrets/group/<string:name>/<string:secret>/_delete', methods=['GET'])
###@token_required
def config_group_secret_delete(name=None, secret=None):
    """
    Input - Group Name & Secret Name
    Output - Success or Failure
    """
    group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
    if group:
        groupid  = group[0]['id']
        where = f' WHERE groupid = "{groupid}" AND name = "{secret}"'
        db_secret = Database().get_record(None, 'groupsecrets', where)
        if db_secret:
            where = [{"column": "groupid", "value": groupid}, {"column": "name", "value": secret}]
            Database().delete_row('groupsecrets', where)
            response = {'message': f'Secret {secret} deleted from group {name}.'}
            access_code = 204
        else:
            LOGGER.error(f'Secret {secret} is unavailable for group {name}.')
            response = {'message': f'Secret {secret} is unavailable for group {name}.'}
            access_code = 404
    else:
        LOGGER.error(f'Group {name} is not available.')
        response = {'message': f'Group {name} is not available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route('/config/status/<string:request_id>', methods=['GET'])
def control_status(request_id=None):
    """
    Input - request_id
    Process - gets the list from status table. renders this into a response.
    Output - Success or failure
    """

    LOGGER.info(f"control STATUS: request_id: [{request_id}]")
    access_code = 400
    response = {'message': 'Bad Request.'}
    status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
    if status:
        message=[]
        for record in status:
            if 'read' in record:
                if record['read']==0:
                    if 'message' in record:
                        if record['message'] == "EOF":
                            Database().delete_row('status', [{"column": "request_id", "value": request_id}])
                        else:
                            created,*_=(record['created'].split('.')+[None])
                            message.append(created+" :: "+record['message'])
        response={'message': (';;').join(message) }
        where = [{"column": "request_id", "value": request_id}]
        row = [{"column": "read", "value": "1"}]
        Database().update('status', row, where)
        access_code = 200
    return json.dumps(response), access_code

