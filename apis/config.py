#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This File is a A Entry Point of Every Configuration Related Activity.
@token_required is a Wrapper Method to Validate the POST API. It contains
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
from common.validate_auth import token_required
from utils.database import Database
from utils.log import Log
from utils.helper import Helper
from common.constant import CONFIGFILE

LOGGER = Log.get_logger()
config_blueprint = Blueprint('config', __name__)

############################# Node configuration #############################

@config_blueprint.route('/config/node', methods=['GET'])
@token_required
def config_node():
    """
    Input - None
    Output - Return the List Of Nodes.
    """
    nodes = Database().get_record(None, 'node', None)
    if nodes:
        response = {'config': {'node': {} }}
        for node in nodes:
            node_name = node['name']
            nodeid = node['id']
            if node['bmcsetupid']:
                node['bmcsetup'] = Database().getname_byid('bmcsetup', node['bmcsetupid'])
            if node['groupid']:
                node['group'] = Database().getname_byid('group', node['groupid'])
            if node['osimageid']:
                node['osimage'] = Database().getname_byid('osimage', node['osimageid'])
            if node['switchid']:
                node['switch'] = Database().getname_byid('switch', node['switchid'])
            del node['name']
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
            where = f' WHERE nodeid = "{nodeid}"'
            node_interface = Database().get_record(None, 'nodeinterface', where)
            if node_interface:
                node['interfaces'] = []
                for interface in node_interface:
                    interface['network'] = Database().getname_byid('network',interface['networkid'])
                    del interface['nodeid']
                    del interface['id']
                    del interface['networkid']
                    node['interfaces'].append(interface)
            response['config']['node'][node_name] = node
        LOGGER.info('Provided List Of All Nodes.')
        access_code = 200
    else:
        LOGGER.error('No Node is available.')
        response = {'message': 'No Node is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route('/config/node/<string:name>', methods=['GET'])
@token_required
def config_node_get(name=None):
    """
    Input - None
    Output - Return the Node Information.
    """
    node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
    if node:
        response = {'config': {'node': {} }}
        node = node[0]
        nodename = node['name']
        nodeid = node['id']
        if node['bmcsetupid']:
            node['bmcsetup'] = Database().getname_byid('bmcsetup', node['bmcsetupid'])
        if node['groupid']:
            node['group'] = Database().getname_byid('group', node['groupid'])
        if node['osimageid']:
            node['osimage'] = Database().getname_byid('osimage', node['osimageid'])
        if node['switchid']:
            node['switch'] = Database().getname_byid('switch', node['switchid'])
        del node['name']
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
        node_interface = Database().get_record(None, 'nodeinterface', f' WHERE nodeid = "{nodeid}"')
        if node_interface:
            node['interfaces'] = []
            for interface in node_interface:
                interface['network'] = Database().getname_byid('network', interface['networkid'])
                del interface['nodeid']
                del interface['id']
                del interface['networkid']
                node['interfaces'].append(interface)
        response['config']['node'][nodename] = node
        LOGGER.info('Provided List Of All Nodes.')
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
    Input - Node Name
    Process - Create Or Update The Groups.
    Output - Node Information.
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
        data = request_data['config']['node'][name]
        node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if node:
            nodeid = node[0]['id']
            if 'newnodename' in data:
                nodename_new = data['newnodename']
                where = f' WHERE `name` = "{nodename_new}";'
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
                response = {'message': f'Node {name} Updated Successfully.'}
                access_code = 204
            if create:
                data['name'] = name
                row = Helper().make_rows(data)
                nodeid = Database().insert('node', row)
                response = {'message': f'Node {name} Created Successfully.'}
                access_code = 201
            if interfaces:
                for interface in interfaces:
                    networkid = Database().getid_byname('network', interface['network'])
                    if networkid is None:
                        response = {'message': f'Bad Request; Network {networkid} Not Exist.'}
                        access_code = 400
                        return json.dumps(response), access_code
                    else:
                        interface['networkid'] = networkid
                        interface['nodeid'] = nodeid
                        del interface['network']
                    interface_name = interface['interface']
                    node_clause = f'nodeid = "{nodeid}"'
                    network_clause = f'networkid = "{networkid}"'
                    interface_clause = f'interface = "{interface_name}"'
                    where = f' WHERE {node_clause} AND {network_clause} AND {interface_clause}'
                    check_interface = Database().get_record(None, 'nodeinterface', where)
                    if not check_interface:
                        row = Helper().make_rows(interface)
                        result = Database().insert('nodeinterface', row)
                        LOGGER.info(f"Interface Created => {result} .")

        else:
            response = {'message': 'Bad Request; Columns are Incorrect.'}
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
    node = Database().get_record(None, 'node', f' WHERE `name` = "{name}";')
    if node:
        Database().delete_row('node', [{"column": "name", "value": name}])
        Database().delete_row('nodeinterface', [{"column": "nodeid", "value": node[0]['id']}])
        Database().delete_row('nodesecrets', [{"column": "nodeid", "value": node[0]['id']}])
        response = {'message': f'Node {name} with all its interfaces Removed Successfully.'}
        access_code = 204
    else:
        response = {'message': f'Node {name} Not Present in Database.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route('/config/node/<string:name>/interfaces', methods=['GET'])
@token_required
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
        where = f' WHERE nodeid = "{nodeid}"'
        node_interfaces = Database().get_record(None, 'nodeinterface', where)
        if node_interfaces:
            new_interfaces = []
            for interface in node_interfaces:
                interface['network'] = Database().getname_byid('network', interface['networkid'])
                del interface['nodeid']
                del interface['id']
                del interface['networkid']
                new_interfaces.append(interface)
            response['config']['node'][name]['interfaces'] = new_interfaces
            LOGGER.info(f'Returned Group {name} with Details.')
            access_code = 200
        else:
            LOGGER.error(f'Node {name} dont have any Interface.')
            response = {'message': f'Node {name} dont have any Interface.'}
            access_code = 404
    else:
        LOGGER.error('No Node is available.')
        response = {'message': 'No Node is available.'}
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
                    networkid = Database().getid_byname('network', interface['network'])
                    if networkid is None:
                        response = {'message': f'Bad Request; Network {networkid} Not Exist.'}
                        access_code = 400
                        return json.dumps(response), access_code
                    else:
                        interface['networkid'] = networkid
                        interface['nodeid'] = nodeid
                        del interface['network']
                    interface_name = interface['interface']
                    node_clause = f'nodeid = "{nodeid}"'
                    network_clause = f'networkid = "{networkid}"'
                    interface_clause = f'interface = "{interface_name}"'
                    where = f' WHERE {node_clause} AND {network_clause} AND {interface_clause}'
                    interface_check = Database().get_record(None, 'nodeinterface', where)
                    if not interface_check:
                        row = Helper().make_rows(interface)
                        Database().insert('nodeinterface', row)
                    response = {'message': 'Interface Updated.'}
                    access_code = 204
            else:
                LOGGER.error('Kindly Provide the interface.')
                response = {'message': 'Kindly Provide the interface.'}
                access_code = 404
        else:
            LOGGER.error(f'Node {name} is Not available.')
            response = {'message': f'Node {name} is Not available.'}
            access_code = 404
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route("/config/node/<string:name>/interfaces/<string:interface>", methods=['GET'])
@token_required
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
        where = f' WHERE nodeid = "{nodeid}" AND interface = "{interface}"'
        node_interfaces = Database().get_record(None, 'nodeinterface', where)
        if node_interfaces:
            new_interface = []
            for ifx in node_interfaces:
                ifx['network'] = Database().getname_byid('network', ifx['networkid'])
                del ifx['nodeid']
                del ifx['id']
                del ifx['networkid']
                new_interface.append(ifx)
            response['config']['node'][name]['interfaces'] = new_interface
            LOGGER.info(f'Returned Group {name} with Details.')
            access_code = 200
        else:
            LOGGER.error(f'Node {name} dont have {interface} Interface.')
            response = {'message': f'Node {name} dont have {interface} Interface.'}
            access_code = 404
    else:
        LOGGER.error('No Node is available.')
        response = {'message': 'No Node is available.'}
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
    node = Database().get_record(None, 'node', f' WHERE `name` = "{name}";')
    if node:
        nodeid = node[0]['id']
        node_interface = Database().get_record(None, 'nodeinterface', f' WHERE `interface` = "{interface}" AND `nodeid` = "{nodeid}";')
        if node_interface:
            Database().delete_row('nodeinterface', [{"column": "id", "value": node_interface[0]['id']}])
            response = {'message': f'Node {name} interface {interface} Removed Successfully.'}
            access_code = 204
        else:
            response = {'message': f'Node {name} interface {interface} Not Present in Database.'}
            access_code = 404
    else:
        response = {'message': f'Node {name} Not Present in Database.'}
        access_code = 404
    return json.dumps(response), access_code

######################################################## Group configuration #############################################################

@config_blueprint.route("/config/group", methods=['GET'])
@token_required
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
            grp_interface = Database().get_record(None, 'groupinterface', f' WHERE groupid = "{grpid}"')
            if grp_interface:
                grp['interfaces'] = []
                for interface in grp_interface:
                    interface['network'] = Database().getname_byid('network', interface['networkid'])
                    del interface['groupid']
                    del interface['id']
                    del interface['networkid']
                    grp['interfaces'].append(interface)
            del grp['id']
            del grp['name']
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
        LOGGER.info('Provided List Of All Groups with Details.')
        access_code = 200
    else:
        LOGGER.error('No Group is available.')
        response = {'message': 'No Group is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/group/<string:name>", methods=['GET'])
@token_required
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
            grp_interface = Database().get_record(None, 'groupinterface', f' WHERE groupid = "{grpid}"')
            if grp_interface:
                grp['interfaces'] = []
                for interface in grp_interface:
                    interface['network'] = Database().getname_byid('network', interface['networkid'])
                    del interface['groupid']
                    del interface['id']
                    del interface['networkid']
                    grp['interfaces'].append(interface)
            del grp['id']
            del grp['name']
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
        LOGGER.error('No Group is available.')
        response = {'message': 'No Group is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/group/<string:name>", methods=['POST'])
@token_required
def config_group_post(name=None):
    """
    Input - Group ID or Name
    Process - Create Or Update The Groups.
    Output - Group Information.
    """
    DATA = {}
    CREATE, UPDATE = False, False

    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['group'][name]
        GRP = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if GRP:
            GRPID = GRP[0]['id']
            if 'newgroupname' in DATA:
                NEWGRPNAME = DATA['newgroupname']
                CHECKNEWGRP = Database().get_record(None, 'group', f' WHERE `name` = "{NEWGRPNAME}";')
                if CHECKNEWGRP:
                    response = {'message': f'{NEWGRPNAME} Already Present in Database, Choose Another Name Or Delete {NEWGRPNAME}.'}
                    access_code = 400
                    return json.dumps(response), access_code
                else:
                    DATA['name'] = DATA['newgroupname']
                    del DATA['newgroupname']
            UPDATE = True
            if 'bmcsetup' in DATA:
                DATA['bmcsetup'] = Helper().bool_revert(DATA['bmcsetup'])
            if 'netboot' in DATA:
                DATA['netboot'] = Helper().bool_revert(DATA['netboot'])
            if 'localinstall' in DATA:
                DATA['localinstall'] = Helper().bool_revert(DATA['localinstall'])
            if 'bootmenu' in DATA:
                DATA['bootmenu'] = Helper().bool_revert(DATA['bootmenu'])
        else:
            if 'newgroupname' in DATA:
                response = {'message': f'{NEWGRPNAME} is not allwoed while creating a new group.'}
                access_code = 400
                return json.dumps(response), access_code
            if 'bmcsetup' in DATA:
                DATA['bmcsetup'] = Helper().bool_revert(DATA['bmcsetup'])
            else:
                DATA['bmcsetup'] = 0
            if 'netboot' in DATA:
                DATA['netboot'] = Helper().bool_revert(DATA['netboot'])
            else:
                DATA['netboot'] = 0
            if 'localinstall' in DATA:
                DATA['localinstall'] = Helper().bool_revert(DATA['localinstall'])
            else:
                DATA['localinstall'] = 0
            if 'bootmenu' in DATA:
                DATA['bootmenu'] = Helper().bool_revert(DATA['bootmenu'])
            else:
                DATA['bootmenu'] = 0
            CREATE = True
        if 'bmcsetupname' in DATA:
            BMCNAME = DATA['bmcsetupname']
            DATA['bmcsetupid'] = Database().getid_byname('bmcsetup', DATA['bmcsetupname'])
            if DATA['bmcsetupid']:
                del DATA['bmcsetupname']
            else:
                response = {'message': f'BMC Setup {BMCNAME} does not exist, Choose Another BMC Setup.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'osimage' in DATA:
            OSNAME = DATA['osimage']
            del DATA['osimage']
            DATA['osimageid'] = Database().getid_byname('osimage', OSNAME)
        if not DATA['bmcsetupid']:
            response = {'message': f'BMC Setup {OSNAME} does not exist, Choose Another BMC Setup.'}
            access_code = 400
            return json.dumps(response), access_code
        if 'interfaces' in DATA:
            NEWINTERFACE = DATA['interfaces']
            del DATA['interfaces']

        GRPCOLUMNS = Database().get_columns('group')
        COLUMNCHECK = Helper().checkin_list(DATA, GRPCOLUMNS)
        if COLUMNCHECK:
            if UPDATE:
                where = [{"column": "id", "value": GRPID}]
                row = Helper().make_rows(DATA)
                UPDATEID = Database().update('group', row, where)
                response = {'message': f'Group {name} Updated Successfully.'}
                access_code = 204
            if CREATE:
                DATA['name'] = name
                row = Helper().make_rows(DATA)
                GRPID = Database().insert('group', row)
                response = {'message': f'Group {name} Created Successfully.'}
                access_code = 201
            if NEWINTERFACE:
                for INTERFACE in NEWINTERFACE:
                    NWK = Database().getid_byname('network', INTERFACE['network'])
                    if NWK == None:
                        response = {'message': f'Bad Request; Network {NWK} Not Exist.'}
                        access_code = 400
                        return json.dumps(response), access_code
                    else:
                        INTERFACE['networkid'] = NWK
                        INTERFACE['groupid'] = GRPID
                        del INTERFACE['network']
                    IFNAME = INTERFACE['interfacename']
                    where = f' WHERE groupid = "{GRPID}" AND networkid = "{NWK}" AND interfacename = "{IFNAME}"'
                    CHECKINTERFACE = Database().get_record(None, 'groupinterface', where)
                    if not CHECKINTERFACE:
                        row = Helper().make_rows(INTERFACE)
                        result = Database().insert('groupinterface', row)
                        LOGGER.info("Interface Created => {} .".format(result))

        else:
            response = {'message': 'Bad Request; Columns are Incorrect.'}
            access_code = 400
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route("/config/group/<string:name>/_delete", methods=['GET'])
@token_required
def config_group_delete(name=None):
    """
    Input - Group Name
    Process - Delete the Group and it's interfaces.
    Output - Success or Failure.
    """
    CHECKGRP = Database().get_record(None, 'group', f' WHERE `name` = "{name}";')
    if CHECKGRP:
        Database().delete_row('group', [{"column": "name", "value": name}])
        Database().delete_row('groupinterface', [{"column": "groupid", "value": CHECKGRP[0]['id']}])
        Database().delete_row('groupsecrets', [{"column": "groupid", "value": CHECKGRP[0]['id']}])
        response = {'message': f'Group {name} with all its interfaces Removed Successfully.'}
        access_code = 204
    else:
        response = {'message': f'Group {name} Not Present in Database.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/group/<string:name>/interfaces", methods=['GET'])
@token_required
def config_group_get_interfaces(name=None):
    """
    Input - Group Name
    Process - Fetch the Group Interface List.
    Output - Group Interface List.
    """
    GROUPS = Database().get_record(None, 'group', f' WHERE name = "{name}"')
    if GROUPS:
        response = {'config': {'group': {name: {'interfaces': [] } } } }
        for GRP in GROUPS:
            GRPNAME = GRP['name']
            GRPID = GRP['id']
            GRPINTERFACE = Database().get_record(None, 'groupinterface', f' WHERE groupid = "{GRPID}"')
            if GRPINTERFACE:
                GRPIFC = []
                for INTERFACE in GRPINTERFACE:
                    INTERFACE['network'] = Database().getname_byid('network', INTERFACE['networkid'])
                    del INTERFACE['groupid']
                    del INTERFACE['id']
                    del INTERFACE['networkid']
                    GRPIFC.append(INTERFACE)
                response['config']['group'][GRPNAME]['interfaces'] = GRPIFC
            else:
                LOGGER.error(f'No Group {name} dont have any Interface.')
                response = {'message': f'No Group {name} dont have any Interface.'}
                access_code = 404
        LOGGER.info(f'Returned Group {name} with Details.')
        access_code = 200
    else:
        LOGGER.error('No Group is available.')
        response = {'message': 'No Group is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/group/<string:name>/interfaces", methods=['POST'])
@token_required
def config_group_post_interfaces(name=None):
    """
    Input - Group Name
    Process - Create Or Update The Group Interface.
    Output - Group Interface.
    """
    DATA = {}
    CREATE, UPDATE = False, False

    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        GRP = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if GRP:
            GRPID = GRP[0]['id']
            if 'interfaces' in REQUEST['config']['group'][name]:
                for INTERFACE in REQUEST['config']['group'][name]['interfaces']:
                    NWK = Database().getid_byname('network', INTERFACE['network'])
                    if NWK == None:
                        response = {'message': f'Bad Request; Network {NWK} Not Exist.'}
                        access_code = 400
                        return json.dumps(response), access_code
                    else:
                        INTERFACE['networkid'] = NWK
                        INTERFACE['groupid'] = GRPID
                        del INTERFACE['network']
                    IFNAME = INTERFACE['interfacename']
                    where = f' WHERE groupid = "{GRPID}" AND networkid = "{NWK}" AND interfacename = "{IFNAME}"'
                    CHECKINTERFACE = Database().get_record(None, 'groupinterface', where)
                    if not CHECKINTERFACE:
                        row = Helper().make_rows(INTERFACE)
                        result = Database().insert('groupinterface', row)
                    response = {'message': 'Interface Updated.'}
                    access_code = 204
            else:
                LOGGER.error('Kindly Provide the interface.')
                response = {'message': 'Kindly Provide the interface.'}
                access_code = 404
        else:
            LOGGER.error('No Group is available.')
            response = {'message': 'No Group is available.'}
            access_code = 404
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
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
    CHECKGRP = Database().get_record(None, 'group', f' WHERE `name` = "{name}";')
    if CHECKGRP:
        GRPID = CHECKGRP[0]['id']
        CHECKGRPIFC = Database().get_record(None, 'groupinterface', f' WHERE `interfacename` = "{interface}" AND `groupid` = "{GRPID}";')
        if CHECKGRPIFC:
            Database().delete_row('groupinterface', [{"column": "id", "value": CHECKGRPIFC[0]['id']}])
            response = {'message': f'Group {name} interface {interface} Removed Successfully.'}
            access_code = 204
        else:
            response = {'message': f'Group {name} interface {interface} Not Present in Database.'}
            access_code = 404
    else:
        response = {'message': f'Group {name} Not Present in Database.'}
        access_code = 404
    return json.dumps(response), access_code

######################################################## OSimage configuration #############################################################

@config_blueprint.route("/config/osimage", methods=['GET'])
def config_osimage():
    """
    Input - OS Image ID or Name
    Process - Fetch the OS Image information.
    Output - OSImage Info.
    """
    OSIMAGES = Database().get_record(None, 'osimage', None)
    if OSIMAGES:
        response = {'config': {'osimage': {} }}
        for IMAGE in OSIMAGES:
            IMAGENAME = IMAGE['name']
            del IMAGE['id']
            del IMAGE['name']
            response['config']['osimage'][IMAGENAME] = IMAGE
        LOGGER.info('Provided List Of All OS Images with Details.')
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
    OSIMAGES = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
    if OSIMAGES:
        response = {'config': {'osimage': {} }}
        for IMAGE in OSIMAGES:
            del IMAGE['id']
            del IMAGE['name']
            response['config']['osimage'][name] = IMAGE
        LOGGER.info(f'Returned OS Image {name} with Details.')
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
    DATA = {}
    CREATE, UPDATE = False, False
    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['osimage'][name]
        IMAGE = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
        if IMAGE:
            IMAGEID = IMAGE[0]['id']
            if 'newosimage' in DATA:
                NEWOSNAME = DATA['newosimage']
                CHECKNEWOS = Database().get_record(None, 'osimage', f' WHERE `name` = "{NEWOSNAME}";')
                if CHECKNEWOS:
                    response = {'message': f'{NEWOSNAME} Already Present in Database, Choose Another Name Or Delete {NEWOSNAME}.'}
                    access_code = 400
                    return json.dumps(response), access_code
                else:
                    DATA['name'] = DATA['newosimage']
                    del DATA['newosimage']
                UPDATE = True
            else:
                response = {'message': 'Kindly Pass The New OS Image Name.'}
                access_code = 400
                return json.dumps(response), access_code
        else:
            if 'newosimage' in DATA:
                NEWOSNAME = DATA['newosimage']
                CHECKNEWOS = Database().get_record(None, 'osimage', f' WHERE `name` = "{NEWOSNAME}";')
                if CHECKNEWOS:
                    response = {'message': f'{NEWOSNAME} Already Present in Database, Choose Another Name Or Delete {NEWOSNAME}.'}
                    access_code = 400
                    return json.dumps(response), access_code
                else:
                    DATA['name'] = DATA['newosimage']
                    del DATA['newosimage']
                CREATE = True
            else:
                response = {'message': 'Kindly Pass The New OS Image Name.'}
                access_code = 400
                return json.dumps(response), access_code

        OSIMAGECOLUMNS = Database().get_columns('osimage')
        COLUMNCHECK = Helper().checkin_list(DATA, OSIMAGECOLUMNS)
        if COLUMNCHECK:
            if UPDATE:
                where = [{"column": "id", "value": IMAGEID}]
                row = Helper().make_rows(DATA)
                result = Database().update('osimage', row, where)
                response = {'message': f'OS Image {name} Updated Successfully.'}
                access_code = 204
            if CREATE:
                DATA['name'] = name
                row = Helper().make_rows(DATA)
                result = Database().insert('osimage', row)
                response = {'message': f'OS Image {name} Created Successfully.'}
                access_code = 201
        else:
            response = {'message': 'Bad Request; Columns are Incorrect.'}
            access_code = 400
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
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
    CHECKOSIMAGE = Database().get_record(None, 'osimage', f' WHERE `name` = "{name}";')
    if CHECKOSIMAGE:
        Database().delete_row('osimage', [{"column": "name", "value": name}])
        response = {'message': f'OS Image {name} Removed Successfully.'}
        access_code = 204
    else:
        response = {'message': f'OS Image {name} Not Present in Database.'}
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
    DATA = {}
    CREATE = False
    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['osimage'][name]
        IMAGE = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
        if IMAGE:
            if 'newosimage' in DATA:
                NEWOSNAME = DATA['newosimage']
                CHECKNEWOS = Database().get_record(None, 'osimage', f' WHERE `name` = "{NEWOSNAME}";')
                if CHECKNEWOS:
                    response = {'message': f'{NEWOSNAME} Already Present in Database, Choose Another Name Or Delete {NEWOSNAME}.'}
                    access_code = 400
                    return json.dumps(response), access_code
                else:
                    DATA['name'] = DATA['newosimage']
                    del DATA['newosimage']
                    CREATE = True
            else:
                response = {'message': 'Kindly Pass The New OS Image Name.'}
                access_code = 400
                return json.dumps(response), access_code
        else:
            response = {'message': f'OS Image {name} Not Present In the Database.'}
            access_code = 400
            return json.dumps(response), access_code

        OSIMAGECOLUMNS = Database().get_columns('osimage')
        COLUMNCHECK = Helper().checkin_list(DATA, OSIMAGECOLUMNS)
        if COLUMNCHECK:
            if CREATE:
                row = Helper().make_rows(DATA)
                result = Database().insert('osimage', row)
                response = {'message': f'OS Image {name} Clone to {NEWOSNAME} Successfully.'}
                access_code = 201
        else:
            response = {'message': 'Bad Request; Columns are Incorrect.'}
            access_code = 400
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
    return json.dumps(response), access_code



@config_blueprint.route("/config/osimage/<string:name>/pack", methods=['GET'])
@token_required
def config_osimage_pack(name=None):
    """
    Input - OS Image ID or Name
    Process - Manually Pack the OS Image.
    Output - Success or Failure.
    """
    LOGGER.info("OS Image {} Packed Successfully.".format(name))
    response = {"message": "OS Image {} Packed Successfully.".format(name)}
    code = 200
    return json.dumps(response), code


@config_blueprint.route("/config/osimage/<string:name>/kernel", methods=['POST'])
# @token_required
def config_osimage_kernel_post(name=None):
    """
    Input - OS Image Name
    Process - Manually change kernel version.
    Output - Kernel Version.
    """
    DATA = {}
    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['osimage'][name]
        IMAGE = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
        if IMAGE:
            IMAGEID = IMAGE[0]['id']
            OSIMAGECOLUMNS = Database().get_columns('osimage')
            COLUMNCHECK = Helper().checkin_list(DATA, OSIMAGECOLUMNS)
            if COLUMNCHECK:
                REQUESTCHECK = Helper().pack(name)
                print(f'REQUESTCHECK=======>> {REQUESTCHECK}')
                # where = [{"column": "id", "value": IMAGEID}]
                # row = Helper().make_rows(DATA)
                # result = Database().update('osimage', row, where)
                response = {'message': f'OS Image {name} Kernel Updated Successfully.'}
                access_code = 204
            else:
                response = {'message': 'Bad Request; Columns are Incorrect.'}
                access_code = 400
        else:
            response = {'message': f'OS Image {name} Dose Not Exist.'}
            access_code = 400
            return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
    return json.dumps(response), access_code


######################################################## Cluster configuration #############################################################


@config_blueprint.route("/config/cluster", methods=['GET'])
@token_required
def config_cluster():
    """
    Input - None
    Process - Fetch The Cluster Information.
    Output - Cluster Information.
    """
    CLUSTER = Database().get_record(None, 'cluster', None)
    if CLUSTER:
        CLUSTERID = CLUSTER[0]['id']
        del CLUSTER[0]['id']
        if CLUSTER[0]['debug']:
            CLUSTER[0]['debug'] = True
        else:
            CLUSTER[0]['debug'] = False
        if CLUSTER[0]['security']:
            CLUSTER[0]['security'] = True
        else:
            CLUSTER[0]['security'] = False
        response = {'config': {'cluster': CLUSTER[0] }}
        CONTROLLERS = Database().get_record(None, 'controller', f' WHERE clusterid = {CLUSTERID}')
        for CONTROLLER in CONTROLLERS:
            CONTROLLERIP = Database().get_record(None, 'ipaddress', f' WHERE id = {CONTROLLER["ipaddr"]}')
            if CONTROLLERIP:
                CONTROLLER['ipaddress'] = CONTROLLERIP[0]["ipaddress"]
            del CONTROLLER['id']
            del CONTROLLER['clusterid']
            CONTROLLER['luna_config'] = CONFIGFILE
            response['config']['cluster'][CONTROLLER['hostname']] = CONTROLLER
            access_code = 200
    else:
        LOGGER.error('No Cluster is available.')
        response = {'message': 'No Cluster is available.'}
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
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['cluster']
        CLUSTERCOLUMNS = Database().get_columns('cluster')
        COLUMNCHECK = Helper().checkin_list(DATA, CLUSTERCOLUMNS)
        if COLUMNCHECK:
            CLUSTER = Database().get_record(None, 'cluster', None)
            if CLUSTER:
                where = [{"column": "id", "value": CLUSTER[0]['id']}]
                row = Helper().make_rows(DATA)
                result = Database().update('cluster', row, where)
                response = {'message': 'Cluster Updated Successfully.'}
                access_code = 204
            else:
                response = {'message': 'Bad Request; No Cluster is available to Update.'}
                access_code = 400
        else:
            response = {'message': 'Bad Request; Columns are Incorrect.'}
            access_code = 400
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
    return json.dumps(response), 200


######################################################## BMC setup configuration #############################################################

@config_blueprint.route("/config/bmcsetup", methods=['GET'])
@token_required
def config_bmcsetup():
    """
    Input - None
    Process - Fetch The list of configured settings.
    Output - List Of BMC Setup.
    """
    BMCSETUP = Database().get_record(None, 'bmcsetup', None)
    if BMCSETUP:
        response = {'config': {'bmcsetup': {} }}
        for BMC in BMCSETUP:
            BMCNAME = BMC['name']
            del BMC['name']
            del BMC['id']
            response['config']['bmcsetup'][BMCNAME] = BMC
        access_code = 200
    else:
        LOGGER.error('No BMC Setup is available.')
        response = {'message': 'No BMC Setup is available.'}
        access_code = 404
    return json.dumps(response), access_code



@config_blueprint.route("/config/bmcsetup/<string:bmcname>", methods=['GET'])
@token_required
def config_bmcsetup_get(bmcname=None):
    """
    Input - BMC Setup ID or Name
    Process - Fetch The BMC Setup information.
    Output - BMC Setup Information.
    """
    BMCSETUP = Database().get_record(None, 'bmcsetup', f' WHERE name = "{bmcname}"')
    if BMCSETUP:
        response = {'config': {'bmcsetup': {} }}
        for BMC in BMCSETUP:
            BMCNAME = BMC['name']
            del BMC['name']
            del BMC['id']
            response['config']['bmcsetup'][BMCNAME] = BMC
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
    DATA = {}
    CREATE, UPDATE = False, False
    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['bmcsetup'][bmcname]
        DATA['name'] = bmcname
        CHECKBMC = Database().get_record(None, 'bmcsetup', f' WHERE `name` = "{bmcname}";')
        if CHECKBMC:
            BMCID = CHECKBMC[0]['id']
            if 'newbmcname' in REQUEST['config']['bmcsetup'][bmcname]:
                DATA['name'] = DATA['newbmcname']
                del DATA['newbmcname']
            UPDATE = True
        else:
            CREATE = True
        BMCCOLUMNS = Database().get_columns('bmcsetup')
        COLUMNCHECK = Helper().checkin_list(DATA, BMCCOLUMNS)
        row = Helper().make_rows(DATA)
        if COLUMNCHECK:
            if CREATE:
                result = Database().insert('bmcsetup', row)
                response = {'message': 'BMC Setup Created Successfully.'}
                access_code = 201
            if UPDATE:
                where = [{"column": "id", "value": BMCID}]
                result = Database().update('bmcsetup', row, where)
                response = {'message': 'BMC Setup Updated Successfully.'}
                access_code = 204
        else:
            response = {'message': 'Bad Request; Columns are Incorrect.'}
            access_code = 400
            return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(DATA), access_code



@config_blueprint.route("/config/bmcsetup/<string:bmcname>/_clone", methods=['POST'])
@token_required
def config_bmcsetup_clone(bmcname=None):
    """
    Input - BMC Setup ID or Name
    Process - Fetch BMC Setup and Credentials.
    Output - BMC Name And Credentials.
    """
    DATA = {}
    CREATE = False
    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['bmcsetup'][bmcname]
        if 'newbmcname' in DATA:
            DATA['name'] = DATA['newbmcname']
            NEWBMCNAME = DATA['newbmcname']
            del DATA['newbmcname']
        else:
            response = {'message': 'Kindly Provide the New BMC Name.'}
            access_code = 400
            return json.dumps(response), access_code
        CHECKBMC = Database().get_record(None, 'bmcsetup', f' WHERE `name` = "{bmcname}";')
        if CHECKBMC:
            CHECKNEWBMC = Database().get_record(None, 'bmcsetup', f' WHERE `name` = "{NEWBMCNAME}";')
            if CHECKNEWBMC:
                response = {'message': f'{NEWBMCNAME} Already Present in Database.'}
                access_code = 400
                return json.dumps(response), access_code
            else:
                CREATE = True
        else:
            response = {'message': f'{bmcname} Not Present in Database.'}
            access_code = 400
            return json.dumps(response), access_code
        BMCCOLUMNS = Database().get_columns('bmcsetup')
        COLUMNCHECK = Helper().checkin_list(DATA, BMCCOLUMNS)
        row = Helper().make_rows(DATA)
        if COLUMNCHECK:
            if CREATE:
                result = Database().insert('bmcsetup', row)
                response = {'message': 'BMC Setup Created Successfully.'}
                access_code = 201
        else:
            response = {'message': 'Bad Request; Columns are Incorrect.'}
            access_code = 400
            return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(DATA), access_code


@config_blueprint.route("/config/bmcsetup/<string:bmcname>/_delete", methods=['GET'])
@token_required
def config_bmcsetup_delete(bmcname=None):
    """
    Input - BMC Setup ID or Name
    Process - Delete The BMC Setup Credentials.
    Output - Success or Failure.
    """
    CHECKBMC = Database().get_record(None, 'bmcsetup', f' WHERE `name` = "{bmcname}";')
    if CHECKBMC:
        Database().delete_row('bmcsetup', [{"column": "name", "value": bmcname}])
        response = {'message': 'BMC Setup Removed Successfully.'}
        access_code = 204
    else:
        response = {'message': f'{bmcname} not present in the database.'}
        access_code = 404
    return json.dumps(response), access_code



######################################################## Switch configuration #############################################################

@config_blueprint.route("/config/switch", methods=['GET'])
@token_required
def config_switch():
    """
    Input - None
    Process - Fetch The List Of Switches.
    Output - Switches.
    """
    SWITCHES = Database().get_record(None, 'switch', None)
    if SWITCHES:
        response = {'config': {'switch': { } }}
        for SWITCH in SWITCHES:
            SWITCHNAME = SWITCH['name']
            SWITCHIP = Database().get_record(None, 'ipaddress', f' WHERE id = {SWITCH["ipaddress"]}')
            LOGGER.debug(f'With Switch {SWITCHNAME} attached IP ROWs {SWITCHIP}')
            if SWITCHIP:
                SWITCH['ipaddress'] = SWITCHIP[0]["ipaddress"]
            del SWITCH['id']
            del SWITCH['name']
            response['config']['switch'][SWITCHNAME] = SWITCH
        LOGGER.info("available Switches are {}.".format(SWITCHES))
        access_code = 200
    else:
        LOGGER.error('No Switch is available.')
        response = {'message': 'No Switch is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/switch/<string:switch>", methods=['GET'])
@token_required
def config_switch_get(switch=None):
    """
    Input - Switch ID or Name
    Process - Fetch The Switch Information.
    Output - Switch Details.
    """
    SWITCHES = Database().get_record(None, 'switch', f' WHERE name = "{switch}"')
    if SWITCHES:
        response = {'config': {'switch': { } }}
        for SWITCH in SWITCHES:
            SWITCHNAME = SWITCH['name']
            SWITCHIP = Database().get_record(None, 'ipaddress', f' WHERE id = {SWITCH["ipaddress"]}')
            LOGGER.debug(f'With Switch {SWITCHNAME} attached IP ROWs {SWITCHIP}')
            if SWITCHIP:
                SWITCH['ipaddress'] = SWITCHIP[0]["ipaddress"]
            del SWITCH['id']
            del SWITCH['name']
            response['config']['switch'][SWITCHNAME] = SWITCH
        LOGGER.info("available Switches are {}.".format(SWITCHES))
        access_code = 200
    else:
        LOGGER.error('No Switch is available.')
        response = {'message': 'No Switch is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/switch/<string:switch>", methods=['POST'])
@token_required
def config_switch_post(switch=None):
    """
    Input - Switch ID or Name
    Process - Fetch The Switch Information.
    Output - Switch Details.
    """
    DATA = {}
    CREATE, UPDATE = False, False
    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['switch'][switch]
        DATA['name'] = switch
        CHECKSWITCH = Database().get_record(None, 'switch', f' WHERE `name` = "{switch}";')
        if CHECKSWITCH:
            SWITCHID = CHECKSWITCH[0]['id']
            if 'newswitchname' in REQUEST['config']['switch'][switch]:
                DATA['name'] = DATA['newswitchname']
                del DATA['newswitchname']
            UPDATE = True
        else:
            CREATE = True
        SWITCHCOLUMNS = Database().get_columns('switch')
        COLUMNCHECK = Helper().checkin_list(DATA, SWITCHCOLUMNS)
        DATA = Helper().check_ip_exist(DATA)
        if DATA:
            row = Helper().make_rows(DATA)
            if COLUMNCHECK:
                if CREATE:
                    result = Database().insert('switch', row)
                    response = {'message': 'Switch Created Successfully.'}
                    access_code = 201
                if UPDATE:
                    where = [{"column": "id", "value": SWITCHID}]
                    result = Database().update('switch', row, where)
                    response = {'message': 'Switch Updated Successfully.'}
                    access_code = 204
            else:
                response = {'message': 'Bad Request; Columns are Incorrect.'}
                access_code = 400
                return json.dumps(response), access_code
        else:
            response = {'message': 'Bad Request; IP Address Already Exist in The Database.'}
            access_code = 400
            return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(DATA), access_code



@config_blueprint.route("/config/switch/<string:switch>/_clone", methods=['POST'])
@token_required
def config_switch_clone(switch=None):
    """
    Input - Switch ID or Name
    Process - Delete The Switch.
    Output - Success or Failure.
    """
    DATA = {}
    CREATE = False
    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['switch'][switch]
        if 'newswitchname' in DATA:
            DATA['name'] = DATA['newswitchname']
            NEWSWITCHNAME = DATA['newswitchname']
            del DATA['newswitchname']
        else:
            response = {'message': 'Kindly Provide the New Switch Name.'}
            access_code = 400
            return json.dumps(response), access_code
        CHECKSWITCH = Database().get_record(None, 'switch', f' WHERE `name` = "{NEWSWITCHNAME}";')
        if CHECKSWITCH:
            response = {'message': f'{NEWSWITCHNAME} Already Present in Database.'}
            access_code = 400
            return json.dumps(response), access_code
        else:
            CREATE = True
        SWITCHCOLUMNS = Database().get_columns('switch')
        COLUMNCHECK = Helper().checkin_list(DATA, SWITCHCOLUMNS)
        DATA = Helper().check_ip_exist(DATA)
        if DATA:
            row = Helper().make_rows(DATA)
            if COLUMNCHECK:
                if CREATE:
                    result = Database().insert('switch', row)
                    response = {'message': 'Switch Created Successfully.'}
                    access_code = 201
            else:
                response = {'message': 'Bad Request; Columns are Incorrect.'}
                access_code = 400
                return json.dumps(response), access_code
        else:
            response = {'message': 'Bad Request; IP Address Already Exist in The Database.'}
            access_code = 400
            return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(DATA), access_code



@config_blueprint.route("/config/switch/<string:switch>/_delete", methods=['POST'])
@token_required
def config_switch_delete(switch=None):
    """
    Input - Switch ID or Name
    Process - Delete The Switch.
    Output - Success or Failure.
    """
    CHECKSWITCH = Database().get_record(None, 'switch', f' WHERE `name` = "{switch}";')
    if CHECKSWITCH:
        Database().delete_row('ipaddress', [{"column": "id", "value": CHECKSWITCH[0]['ipaddress']}])
        Database().delete_row('switch', [{"column": "name", "value": switch}])
        response = {'message': 'Switch Removed Successfully.'}
        access_code = 204
    else:
        response = {'message': f'{switch} Not Present in Database.'}
        access_code = 404
    return json.dumps(response), access_code


######################################################## Other Devices configuration #############################################################


@config_blueprint.route("/config/otherdev", methods=['GET'])
@token_required
def config_otherdev():
    """
    Input - None
    Process - Fetch The List Of Devices.
    Output - Devices.
    """
    DEVICES = Database().get_record(None, 'otherdevices', None)
    if DEVICES:
        response = {'config': {'otherdev': { } }}
        for DEVICE in DEVICES:
            DEVICENAME = DEVICE['name']
            DEVICEIP = Database().get_record(None, 'ipaddress', f' WHERE id = {DEVICE["ipaddress"]}')
            LOGGER.debug(f'With Device {DEVICENAME} attached IP ROWs {DEVICEIP}')
            if DEVICEIP:
                DEVICE['ipaddress'] = DEVICEIP[0]["ipaddress"]
            del DEVICE['id']
            del DEVICE['name']
            response['config']['otherdev'][DEVICENAME] = DEVICE
        LOGGER.info("available Devices are {}.".format(DEVICES))
        access_code = 200
    else:
        LOGGER.error('No Device is available.')
        response = {'message': 'No Device is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/otherdev/<string:device>", methods=['GET'])
@token_required
def config_otherdev_get(device=None):
    """
    Input - Device ID or Name
    Process - Fetch The List Of Devices.
    Output - Devices.
    """
    DEVICES = Database().get_record(None, 'otherdevices', f' WHERE name = "{device}"')
    if DEVICES:
        response = {'config': {'otherdev': { } }}
        for DEVICE in DEVICES:
            DEVICENAME = DEVICE['name']
            DEVICEIP = Database().get_record(None, 'ipaddress', f' WHERE id = {DEVICE["ipaddress"]}')
            LOGGER.debug(f'With Device {DEVICENAME} attached IP ROWs {DEVICEIP}')
            if DEVICEIP:
                DEVICE['ipaddress'] = DEVICEIP[0]["ipaddress"]
            del DEVICE['id']
            del DEVICE['name']
            response['config']['otherdev'][DEVICENAME] = DEVICE
        LOGGER.info("available Devices are {}.".format(DEVICES))
        access_code = 200
    else:
        LOGGER.error('No Device is available.')
        response = {'message': 'No Device is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/otherdev/<string:device>", methods=['POST'])
@token_required
def config_otherdev_post(device=None):
    """
    Input - Device Name
    Output - Create or Update Device.
    """
    DATA = {}
    CREATE, UPDATE = False, False
    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['otherdev'][device]
        DATA['name'] = device
        CHECKDEVICE = Database().get_record(None, 'otherdevices', f' WHERE `name` = "{device}";')
        if CHECKDEVICE:
            DEVICEID = CHECKDEVICE[0]['id']
            if 'newotherdevname' in REQUEST['config']['otherdev'][device]:
                DATA['name'] = DATA['newotherdevname']
                del DATA['newotherdevname']
            UPDATE = True
        else:
            CREATE = True
        DEVICECOLUMNS = Database().get_columns('otherdevices')
        COLUMNCHECK = Helper().checkin_list(DATA, DEVICECOLUMNS)
        DATA = Helper().check_ip_exist(DATA)
        if DATA:
            row = Helper().make_rows(DATA)
            if COLUMNCHECK:
                if CREATE:
                    result = Database().insert('otherdevices', row)
                    response = {'message': 'Device Created Successfully.'}
                    access_code = 201
                if UPDATE:
                    where = [{"column": "id", "value": DEVICEID}]
                    result = Database().update('otherdevices', row, where)
                    response = {'message': 'Device Updated Successfully.'}
                    access_code = 204
            else:
                response = {'message': 'Bad Request; Columns are Incorrect.'}
                access_code = 400
                return json.dumps(response), access_code
        else:
            response = {'message': 'Bad Request; IP Address Already Exist in The Database.'}
            access_code = 400
            return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(DATA), access_code



@config_blueprint.route("/config/otherdev/<string:device>/_clone", methods=['POST'])
@token_required
def config_otherdev_clone(device=None):
    """
    Input - Device ID or Name
    Output - Clone The Device.
    """
    DATA = {}
    CREATE = False
    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['otherdev'][device]
        if 'newotherdevname' in DATA:
            DATA['name'] = DATA['newotherdevname']
            NEWDEVICENAME = DATA['newotherdevname']
            del DATA['newotherdevname']
        else:
            response = {'message': 'Kindly Provide the New Device Name.'}
            access_code = 400
            return json.dumps(response), access_code
        CHECKDEVICE = Database().get_record(None, 'otherdevices', f' WHERE `name` = "{NEWDEVICENAME}";')
        if CHECKDEVICE:
            response = {'message': f'{NEWDEVICENAME} Already Present in Database.'}
            access_code = 400
            return json.dumps(response), access_code
        else:
            CREATE = True
        DEVICECOLUMNS = Database().get_columns('otherdevices')
        COLUMNCHECK = Helper().checkin_list(DATA, DEVICECOLUMNS)
        DATA = Helper().check_ip_exist(DATA)
        if DATA:
            row = Helper().make_rows(DATA)
            if COLUMNCHECK:
                if CREATE:
                    result = Database().insert('otherdevices', row)
                    response = {'message': 'Device Cloned Successfully.'}
                    access_code = 201
            else:
                response = {'message': 'Bad Request; Columns are Incorrect.'}
                access_code = 400
                return json.dumps(response), access_code
        else:
            response = {'message': 'Bad Request; IP Address Already Exist in The Database.'}
            access_code = 400
            return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(DATA), access_code



@config_blueprint.route("/config/otherdev/<string:device>/_delete", methods=['GET'])
@token_required
def config_otherdev_delete(device=None):
    """
    Input - Device ID or Name
    Process - Delete The Device.
    Output - Success or Failure.
    """
    CHECKDEVICE = Database().get_record(None, 'otherdevices', f' WHERE `name` = "{device}";')
    if CHECKDEVICE:
        Database().delete_row('ipaddress', [{"column": "id", "value": CHECKDEVICE[0]['ipaddress']}])
        Database().delete_row('otherdevices', [{"column": "name", "value": device}])
        response = {'message': 'Device Removed Successfully.'}
        access_code = 204
    else:
        response = {'message': f'{device} Not Present in Database.'}
        access_code = 404
    return json.dumps(response), access_code


######################################################## Network configuration #############################################################


@config_blueprint.route("/config/network", methods=['GET'])
@token_required
def config_network():
    """
    Input - None
    Process - Fetch The Network Information.
    Output - Network Information.
    """
    NETWORKS = Database().get_record(None, 'network', None)
    if NETWORKS:
        response = {'config': {'network': {} }}
        for NWK in NETWORKS:
            NWK['network'] = Helper().get_network(NWK['network'], NWK['subnet'])
            del NWK['id']
            del NWK['subnet']
            if not NWK['dhcp']:
                del NWK['dhcp_range_begin']
                del NWK['dhcp_range_end']
                NWK['dhcp'] = False
            else:
                NWK['dhcp'] = True
            response['config']['network'][NWK['name']] = NWK
        access_code = 200
    else:
        LOGGER.error('No Networks is available.')
        response = {'message': 'No Networks is available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/network/<string:name>", methods=['GET'])
@token_required
def config_network_get(name=None):
    """
    Input - Network Name
    Process - Fetch The Network Information.
    Output - Network Information.
    """
    NETWORKS = Database().get_record(None, 'network', f' WHERE `name` = "{name}";')
    if NETWORKS:
        response = {'config': {'network': {} }}
        for NWK in NETWORKS:
            NWK['network'] = Helper().get_network(NWK['network'], NWK['subnet'])
            del NWK['id']
            del NWK['subnet']
            if not NWK['dhcp']:
                del NWK['dhcp_range_begin']
                del NWK['dhcp_range_end']
                NWK['dhcp'] = False
            else:
                NWK['dhcp'] = True
            response['config']['network'][NWK['name']] = NWK
        access_code = 200
    else:
        LOGGER.error(f'Network {name} is Not available.')
        response = {'message': f'Network {name} is Not available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/network/<string:name>", methods=['POST'])
@token_required
def config_network_post(name=None):
    """
    Input - Network Name
    Process - Create or Update Network information.
    Output - Success or Failure.
    """
    DATA = {}
    CREATE, UPDATE = False, False
    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['network'][name]
        DATA['name'] = name
        CHECKNETWORK = Database().get_record(None, 'network', f' WHERE `name` = "{name}";')
        if CHECKNETWORK:
            NETWORKID = CHECKNETWORK[0]['id']
            if 'newnetname' in REQUEST['config']['network'][name]:
                NEWNETWORKNAME = REQUEST['config']['network'][name]['newnetname']
                CHECKNEWNETWORK = Database().get_record(None, 'network', f' WHERE `name` = "{NEWNETWORKNAME}";')
                if CHECKNEWNETWORK:
                    response = {'message': f'{NEWNETWORKNAME} Already Present in Database, Choose Another Name Or Delete {NEWNETWORKNAME}.'}
                    access_code = 400
                    return json.dumps(response), access_code
                else:
                    DATA['name'] = DATA['newnetname']
                    del DATA['newnetname']
            UPDATE = True
        else:
            CREATE = True
        if 'network' in DATA:
            NWKIP = Helper().check_ip(DATA['network'])
            if NWKIP:
                NWKDETAILS = Helper().get_network_details(DATA['network'])
                DATA['network'] = NWKIP
                DATA['subnet'] = NWKDETAILS['subnet']
            else:
                response = {'message': f'Incorrect Network IP: {DATA["network"]}.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'gateway' in DATA:
            GWDETAILS = Helper().check_ip_range(DATA['gateway'], DATA['network']+'/'+DATA['subnet'])
            if not GWDETAILS:
                response = {'message': f'Incorrect Gateway IP: {DATA["gateway"]}.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'ns_ip' in DATA:
            NSIPDETAILS = Helper().check_ip_range(DATA['ns_ip'], DATA['network']+'/'+DATA['subnet'])
            if not NSIPDETAILS:
                response = {'message': f'Incorrect NS IP: {DATA["ns_ip"]}.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'ntp_server' in DATA:
            NTPDETAILS = Helper().check_ip_range(DATA['ntp_server'], DATA['network']+'/'+DATA['subnet'])
            if not NTPDETAILS:
                response = {'message': f'Incorrect NTP Server IP: {DATA["ntp_server"]}.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'dhcp' in DATA:
            if 'dhcp_range_begin' in DATA:
                DHCPSTARTDETAILS = Helper().check_ip_range(DATA['dhcp_range_begin'], DATA['network']+'/'+DATA['subnet'])
                if not DHCPSTARTDETAILS:
                    response = {'message': f'Incorrect DHCP Start Range IP: {DATA["dhcp_range_begin"]}.'}
                    access_code = 400
                    return json.dumps(response), access_code
            else:
                response = {'message': f'DHCP Start Range is a Required Parameter.'}
                access_code = 400
                return json.dumps(response), access_code
            if 'dhcp_range_end' in DATA:
                DHCPENDDETAILS = Helper().check_ip_range(DATA['dhcp_range_end'], DATA['network']+'/'+DATA['subnet'])
                if not DHCPENDDETAILS:
                    response = {'message': f'Incorrect DHCP End Range IP: {DATA["dhcp_range_end"]}.'}
                    access_code = 400
                    return json.dumps(response), access_code
            else:
                response = {'message': f'DHCP End Range is a Required Parameter.'}
                access_code = 400
                return json.dumps(response), access_code
        else:
            DATA['dhcp'] = False
            DATA['dhcp_range_begin'] = ""
            DATA['dhcp_range_end'] = ""
        NETWORKCOLUMNS = Database().get_columns('network')
        COLUMNCHECK = Helper().checkin_list(DATA, NETWORKCOLUMNS)
        row = Helper().make_rows(DATA)
        if COLUMNCHECK:
            if CREATE:
                result = Database().insert('network', row)
                response = {'message': 'Network Created Successfully.'}
                access_code = 201
            if UPDATE:
                where = [{"column": "id", "value": NETWORKID}]
                result = Database().update('network', row, where)
                response = {'message': 'Network Updated Successfully.'}
                access_code = 204
        else:
            response = {'message': 'Bad Request; Columns are Incorrect.'}
            access_code = 400
            return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(DATA), access_code


@config_blueprint.route("/config/network/<string:name>/_clone", methods=['POST'])
# @token_required
def config_network_clone(name=None):
    """
    Input - Network Name
    Process - Create or Update Network information.
    Output - Success or Failure.
    """
    DATA = {}
    CREATE, UPDATE = False, False
    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['network'][name]
        DATA['name'] = name
        CHECKNETWORK = Database().get_record(None, 'network', f' WHERE `name` = "{name}";')
        if CHECKNETWORK:
            NETWORKID = CHECKNETWORK[0]['id']
            if 'newnetname' in REQUEST['config']['network'][name]:
                NEWNETWORKNAME = REQUEST['config']['network'][name]['newnetname']
                CHECKNEWNETWORK = Database().get_record(None, 'network', f' WHERE `name` = "{NEWNETWORKNAME}";')
                if CHECKNEWNETWORK:
                    response = {'message': f'{NEWNETWORKNAME} Already Present in Database, Choose Another Name Or Delete {NEWNETWORKNAME}.'}
                    access_code = 400
                    return json.dumps(response), access_code
                else:
                    DATA['name'] = DATA['newnetname']
                    del DATA['newnetname']
            CREATE = True
        else:
            response = {'message': f'Bad Request; Network {name} is Not Present in Database.'}
            access_code = 400
            return json.dumps(response), access_code
        if 'network' in DATA:
            NWKIP = Helper().check_ip(DATA['network'])
            if NWKIP:
                NWKDETAILS = Helper().get_network_details(DATA['network'])
                DATA['network'] = NWKIP
                DATA['subnet'] = NWKDETAILS['subnet']
            else:
                response = {'message': f'Incorrect Network IP: {DATA["network"]}.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'gateway' in DATA:
            GWDETAILS = Helper().check_ip_range(DATA['gateway'], DATA['network']+'/'+DATA['subnet'])
            if not GWDETAILS:
                response = {'message': f'Incorrect Gateway IP: {DATA["gateway"]}.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'ns_ip' in DATA:
            NSIPDETAILS = Helper().check_ip_range(DATA['ns_ip'], DATA['network']+'/'+DATA['subnet'])
            if not NSIPDETAILS:
                response = {'message': f'Incorrect NS IP: {DATA["ns_ip"]}.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'ntp_server' in DATA:
            NTPDETAILS = Helper().check_ip_range(DATA['ntp_server'], DATA['network']+'/'+DATA['subnet'])
            if not NTPDETAILS:
                response = {'message': f'Incorrect NTP Server IP: {DATA["ntp_server"]}.'}
                access_code = 400
                return json.dumps(response), access_code
        if 'dhcp' in DATA:
            if 'dhcp_range_begin' in DATA:
                DHCPSTARTDETAILS = Helper().check_ip_range(DATA['dhcp_range_begin'], DATA['network']+'/'+DATA['subnet'])
                if not DHCPSTARTDETAILS:
                    response = {'message': f'Incorrect DHCP Start Range IP: {DATA["dhcp_range_begin"]}.'}
                    access_code = 400
                    return json.dumps(response), access_code
            else:
                response = {'message': f'DHCP Start Range is a Required Parameter.'}
                access_code = 400
                return json.dumps(response), access_code
            if 'dhcp_range_end' in DATA:
                DHCPENDDETAILS = Helper().check_ip_range(DATA['dhcp_range_end'], DATA['network']+'/'+DATA['subnet'])
                if not DHCPENDDETAILS:
                    response = {'message': f'Incorrect DHCP End Range IP: {DATA["dhcp_range_end"]}.'}
                    access_code = 400
                    return json.dumps(response), access_code
            else:
                response = {'message': f'DHCP End Range is a Required Parameter.'}
                access_code = 400
                return json.dumps(response), access_code
        else:
            DATA['dhcp'] = False
            DATA['dhcp_range_begin'] = ""
            DATA['dhcp_range_end'] = ""
        NETWORKCOLUMNS = Database().get_columns('network')
        COLUMNCHECK = Helper().checkin_list(DATA, NETWORKCOLUMNS)
        row = Helper().make_rows(DATA)
        if COLUMNCHECK:
            if CREATE:
                result = Database().insert('network', row)
                response = {'message': 'Network Created Successfully.'}
                access_code = 201
        else:
            response = {'message': 'Bad Request; Columns are Incorrect.'}
            access_code = 400
            return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(DATA), access_code


@config_blueprint.route("/config/network/<string:name>/_delete", methods=['GET'])
@token_required
def config_network_delete(name=None):
    """
    Input - Network Name
    Process - Delete The Network.
    Output - Success or Failure.
    """
    CHECKNWK = Database().get_record(None, 'network', f' WHERE `name` = "{name}";')
    if CHECKNWK:
        Database().delete_row('network', [{"column": "name", "value": name}])
        response = {'message': 'Network Removed Successfully.'}
        access_code = 204
    else:
        response = {'message': f'Network {name} Not Present in Database.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/network/<string:name>/<string:ipaddr>", methods=['GET'])
@token_required
def config_network_ip(name=None, ipaddr=None):
    """
    Input - Network Name And IP Address
    Process - Delete The Network.
    Output - Success or Failure.
    """
    CHECKNWK = Database().get_record(None, 'network', f' WHERE `name` = "{name}";')
    if CHECKNWK:
        IPDETAILS = Helper().check_ip_range(ipaddr, CHECKNWK[0]['network']+'/'+CHECKNWK[0]['subnet'])
        if IPDETAILS:
            CHECKIP = Database().get_record(None, 'ipaddress', f' WHERE ipaddress = "{ipaddr}"; ')
            if CHECKIP:
                response = {'config': {'network': {ipaddr: {'status': 'taken'} } } }
                access_code = 200
            else:
                response = {'config': {'network': {ipaddr: {'status': 'free'} } } }
                access_code = 200
        else:
            response = {'message': f'{ipaddr} Is Not In The Range.'}
            access_code = 404
            return json.dumps(response), access_code
    else:
        response = {'message': f'Network {name} Not Present in Database.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/network/<string:name>/_nextfreeip", methods=['GET'])
@token_required
def config_network_nextip(name=None):
    """
    Input - Network Name
    Process - Find The Next Available IP on the Netwok.
    Output - Next Available IP on the Netwok.
    """
    response = {'config': {'network': {name: {'nextip': '10.141.0.2'} } } }
    if response:
        response = {'config': {'network': {name: {'nextip': '10.141.0.2'} } } }
        access_code = 200
    else:
        response = {'message': f'Network {name} Not Present in Database.'}
        access_code = 404
    return json.dumps(response), access_code


######################################################## Secrets configuration #############################################################


@config_blueprint.route("/config/secrets", methods=['GET'])
@token_required
def config_secrets_get():
    """
    Input - None
    Output - Return the List Of All Secrets.
    """
    NODESECRETS = Database().get_record(None, 'nodesecrets', None)
    GROUPSECRETS = Database().get_record(None, 'groupsecrets', None)
    if NODESECRETS or GROUPSECRETS:
        response = {'config': {'secrets': {} }}
        access_code = 200
    else:
        LOGGER.error('Secrets are not available.')
        response = {'message': 'Secrets are not available.'}
        access_code = 404
    if NODESECRETS:
        response['config']['secrets']['node'] = {}
        for NODE in NODESECRETS:
            NODENAME = Database().getname_byid('node', NODE['nodeid'])
            if NODENAME not in response['config']['secrets']['node']:
                response['config']['secrets']['node'][NODENAME] = []
            del NODE['nodeid']
            del NODE['id']
            NODE['content'] = Helper().decrypt_string(NODE['content'])
            response['config']['secrets']['node'][NODENAME].append(NODE)
    if GROUPSECRETS:
        response['config']['secrets']['group'] = {}
        for GROUP in GROUPSECRETS:
            GROUPNAME = Database().getname_byid('group', GROUP['groupid'])
            if GROUPNAME not in response['config']['secrets']['group']:
                response['config']['secrets']['group'][GROUPNAME] = []
            del GROUP['groupid']
            del GROUP['id']
            GROUP['content'] = Helper().decrypt_string(GROUP['content'])
            response['config']['secrets']['group'][GROUPNAME].append(GROUP)
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/node/<string:name>", methods=['GET'])
@token_required
def config_get_secrets_node(name=None):
    """
    Input - Node Name
    Output - Return the Node Secrets And Group Secrets for the Node.
    """
    NODE = Database().get_record(None, 'node', f' WHERE name = "{name}"')
    if NODE:
        NODEID  = NODE[0]['id']
        GROUPID  = NODE[0]['groupid']
        NODESECRETS = Database().get_record(None, 'nodesecrets', f' WHERE nodeid = "{NODEID}"')
        GROUPSECRETS = Database().get_record(None, 'groupsecrets', f' WHERE groupid = "{GROUPID}"')
        if NODESECRETS or GROUPSECRETS:
            response = {'config': {'secrets': {} }}
            access_code = 200
        else:
            LOGGER.error(f'Secrets are not available for Node {name}.')
            response = {'message': f'Secrets are not available for Node {name}.'}
            access_code = 404
        if NODESECRETS:
            response['config']['secrets']['node'] = {}
            for NODE in NODESECRETS:
                NODENAME = Database().getname_byid('node', NODE['nodeid'])
                if NODENAME not in response['config']['secrets']['node']:
                    response['config']['secrets']['node'][NODENAME] = []
                del NODE['nodeid']
                del NODE['id']
                NODE['content'] = Helper().decrypt_string(NODE['content'])
                response['config']['secrets']['node'][NODENAME].append(NODE)
        if GROUPSECRETS:
            response['config']['secrets']['group'] = {}
            for GROUP in GROUPSECRETS:
                GROUPNAME = Database().getname_byid('group', GROUP['groupid'])
                if GROUPNAME not in response['config']['secrets']['group']:
                    response['config']['secrets']['group'][GROUPNAME] = []
                del GROUP['groupid']
                del GROUP['id']
                GROUP['content'] = Helper().decrypt_string(GROUP['content'])
                response['config']['secrets']['group'][GROUPNAME].append(GROUP)
    else:
        LOGGER.error(f'Node {name} is not available.')
        response = {'message': f'Node {name} is not available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/node/<string:name>", methods=['POST'])
@token_required
def config_post_secrets_node(name=None):
    """
    Input - Node Name & Payload
    Process - Create Or Update Node Secrets.
    Output - None.
    """
    DATA,NODESECRETS = {}, []
    CREATE, UPDATE = False, False
    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['secrets']['node'][name]
        NODE = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if NODE:
            NODEID = NODE[0]['id']
            if DATA:
                for SECRET in DATA:
                    SECRETNAME = SECRET['name']
                    SECRETDATA = Database().get_record(None, 'nodesecrets', f' WHERE nodeid = "{NODEID}" AND name = "{SECRETNAME}";')
                    if SECRETDATA:
                        NODESECRETSCOLUMNS = Database().get_columns('nodesecrets')
                        COLUMNCHECK = Helper().checkin_list(SECRETDATA[0], NODESECRETSCOLUMNS)
                        if COLUMNCHECK:
                            SECRETID = SECRETDATA[0]['id']
                            SECRET['content'] = Helper().encrypt_string(SECRET['content'])
                            where = [{"column": "id", "value": SECRETID}, {"column": "nodeid", "value": NODEID}, {"column": "name", "value": SECRETNAME}]
                            row = Helper().make_rows(SECRET)
                            Database().update('nodesecrets', row, where)
                            UPDATE = True
                    else:
                        SECRET['nodeid'] = NODEID
                        SECRET['content'] = Helper().encrypt_string(SECRET['content'])
                        row = Helper().make_rows(SECRET)
                        Database().insert('nodesecrets', row)
                        CREATE = True
            else:
                LOGGER.error('Kindly provide at least one secret.')
                response = {'message': 'Kindly provide at least one secret.'}
                access_code = 404
        else:
            LOGGER.error(f'Node {name} is not available.')
            response = {'message': f'Node {name} is not available.'}
            access_code = 404

        if CREATE == True and UPDATE == True:
            response = {'message': f'Node {name} Secrets Created & Updated Successfully.'}
            access_code = 201
        elif CREATE == True and UPDATE == False:
            response = {'message': f'Node {name} Secret Created Successfully.'}
            access_code = 201
        elif CREATE == False and UPDATE == True:
            response = {'message': f'Node {name} Secret Updated Successfully.'}
            access_code = 201
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/node/<string:name>/<string:secret>", methods=['GET'])
@token_required
def config_get_node_secret(name=None, secret=None):
    """
    Input - Node Name & Secret Name
    Output - Return the Node Secret
    """
    NODE = Database().get_record(None, 'node', f' WHERE name = "{name}"')
    if NODE:
        NODEID  = NODE[0]['id']
        SECRET = Database().get_record(None, 'nodesecrets', f' WHERE nodeid = "{NODEID}" AND name = "{secret}"')
        if SECRET:
            response = {'config': {'secrets': {'node': {name: [] } } } }
            access_code = 200
            del SECRET[0]['nodeid']
            del SECRET[0]['id']
            SECRET[0]['content'] = Helper().decrypt_string(SECRET[0]['content'])
            response['config']['secrets']['node'][name] = SECRET
        else:
            LOGGER.error(f'Secret {secret} is unavailable for Node {name}.')
            response = {'message': f'Secret {secret} is unavailable for Node {name}.'}
            access_code = 404
    else:
        LOGGER.error(f'Node {name} is not available.')
        response = {'message': f'Node {name} is not available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/node/<string:name>/<string:secret>", methods=['POST'])
@token_required
def config_post_node_secret(name=None, secret=None):
    """
    Input - Node Name & Payload
    Process - Create Or Update Node Secrets.
    Output - None.
    """
    DATA = {}
    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['secrets']['node'][name]
        NODE = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if NODE:
            NODEID = NODE[0]['id']
            if DATA:
                SECRETNAME = DATA[0]['name']
                SECRETDATA = Database().get_record(None, 'nodesecrets', f' WHERE nodeid = "{NODEID}" AND name = "{SECRETNAME}";')
                if SECRETDATA:
                    NODESECRETSCOLUMNS = Database().get_columns('nodesecrets')
                    COLUMNCHECK = Helper().checkin_list(DATA[0], NODESECRETSCOLUMNS)
                    if COLUMNCHECK:
                        SECRETID = SECRETDATA[0]['id']
                        DATA[0]['content'] = Helper().encrypt_string(DATA[0]['content'])
                        where = [{"column": "id", "value": SECRETID}, {"column": "nodeid", "value": NODEID}, {"column": "name", "value": SECRETNAME}]
                        row = Helper().make_rows(DATA[0])
                        Database().update('nodesecrets', row, where)
                        response = {'message': f'Node {name} Secret {secret} Updated Successfully.'}
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
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/node/<string:name>/<string:secret>/_clone", methods=['POST'])
@token_required
def config_clone_node_secret(name=None, secret=None):
    """
    Input - Node Name & Payload
    Process - Create Or Update Node Secrets.
    Output - None.
    """
    DATA = {}
    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['secrets']['node'][name]
        NODE = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if NODE:
            NODEID = NODE[0]['id']
            if DATA:
                SECRETNAME = DATA[0]['name']
                SECRETDATA = Database().get_record(None, 'nodesecrets', f' WHERE nodeid = "{NODEID}" AND name = "{SECRETNAME}";')
                if SECRETDATA:
                    if 'newsecretname' in DATA[0]:
                        NEWSECRETNAME = DATA[0]['newsecretname']
                        del DATA[0]['newsecretname']
                        DATA[0]['nodeid'] = NODEID
                        DATA[0]['name'] = NEWSECRETNAME
                        NEWSECRETDATA = Database().get_record(None, 'nodesecrets', f' WHERE nodeid = "{NODEID}" AND name = "{NEWSECRETNAME}";')
                        if NEWSECRETDATA:
                            LOGGER.error(f'Secret {NEWSECRETNAME} Already Present..')
                            response = {'message': f'Secret {NEWSECRETNAME} Already Present..'}
                            access_code = 404
                        else:
                            NODESECRETSCOLUMNS = Database().get_columns('nodesecrets')
                            COLUMNCHECK = Helper().checkin_list(DATA[0], NODESECRETSCOLUMNS)
                            if COLUMNCHECK:
                                SECRETID = SECRETDATA[0]['id']
                                DATA[0]['content'] = Helper().encrypt_string(DATA[0]['content'])
                                row = Helper().make_rows(DATA[0])
                                Database().insert('nodesecrets', row)
                                response = {'message': f'Node {name} Secret {secret} Clone Successfully to {NEWSECRETNAME}.'}
                                access_code = 204
                    else:
                        LOGGER.error('Kindly Pass the New Secret Name.')
                        response = {'message': 'Kindly Pass the New Secret Name.'}
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
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/node/<string:name>/<string:secret>/_delete", methods=['GET'])
@token_required
def config_node_secret_delete(name=None, secret=None):
    """
    Input - Node Name & Secret Name
    Output - Success or Failure
    """
    NODE = Database().get_record(None, 'node', f' WHERE name = "{name}"')
    if NODE:
        NODEID  = NODE[0]['id']
        SECRET = Database().get_record(None, 'nodesecrets', f' WHERE nodeid = "{NODEID}" AND name = "{secret}"')
        if SECRET:
            Database().delete_row('nodesecrets', [{"column": "nodeid", "value": NODEID}, {"column": "name", "value": secret}])
            response = {'message': f'Secret {secret} Deleted From Node {name}.'}
            access_code = 204
        else:
            LOGGER.error(f'Secret {secret} is unavailable for Node {name}.')
            response = {'message': f'Secret {secret} is unavailable for Node {name}.'}
            access_code = 404
    else:
        LOGGER.error(f'Node {name} is not available.')
        response = {'message': f'Node {name} is not available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/group/<string:name>", methods=['GET'])
@token_required
def config_get_secrets_group(name=None):
    """
    Input - Group Name
    Output - Return the Group Secrets.
    """
    GROUP = Database().get_record(None, 'group', f' WHERE name = "{name}"')
    if GROUP:
        GROUPID  = GROUP[0]['id']
        GROUPSECRETS = Database().get_record(None, 'groupsecrets', f' WHERE groupid = "{GROUPID}"')
        if GROUPSECRETS:
            response = {'config': {'secrets': {'group': {name: [] } } } }
            for GRP in GROUPSECRETS:
                del GRP['groupid']
                del GRP['id']
                GRP['content'] = Helper().decrypt_string(GRP['content'])
                response['config']['secrets']['group'][name].append(GRP)
                access_code = 200
        else:
            LOGGER.error(f'Secrets are not available for Group {name}.')
            response = {'message': f'Secrets are not available for Group {name}.'}
            access_code = 404
    else:
        LOGGER.error(f'Group {name} is not available.')
        response = {'message': f'Group {name} is not available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/group/<string:name>", methods=['POST'])
@token_required
def config_post_secrets_group(name=None):
    """
    Input - Group Name & Payload
    Process - Create Or Update Group Secrets.
    Output - None.
    """
    DATA = {}
    CREATE, UPDATE = False, False
    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['secrets']['group'][name]
        GROUP = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if GROUP:
            GROUPID = GROUP[0]['id']
            if DATA:
                for SECRET in DATA:
                    SECRETNAME = SECRET['name']
                    SECRETDATA = Database().get_record(None, 'groupsecrets', f' WHERE groupid = "{GROUPID}" AND name = "{SECRETNAME}";')
                    if SECRETDATA:
                        GRPSECRETSCOLUMNS = Database().get_columns('groupsecrets')
                        COLUMNCHECK = Helper().checkin_list(SECRETDATA[0], GRPSECRETSCOLUMNS)
                        if COLUMNCHECK:
                            SECRETID = SECRETDATA[0]['id']
                            SECRET['content'] = Helper().encrypt_string(SECRET['content'])
                            where = [{"column": "id", "value": SECRETID}, {"column": "groupid", "value": GROUPID}, {"column": "name", "value": SECRETNAME}]
                            row = Helper().make_rows(SECRET)
                            Database().update('groupsecrets', row, where)
                            UPDATE = True
                    else:
                        SECRET['groupid'] = GROUPID
                        SECRET['content'] = Helper().encrypt_string(SECRET['content'])
                        row = Helper().make_rows(SECRET)
                        Database().insert('groupsecrets', row)
                        CREATE = True
            else:
                LOGGER.error('Kindly provide at least one secret.')
                response = {'message': 'Kindly provide at least one secret.'}
                access_code = 404
        else:
            LOGGER.error(f'Group {name} is not available.')
            response = {'message': f'Group {name} is not available.'}
            access_code = 404

        if CREATE == True and UPDATE == True:
            response = {'message': f'Group {name} Secrets Created & Updated Successfully.'}
            access_code = 204
        elif CREATE == True and UPDATE == False:
            response = {'message': f'Group {name} Secret Created Successfully.'}
            access_code = 201
        elif CREATE == False and UPDATE == True:
            response = {'message': f'Group {name} Secret Updated Successfully.'}
            access_code = 204
    else:
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/group/<string:name>/<string:secret>", methods=['GET'])
@token_required
def config_get_group_secret(name=None, secret=None):
    """
    Input - Group Name & Secret Name
    Output - Return the Group Secret
    """
    GROUP = Database().get_record(None, 'group', f' WHERE name = "{name}"')
    if GROUP:
        GROUPID  = GROUP[0]['id']
        SECRET = Database().get_record(None, 'groupsecrets', f' WHERE groupid = "{GROUPID}" AND name = "{secret}"')
        if SECRET:
            response = {'config': {'secrets': {'group': {name: [] } } } }
            access_code = 200
            del SECRET[0]['groupid']
            del SECRET[0]['id']
            SECRET[0]['content'] = Helper().decrypt_string(SECRET[0]['content'])
            response['config']['secrets']['group'][name] = SECRET
        else:
            LOGGER.error(f'Secret {secret} is unavailable for Group {name}.')
            response = {'message': f'Secret {secret} is unavailable for Group {name}.'}
            access_code = 404
    else:
        LOGGER.error(f'Group {name} is not available.')
        response = {'message': f'Group {name} is not available.'}
        access_code = 404
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/group/<string:name>/<string:secret>", methods=['POST'])
@token_required
def config_post_group_secret(name=None, secret=None):
    """
    Input - Group Name & Payload
    Process - Create Or Update Group Secrets.
    Output - None.
    """
    DATA = {}
    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['secrets']['group'][name]
        GROUP = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if GROUP:
            GROUPID = GROUP[0]['id']
            if DATA:
                SECRETNAME = DATA[0]['name']
                SECRETDATA = Database().get_record(None, 'groupsecrets', f' WHERE groupid = "{GROUPID}" AND name = "{SECRETNAME}";')
                if SECRETDATA:
                    GRPSECRETSCOLUMNS = Database().get_columns('groupsecrets')
                    COLUMNCHECK = Helper().checkin_list(DATA[0], GRPSECRETSCOLUMNS)
                    if COLUMNCHECK:
                        SECRETID = SECRETDATA[0]['id']
                        DATA[0]['content'] = Helper().encrypt_string(DATA[0]['content'])
                        where = [{"column": "id", "value": SECRETID}, {"column": "groupid", "value": GROUPID}, {"column": "name", "value": SECRETNAME}]
                        row = Helper().make_rows(DATA[0])
                        Database().update('groupsecrets', row, where)
                        response = {'message': f'Group {name} Secret {secret} Updated Successfully.'}
                        access_code = 204
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
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route("/config/secrets/group/<string:name>/<string:secret>/_clone", methods=['POST'])
@token_required
def config_clone_group_secret(name=None, secret=None):
    """
    Input - Group Name & Payload
    Process - Clone Group Secrets.
    Output - None.
    """
    DATA = {}
    if Helper().check_json(request.data):
        REQUEST = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if REQUEST:
        DATA = REQUEST['config']['secrets']['group'][name]
        GROUP = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if GROUP:
            GROUPID = GROUP[0]['id']
            if DATA:
                SECRETNAME = DATA[0]['name']
                SECRETDATA = Database().get_record(None, 'groupsecrets', f' WHERE groupid = "{GROUPID}" AND name = "{SECRETNAME}";')
                if SECRETDATA:
                    if 'newsecretname' in DATA[0]:
                        NEWSECRETNAME = DATA[0]['newsecretname']
                        del DATA[0]['newsecretname']
                        DATA[0]['groupid'] = GROUPID
                        DATA[0]['name'] = NEWSECRETNAME
                        NEWSECRETDATA = Database().get_record(None, 'groupsecrets', f' WHERE groupid = "{GROUPID}" AND name = "{NEWSECRETNAME}";')
                        if NEWSECRETDATA:
                            LOGGER.error(f'Secret {NEWSECRETNAME} Already Present..')
                            response = {'message': f'Secret {NEWSECRETNAME} Already Present..'}
                            access_code = 404
                        else:
                            GRPSECRETSCOLUMNS = Database().get_columns('groupsecrets')
                            COLUMNCHECK = Helper().checkin_list(DATA[0], GRPSECRETSCOLUMNS)
                            if COLUMNCHECK:
                                SECRETID = SECRETDATA[0]['id']
                                DATA[0]['content'] = Helper().encrypt_string(DATA[0]['content'])
                                row = Helper().make_rows(DATA[0])
                                Database().insert('groupsecrets', row)
                                response = {'message': f'Group {name} Secret {secret} Clone Successfully to {NEWSECRETNAME}.'}
                                access_code = 204
                    else:
                        LOGGER.error('Kindly Pass the New Secret Name.')
                        response = {'message': 'Kindly Pass the New Secret Name.'}
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
        response = {'message': 'Bad Request; Did not received Data.'}
        access_code = 400
    return json.dumps(response), access_code


@config_blueprint.route('/config/secrets/group/<string:name>/<string:secret>/_delete', methods=['GET'])
@token_required
def config_group_secret_delete(name=None, secret=None):
    """
    Input - Group Name & Secret Name
    Output - Success or Failure
    """
    group = Database().get_record(None, 'group', f' WHERE name = "{name}"')
    if group:
        groupid  = group[0]['id']
        db_secret = Database().get_record(None, 'groupsecrets', f' WHERE groupid = "{groupid}" AND name = "{secret}"')
        if db_secret:
            Database().delete_row('groupsecrets', [{"column": "groupid", "value": groupid}, {"column": "name", "value": secret}])
            response = {'message': f'Secret {secret} Deleted From Group {name}.'}
            access_code = 204
        else:
            LOGGER.error(f'Secret {secret} is unavailable for Group {name}.')
            response = {'message': f'Secret {secret} is unavailable for Group {name}.'}
            access_code = 404
    else:
        LOGGER.error(f'Group {name} is not available.')
        response = {'message': f'Group {name} is not available.'}
        access_code = 404
    return json.dumps(response), access_code
