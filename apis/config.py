#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File is a A Entry Point of Every Configuration Related Activity.
@token_required is a Wrapper Method to Validate the POST API. It contains arguments and keyword arguments Of The API
@validate_access is a Wrapper to Validate the access for the GET API.
    It contains arguments and keyword arguments Of The API
    After validate the Token, Return the arguments and keyword arguments Of The API Along access key with admin value to use further.

"""

from common.validate_auth import *
from flask import Blueprint, request, json
from utils.log import *
from utils.helper import Helper
from common.constant import ConfigFile

logger = Log.get_logger()

config_blueprint = Blueprint('config', __name__)


######################################################## Node Configuration #############################################################


@config_blueprint.route("/config/node", methods=['GET'])
@token_required
def config_node():
    """
    Input - None
    Output - Return the List Of Nodes.
    """
    NODES = Database().get_record(None, 'node', None)
    if NODES:
        RESPONSE = {'config': {'node': {} }}
        for NODE in NODES:
            NODENAME = NODE['name']
            NODEID = NODE['id']
            if NODE['bmcsetupid']:
                NODE['bmcsetup'] = Database().getname_byid('bmcsetup', NODE['bmcsetupid'])
            if NODE['groupid']:
                NODE['group'] = Database().getname_byid('group', NODE['groupid'])
            if NODE['osimageid']:
                NODE['osimage'] = Database().getname_byid('osimage', NODE['osimageid'])
            if NODE['switchid']:
                NODE['switch'] = Database().getname_byid('switch', NODE['switchid'])
            del NODE['name']
            del NODE['id']
            del NODE['bmcsetupid']
            del NODE['groupid']
            del NODE['osimageid']
            del NODE['switchid']
            NODE['bootmenu'] = Helper().bool_revert(NODE['bootmenu'])
            NODE['localboot'] = Helper().bool_revert(NODE['localboot'])
            NODE['localinstall'] = Helper().bool_revert(NODE['localinstall'])
            NODE['netboot'] = Helper().bool_revert(NODE['netboot'])
            NODE['service'] = Helper().bool_revert(NODE['service'])
            NODE['setupbmc'] = Helper().bool_revert(NODE['setupbmc'])
            NODEINTERFACE = Database().get_record(None, 'nodeinterface', f' WHERE nodeid = "{NODEID}"')
            if NODEINTERFACE:
                NODE['interfaces'] = []
                for INTERFACE in NODEINTERFACE:
                    INTERFACE['network'] = Database().getname_byid('network', INTERFACE['networkid'])
                    del INTERFACE['nodeid']
                    del INTERFACE['id']
                    del INTERFACE['networkid']
                    NODE['interfaces'].append(INTERFACE)
            RESPONSE['config']['node'][NODENAME] = NODE
        logger.info('Provided List Of All Nodes.')
        ACCESSCODE = 200
    else:
        logger.error('No Node is Avaiable.')
        RESPONSE = {'message': 'No Node is Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


@config_blueprint.route("/config/node/<string:name>", methods=['GET'])
@token_required
def config_node_get(name=None):
    """
    Input - None
    Output - Return the Node Information.
    """
    NODE = Database().get_record(None, 'node', f' WHERE name = "{name}"')
    if NODE:
        RESPONSE = {'config': {'node': {} }}
        NODE = NODE[0]
        NODENAME = NODE['name']
        NODEID = NODE['id']
        if NODE['bmcsetupid']:
            NODE['bmcsetup'] = Database().getname_byid('bmcsetup', NODE['bmcsetupid'])
        if NODE['groupid']:
            NODE['group'] = Database().getname_byid('group', NODE['groupid'])
        if NODE['osimageid']:
            NODE['osimage'] = Database().getname_byid('osimage', NODE['osimageid'])
        if NODE['switchid']:
            NODE['switch'] = Database().getname_byid('switch', NODE['switchid'])
        del NODE['name']
        del NODE['id']
        del NODE['bmcsetupid']
        del NODE['groupid']
        del NODE['osimageid']
        del NODE['switchid']
        NODE['bootmenu'] = Helper().bool_revert(NODE['bootmenu'])
        NODE['localboot'] = Helper().bool_revert(NODE['localboot'])
        NODE['localinstall'] = Helper().bool_revert(NODE['localinstall'])
        NODE['netboot'] = Helper().bool_revert(NODE['netboot'])
        NODE['service'] = Helper().bool_revert(NODE['service'])
        NODE['setupbmc'] = Helper().bool_revert(NODE['setupbmc'])
        NODEINTERFACE = Database().get_record(None, 'nodeinterface', f' WHERE nodeid = "{NODEID}"')
        if NODEINTERFACE:
            NODE['interfaces'] = []
            for INTERFACE in NODEINTERFACE:
                INTERFACE['network'] = Database().getname_byid('network', INTERFACE['networkid'])
                del INTERFACE['nodeid']
                del INTERFACE['id']
                del INTERFACE['networkid']
                NODE['interfaces'].append(INTERFACE)
        RESPONSE['config']['node'][NODENAME] = NODE
        logger.info('Provided List Of All Nodes.')
        ACCESSCODE = 200
    else:
        logger.error(f'Node {name} is not Avaiable.')
        RESPONSE = {'message': f'Node {name} is not Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


@config_blueprint.route("/config/node/<string:name>", methods=['POST'])
@token_required
def config_node_post(name=None):
    """
    Input - Node Name
    Process - Create Or Update The Groups.
    Output - Node Information.
    """
    DATA = {}
    CREATE, UPDATE = False, False

    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
    if REQUEST:
        DATA = REQUEST['config']['node'][name]
        NODE = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if NODE:
            NODEID = NODE[0]['id']
            if 'newnodename' in DATA:
                NEWNODENAME = DATA['newnodename']
                CHECKNEWNODE = Database().get_record(None, 'node', f' WHERE `name` = "{NEWNODENAME}";')
                if CHECKNEWNODE:
                    RESPONSE = {'message': f'{NEWNODENAME} Already Present in Database, Choose Another Name Or Delete {NEWNODENAME}.'}
                    ACCESSCODE = 400
                    return json.dumps(RESPONSE), ACCESSCODE
                else:
                    DATA['name'] = DATA['newnodename']
                    del DATA['newnodename']
            UPDATE = True
            if 'bootmenu' in DATA:
                DATA['bootmenu'] = Helper().bool_revert(DATA['bootmenu'])
            if 'localboot' in DATA:
                DATA['localboot'] = Helper().bool_revert(DATA['localboot'])
            if 'localinstall' in DATA:
                DATA['localinstall'] = Helper().bool_revert(DATA['localinstall'])
            if 'netboot' in DATA:
                DATA['netboot'] = Helper().bool_revert(DATA['netboot'])
            if 'service' in DATA:
                DATA['service'] = Helper().bool_revert(DATA['service'])
            if 'setupbmc' in DATA:
                DATA['setupbmc'] = Helper().bool_revert(DATA['setupbmc'])
        else:
            if 'newnodename' in DATA:
                RESPONSE = {'message': f'{NEWNODENAME} is not allwoed while creating a new node.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
            if 'bootmenu' in DATA:
                DATA['bootmenu'] = Helper().bool_revert(DATA['bootmenu'])
            else:
                DATA['bootmenu'] = 0
            if 'localboot' in DATA:
                DATA['localboot'] = Helper().bool_revert(DATA['localboot'])
            else:
                DATA['localboot'] = 0
            if 'localinstall' in DATA:
                DATA['localinstall'] = Helper().bool_revert(DATA['localinstall'])
            else:
                DATA['localinstall'] = 0
            if 'netboot' in DATA:
                DATA['netboot'] = Helper().bool_revert(DATA['netboot'])
            else:
                DATA['netboot'] = 0
            if 'service' in DATA:
                DATA['service'] = Helper().bool_revert(DATA['service'])
            else:
                DATA['service'] = 0
            if 'setupbmc' in DATA:
                DATA['setupbmc'] = Helper().bool_revert(DATA['setupbmc'])
            else:
                DATA['setupbmc'] = 0
            CREATE = True

        if 'bmcsetup' in DATA:
            BMCNAME = DATA['bmcsetup']
            del DATA['bmcsetup']
            DATA['bmcsetupid'] = Database().getid_byname('bmcsetup', BMCNAME)
        if 'group' in DATA:
            GRPNAME = DATA['group']
            del DATA['group']
            DATA['groupid'] = Database().getid_byname('group', GRPNAME)
        if 'osimage' in DATA:
            OSNAME = DATA['osimage']
            del DATA['osimage']
            DATA['osimageid'] = Database().getid_byname('osimage', OSNAME)
        if 'switch' in DATA:
            SWITCHNAME = DATA['switch']
            del DATA['switch']
            DATA['switchid'] = Database().getid_byname('switch', SWITCHNAME)

        if 'interfaces' in DATA:
            NEWINTERFACE = DATA['interfaces']
            del DATA['interfaces']
        
        NODECOLUMNS = Database().get_columns('node')
        COLUMNCHECK = Helper().checkin_list(DATA, NODECOLUMNS)
        if COLUMNCHECK:
            if UPDATE:
                where = [{"column": "id", "value": NODEID}]
                row = Helper().make_rows(DATA)
                UPDATEID = Database().update('node', row, where)
                RESPONSE = {'message': f'Node {name} Updated Successfully.'}
                ACCESSCODE = 204
            if CREATE:
                DATA['name'] = name
                row = Helper().make_rows(DATA)
                NODEID = Database().insert('node', row)
                RESPONSE = {'message': f'Node {name} Created Successfully.'}
                ACCESSCODE = 201
            if NEWINTERFACE:
                for INTERFACE in NEWINTERFACE:
                    NWK = Database().getid_byname('network', INTERFACE['network'])
                    if NWK == None:
                        RESPONSE = {'message': f'Bad Request; Network {NWK} Not Exist.'}
                        ACCESSCODE = 400
                        return json.dumps(RESPONSE), ACCESSCODE
                    else:
                        INTERFACE['networkid'] = NWK
                        INTERFACE['nodeid'] = NODEID
                        del INTERFACE['network']
                    IFNAME = INTERFACE['interface']
                    where = f' WHERE nodeid = "{NODEID}" AND networkid = "{NWK}" AND interface = "{IFNAME}"'
                    CHECKINTERFACE = Database().get_record(None, 'nodeinterface', where)
                    if not CHECKINTERFACE:
                        row = Helper().make_rows(INTERFACE)
                        result = Database().insert('nodeinterface', row)
                        logger.info("Interface Created => {} .".format(result))

        else:
            RESPONSE = {'message': 'Bad Request; Columns are Incorrect.'}
            ACCESSCODE = 400
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
    return json.dumps(RESPONSE), ACCESSCODE


@config_blueprint.route("/config/node/<string:name>/_delete", methods=['GET'])
@token_required
def config_node_delete(name=None):
    """
    Input - Node Name
    Process - Delete the Node and it's interfaces.
    Output - Success or Failure.
    """
    NODE = Database().get_record(None, 'node', f' WHERE `name` = "{name}";')
    if NODE:
        Database().delete_row('node', [{"column": "name", "value": name}])
        Database().delete_row('nodeinterface', [{"column": "nodeid", "value": NODE[0]['id']}])
        Database().delete_row('nodesecrets', [{"column": "nodeid", "value": NODE[0]['id']}])
        RESPONSE = {'message': f'Node {name} with all its interfaces Removed Successfully.'}
        ACCESSCODE = 204
    else:
        RESPONSE = {'message': f'Node {name} Not Present in Database.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


@config_blueprint.route("/config/node/<string:name>/interfaces", methods=['GET'])
@token_required
def config_node_get_interfaces(name=None):
    """
    Input - Node Name
    Process - Fetch the Node Interface List.
    Output - Node Interface List.
    """
    NODE = Database().get_record(None, 'node', f' WHERE name = "{name}"')
    if NODE:
        RESPONSE = {'config': {'node': {name: {'interfaces': [] } } } }
        NODEID = NODE[0]['id']
        NODEINTERFACE = Database().get_record(None, 'nodeinterface', f' WHERE nodeid = "{NODEID}"')
        if NODEINTERFACE:
            NODEIFC = []
            for INTERFACE in NODEINTERFACE:
                INTERFACE['network'] = Database().getname_byid('network', INTERFACE['networkid'])
                del INTERFACE['nodeid']
                del INTERFACE['id']
                del INTERFACE['networkid']
                NODEIFC.append(INTERFACE)
            RESPONSE['config']['node'][name]['interfaces'] = NODEIFC
            logger.info(f'Returned Group {name} with Details.')
            ACCESSCODE = 200
        else:
            logger.error(f'Node {name} dont have any Interface.')
            RESPONSE = {'message': f'Node {name} dont have any Interface.'}
            ACCESSCODE = 404
    else:
        logger.error('No Node is Avaiable.')
        RESPONSE = {'message': 'No Node is Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


@config_blueprint.route("/config/node/<string:name>/interfaces", methods=['POST'])
@token_required
def config_node_post_interfaces(name=None):
    """
    Input - Node Name
    Process - Create Or Update The Node Interface.
    Output - Node Interface.
    """
    DATA = {}
    CREATE, UPDATE = False, False

    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
    if REQUEST:
        NODE = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if NODE:
            NODEID = NODE[0]['id']
            if 'interfaces' in REQUEST['config']['node'][name]:
                for INTERFACE in REQUEST['config']['node'][name]['interfaces']:
                    NWK = Database().getid_byname('network', INTERFACE['network'])
                    if NWK == None:
                        RESPONSE = {'message': f'Bad Request; Network {NWK} Not Exist.'}
                        ACCESSCODE = 400
                        return json.dumps(RESPONSE), ACCESSCODE
                    else:
                        INTERFACE['networkid'] = NWK
                        INTERFACE['nodeid'] = NODEID
                        del INTERFACE['network']
                    IFNAME = INTERFACE['interface']
                    where = f' WHERE nodeid = "{NODEID}" AND networkid = "{NWK}" AND interface = "{IFNAME}"'
                    CHECKINTERFACE = Database().get_record(None, 'nodeinterface', where)
                    if not CHECKINTERFACE:
                        row = Helper().make_rows(INTERFACE)
                        result = Database().insert('nodeinterface', row)
                    RESPONSE = {'message': 'Interface Updated.'}
                    ACCESSCODE = 204
            else:
                logger.error('Kindly Provide the interface.')
                RESPONSE = {'message': 'Kindly Provide the interface.'}
                ACCESSCODE = 404
        else:
            logger.error(f'Node {name} is Not Avaiable.')
            RESPONSE = {'message': f'Node {name} is Not Avaiable.'}
            ACCESSCODE = 404
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
    return json.dumps(RESPONSE), ACCESSCODE


@config_blueprint.route("/config/node/<string:name>/interfaces/<string:interface>", methods=['GET'])
@token_required
def config_node_interface_get(name=None, interface=None):
    """
    Input - Node Name & Interface Name
    Process - Get the Node Interface.
    Output - Success or Failure.
    """
    NODE = Database().get_record(None, 'node', f' WHERE name = "{name}"')
    if NODE:
        RESPONSE = {'config': {'node': {name: {'interfaces': [] } } } }
        NODEID = NODE[0]['id']
        NODEINTERFACE = Database().get_record(None, 'nodeinterface', f' WHERE nodeid = "{NODEID}" AND interface = "{interface}"')
        if NODEINTERFACE:
            NODEIFC = []
            for INTERFACE in NODEINTERFACE:
                INTERFACE['network'] = Database().getname_byid('network', INTERFACE['networkid'])
                del INTERFACE['nodeid']
                del INTERFACE['id']
                del INTERFACE['networkid']
                NODEIFC.append(INTERFACE)
            RESPONSE['config']['node'][name]['interfaces'] = NODEIFC
            logger.info(f'Returned Group {name} with Details.')
            ACCESSCODE = 200
        else:
            logger.error(f'Node {name} dont have {interface} Interface.')
            RESPONSE = {'message': f'Node {name} dont have {interface} Interface.'}
            ACCESSCODE = 404
    else:
        logger.error('No Node is Avaiable.')
        RESPONSE = {'message': 'No Node is Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE



@config_blueprint.route("/config/node/<string:name>/interfaces/<string:interface>/_delete", methods=['GET'])
@token_required
def config_node_delete_interface(name=None, interface=None):
    """
    Input - Node Name & Interface Name
    Process - Delete the Node Interface.
    Output - Success or Failure.
    """
    NODE = Database().get_record(None, 'node', f' WHERE `name` = "{name}";')
    if NODE:
        NODEID = NODE[0]['id']
        NODEINTERFACE = Database().get_record(None, 'nodeinterface', f' WHERE `interface` = "{interface}" AND `nodeid` = "{NODEID}";')
        if NODEINTERFACE:
            Database().delete_row('nodeinterface', [{"column": "id", "value": NODEINTERFACE[0]['id']}])
            RESPONSE = {'message': f'Node {name} interface {interface} Removed Successfully.'}
            ACCESSCODE = 204
        else:
            RESPONSE = {'message': f'Node {name} interface {interface} Not Present in Database.'}
            ACCESSCODE = 404
    else:
        RESPONSE = {'message': f'Node {name} Not Present in Database.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE

######################################################## Group Configuration #############################################################

@config_blueprint.route("/config/group", methods=['GET'])
@token_required
def config_group():
    """
    Input - Group Name
    Process - Fetch the Group information.
    Output - Group Info.
    """
    GROUPS = Database().get_record(None, 'group', None)
    if GROUPS:
        RESPONSE = {'config': {'group': {} }}
        for GRP in GROUPS:
            GRPNAME = GRP['name']
            GRPID = GRP['id']
            GRPINTERFACE = Database().get_record(None, 'groupinterface', f' WHERE groupid = "{GRPID}"')
            if GRPINTERFACE:
                GRP['interfaces'] = []
                for INTERFACE in GRPINTERFACE:
                    INTERFACE['network'] = Database().getname_byid('network', INTERFACE['networkid'])
                    del INTERFACE['groupid']
                    del INTERFACE['id']
                    del INTERFACE['networkid']
                    GRP['interfaces'].append(INTERFACE)
            del GRP['id']
            del GRP['name']
            GRP['bmcsetup'] = Helper().bool_revert(GRP['bmcsetup'])
            GRP['netboot'] = Helper().bool_revert(GRP['netboot'])
            GRP['localinstall'] = Helper().bool_revert(GRP['localinstall'])
            GRP['bootmenu'] = Helper().bool_revert(GRP['bootmenu'])
            GRP['osimage'] = Database().getname_byid('osimage', GRP['osimageid'])
            del GRP['osimageid']
            if GRP['bmcsetupid']:
                GRP['bmcsetupname'] = Database().getname_byid('bmcsetup', GRP['bmcsetupid'])
            del GRP['bmcsetupid']
            RESPONSE['config']['group'][GRPNAME] = GRP
        logger.info('Provided List Of All Groups with Details.')
        ACCESSCODE = 200
    else:
        logger.error('No Group is Avaiable.')
        RESPONSE = {'message': 'No Group is Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


@config_blueprint.route("/config/group/<string:name>", methods=['GET'])
@token_required
def config_group_get(name=None):
    """
    Input - Group Name
    Process - Fetch the Group information.
    Output - Group Info.
    """
    GROUPS = Database().get_record(None, 'group', f' WHERE name = "{name}"')
    if GROUPS:
        RESPONSE = {'config': {'group': {} }}
        for GRP in GROUPS:
            GRPNAME = GRP['name']
            GRPID = GRP['id']
            GRPINTERFACE = Database().get_record(None, 'groupinterface', f' WHERE groupid = "{GRPID}"')
            if GRPINTERFACE:
                GRP['interfaces'] = []
                for INTERFACE in GRPINTERFACE:
                    INTERFACE['network'] = Database().getname_byid('network', INTERFACE['networkid'])
                    del INTERFACE['groupid']
                    del INTERFACE['id']
                    del INTERFACE['networkid']
                    GRP['interfaces'].append(INTERFACE)
            del GRP['id']
            del GRP['name']
            GRP['bmcsetup'] = Helper().bool_revert(GRP['bmcsetup'])
            GRP['netboot'] = Helper().bool_revert(GRP['netboot'])
            GRP['localinstall'] = Helper().bool_revert(GRP['localinstall'])
            GRP['bootmenu'] = Helper().bool_revert(GRP['bootmenu'])
            GRP['osimage'] = Database().getname_byid('osimage', GRP['osimageid'])
            del GRP['osimageid']
            if GRP['bmcsetupid']:
                GRP['bmcsetupname'] = Database().getname_byid('bmcsetup', GRP['bmcsetupid'])
            del GRP['bmcsetupid']
            RESPONSE['config']['group'][GRPNAME] = GRP
        logger.info(f'Returned Group {name} with Details.')
        ACCESSCODE = 200
    else:
        logger.error('No Group is Avaiable.')
        RESPONSE = {'message': 'No Group is Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


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

    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
    if REQUEST:
        DATA = REQUEST['config']['group'][name]
        GRP = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if GRP:
            GRPID = GRP[0]['id']
            if 'newgroupname' in DATA:
                NEWGRPNAME = DATA['newgroupname']
                CHECKNEWGRP = Database().get_record(None, 'group', f' WHERE `name` = "{NEWGRPNAME}";')
                if CHECKNEWGRP:
                    RESPONSE = {'message': f'{NEWGRPNAME} Already Present in Database, Choose Another Name Or Delete {NEWGRPNAME}.'}
                    ACCESSCODE = 400
                    return json.dumps(RESPONSE), ACCESSCODE
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
                RESPONSE = {'message': f'{NEWGRPNAME} is not allwoed while creating a new group.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
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
                RESPONSE = {'message': f'BMC Setup {BMCNAME} does not exist, Choose Another BMC Setup.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
        if 'osimage' in DATA:
            OSNAME = DATA['osimage']
            del DATA['osimage']
            DATA['osimageid'] = Database().getid_byname('osimage', OSNAME)
        if not DATA['bmcsetupid']:
            RESPONSE = {'message': f'BMC Setup {OSNAME} does not exist, Choose Another BMC Setup.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE
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
                RESPONSE = {'message': f'Group {name} Updated Successfully.'}
                ACCESSCODE = 204
            if CREATE:
                DATA['name'] = name
                row = Helper().make_rows(DATA)
                GRPID = Database().insert('group', row)
                RESPONSE = {'message': f'Group {name} Created Successfully.'}
                ACCESSCODE = 201
            if NEWINTERFACE:
                for INTERFACE in NEWINTERFACE:
                    NWK = Database().getid_byname('network', INTERFACE['network'])
                    if NWK == None:
                        RESPONSE = {'message': f'Bad Request; Network {NWK} Not Exist.'}
                        ACCESSCODE = 400
                        return json.dumps(RESPONSE), ACCESSCODE
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
                        logger.info("Interface Created => {} .".format(result))

        else:
            RESPONSE = {'message': 'Bad Request; Columns are Incorrect.'}
            ACCESSCODE = 400
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
    return json.dumps(RESPONSE), ACCESSCODE


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
        RESPONSE = {'message': f'Group {name} with all its interfaces Removed Successfully.'}
        ACCESSCODE = 204
    else:
        RESPONSE = {'message': f'Group {name} Not Present in Database.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


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
        RESPONSE = {'config': {'group': {name: {'interfaces': [] } } } }
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
                RESPONSE['config']['group'][GRPNAME]['interfaces'] = GRPIFC
            else:
                logger.error(f'No Group {name} dont have any Interface.')
                RESPONSE = {'message': f'No Group {name} dont have any Interface.'}
                ACCESSCODE = 404
        logger.info(f'Returned Group {name} with Details.')
        ACCESSCODE = 200
    else:
        logger.error('No Group is Avaiable.')
        RESPONSE = {'message': 'No Group is Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


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

    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
    if REQUEST:
        GRP = Database().get_record(None, 'group', f' WHERE name = "{name}"')
        if GRP:
            GRPID = GRP[0]['id']
            if 'interfaces' in REQUEST['config']['group'][name]:
                for INTERFACE in REQUEST['config']['group'][name]['interfaces']:
                    NWK = Database().getid_byname('network', INTERFACE['network'])
                    if NWK == None:
                        RESPONSE = {'message': f'Bad Request; Network {NWK} Not Exist.'}
                        ACCESSCODE = 400
                        return json.dumps(RESPONSE), ACCESSCODE
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
                    RESPONSE = {'message': 'Interface Updated.'}
                    ACCESSCODE = 204
            else:
                logger.error('Kindly Provide the interface.')
                RESPONSE = {'message': 'Kindly Provide the interface.'}
                ACCESSCODE = 404
        else:
            logger.error('No Group is Avaiable.')
            RESPONSE = {'message': 'No Group is Avaiable.'}
            ACCESSCODE = 404
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
    return json.dumps(RESPONSE), ACCESSCODE


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
            RESPONSE = {'message': f'Group {name} interface {interface} Removed Successfully.'}
            ACCESSCODE = 204
        else:
            RESPONSE = {'message': f'Group {name} interface {interface} Not Present in Database.'}
            ACCESSCODE = 404
    else:
        RESPONSE = {'message': f'Group {name} Not Present in Database.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE

######################################################## Cluster Configuration #############################################################

@config_blueprint.route("/config/osimage", methods=['GET'])
def config_osimage():
    """
    Input - OS Image ID or Name
    Process - Fetch the OS Image information.
    Output - OSImage Info.
    """
    OSIMAGES = Database().get_record(None, 'osimage', None)
    if OSIMAGES:
        RESPONSE = {'config': {'osimage': {} }}
        for IMAGE in OSIMAGES:
            IMAGENAME = IMAGE['name']
            del IMAGE['id']
            del IMAGE['name']
            RESPONSE['config']['osimage'][IMAGENAME] = IMAGE
        logger.info('Provided List Of All OS Images with Details.')
        ACCESSCODE = 200
    else:
        logger.error('No OS Image is Avaiable.')
        RESPONSE = {'message': 'No OS Image is Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


@config_blueprint.route("/config/osimage/<string:name>", methods=['GET'])
def config_osimage_get(name=None):
    """
    Input - OS Image ID or Name
    Process - Fetch the OS Image information.
    Output - OSImage Info.
    """
    OSIMAGES = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
    if OSIMAGES:
        RESPONSE = {'config': {'osimage': {} }}
        for IMAGE in OSIMAGES:
            del IMAGE['id']
            del IMAGE['name']
            RESPONSE['config']['osimage'][name] = IMAGE
        logger.info(f'Returned OS Image {name} with Details.')
        ACCESSCODE = 200
    else:
        logger.error('No OS Image is Avaiable.')
        RESPONSE = {'message': 'No OS Image is Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE



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
    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
    if REQUEST:
        DATA = REQUEST['config']['osimage'][name]
        IMAGE = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
        if IMAGE:
            IMAGEID = IMAGE[0]['id']
            if 'newosimage' in DATA:
                NEWOSNAME = DATA['newosimage']
                CHECKNEWOS = Database().get_record(None, 'osimage', f' WHERE `name` = "{NEWOSNAME}";')
                if CHECKNEWOS:
                    RESPONSE = {'message': f'{NEWOSNAME} Already Present in Database, Choose Another Name Or Delete {NEWOSNAME}.'}
                    ACCESSCODE = 400
                    return json.dumps(RESPONSE), ACCESSCODE
                else:
                    DATA['name'] = DATA['newosimage']
                    del DATA['newosimage']
                UPDATE = True
            else:
                RESPONSE = {'message': 'Kindly Pass The New OS Image Name.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
        else:
            if 'newosimage' in DATA:
                NEWOSNAME = DATA['newosimage']
                CHECKNEWOS = Database().get_record(None, 'osimage', f' WHERE `name` = "{NEWOSNAME}";')
                if CHECKNEWOS:
                    RESPONSE = {'message': f'{NEWOSNAME} Already Present in Database, Choose Another Name Or Delete {NEWOSNAME}.'}
                    ACCESSCODE = 400
                    return json.dumps(RESPONSE), ACCESSCODE
                else:
                    DATA['name'] = DATA['newosimage']
                    del DATA['newosimage']
                CREATE = True
            else:
                RESPONSE = {'message': 'Kindly Pass The New OS Image Name.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE

        OSIMAGECOLUMNS = Database().get_columns('osimage')
        COLUMNCHECK = Helper().checkin_list(DATA, OSIMAGECOLUMNS)
        if COLUMNCHECK:
            if UPDATE:
                where = [{"column": "id", "value": IMAGEID}]
                row = Helper().make_rows(DATA)
                result = Database().update('osimage', row, where)
                RESPONSE = {'message': f'OS Image {name} Updated Successfully.'}
                ACCESSCODE = 204
            if CREATE:
                DATA['name'] = name
                row = Helper().make_rows(DATA)
                result = Database().insert('osimage', row)
                RESPONSE = {'message': f'OS Image {name} Created Successfully.'}
                ACCESSCODE = 201
        else:
            RESPONSE = {'message': 'Bad Request; Columns are Incorrect.'}
            ACCESSCODE = 400
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
    return json.dumps(RESPONSE), ACCESSCODE


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
        RESPONSE = {'message': f'OS Image {name} Removed Successfully.'}
        ACCESSCODE = 204
    else:
        RESPONSE = {'message': f'OS Image {name} Not Present in Database.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


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
    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
    if REQUEST:
        DATA = REQUEST['config']['osimage'][name]
        IMAGE = Database().get_record(None, 'osimage', f' WHERE name = "{name}"')
        if IMAGE:
            if 'newosimage' in DATA:
                NEWOSNAME = DATA['newosimage']
                CHECKNEWOS = Database().get_record(None, 'osimage', f' WHERE `name` = "{NEWOSNAME}";')
                if CHECKNEWOS:
                    RESPONSE = {'message': f'{NEWOSNAME} Already Present in Database, Choose Another Name Or Delete {NEWOSNAME}.'}
                    ACCESSCODE = 400
                    return json.dumps(RESPONSE), ACCESSCODE
                else:
                    DATA['name'] = DATA['newosimage']
                    del DATA['newosimage']
                    CREATE = True
            else:
                RESPONSE = {'message': 'Kindly Pass The New OS Image Name.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
        else:
            RESPONSE = {'message': f'OS Image {name} Not Present In the Database.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE

        OSIMAGECOLUMNS = Database().get_columns('osimage')
        COLUMNCHECK = Helper().checkin_list(DATA, OSIMAGECOLUMNS)
        if COLUMNCHECK:
            if CREATE:
                row = Helper().make_rows(DATA)
                result = Database().insert('osimage', row)
                RESPONSE = {'message': f'OS Image {name} Clone to {NEWOSNAME} Successfully.'}
                ACCESSCODE = 201
        else:
            RESPONSE = {'message': 'Bad Request; Columns are Incorrect.'}
            ACCESSCODE = 400
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
    return json.dumps(RESPONSE), ACCESSCODE



@config_blueprint.route("/config/osimage/<string:name>/pack", methods=['GET'])
@token_required
def config_osimage_pack(name=None):
    """
    Input - OS Image ID or Name
    Process - Manually Pack the OS Image.
    Output - Success or Failure.
    """
    logger.info("OS Image {} Packed Successfully.".format(name))
    response = {"message": "OS Image {} Packed Successfully.".format(name)}
    code = 200
    return json.dumps(response), code



@config_blueprint.route("/config/osimage/<string:name>/kernel", methods=['GET'])
@token_required
def config_osimage_kernel(name=None):
    """
    Input - OS Image ID or Name
    Process - Change Kernel Version Of the OS Image.
    Output - Success or Failure.
    """
    logger.info("OS Image {} kernel version Changed Successfully.".format(name))
    response = {"message": "OS Image {} kernel version Changed Successfully.".format(name)}
    code = 200
    return json.dumps(response), code


"""
Input - OS Image ID or Name
Process - Manually change kernel version.
Output - Kernel Version.
"""
@config_blueprint.route("/config/osimage/<string:name>/kernel", methods=['POST'])
@token_required
def config_osimage_kernel_post(name=None):
    kernel = True
    if kernel:
        logger.info("OSImage {} Kernel Changed to: {}".format(name, str(kernel)))
        response = {"message": "OSImage {} Kernel Changed to: {}".format(name, str(kernel))}
        code = 200
    else:
        logger.error("OS Image Is Not Exist.")
        response = {"message": "OS Image Is Not Exist."}
        code = 404
    return json.dumps(response), code



######################################################## Cluster Configuration #############################################################


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
        RESPONSE = {'config': {'cluster': CLUSTER[0] }}
        CONTROLLERS = Database().get_record(None, 'controller', f' WHERE clusterid = {CLUSTERID}')
        for CONTROLLER in CONTROLLERS:
            CONTROLLERIP = Database().get_record(None, 'ipaddress', f' WHERE id = {CONTROLLER["ipaddr"]}')
            if CONTROLLERIP:
                CONTROLLER['ipaddress'] = CONTROLLERIP[0]["ipaddress"]
            del CONTROLLER['id']
            del CONTROLLER['clusterid']
            CONTROLLER['luna_config'] = ConfigFile
            RESPONSE['config']['cluster'][CONTROLLER['hostname']] = CONTROLLER
            ACCESSCODE = 200
    else:
        logger.error('No Cluster is Avaiable.')
        RESPONSE = {'message': 'No Cluster is Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


@config_blueprint.route("/config/cluster", methods=['POST'])
@token_required
def config_cluster_post():
    """
    Input - None
    Process - Fetch The Cluster Information.
    Output - Cluster Information.
    """
    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
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
                RESPONSE = {'message': 'Cluster Updated Successfully.'}
                ACCESSCODE = 204
            else:
                RESPONSE = {'message': 'Bad Request; No Cluster is Avaiable to Update.'}
                ACCESSCODE = 400
        else:
            RESPONSE = {'message': 'Bad Request; Columns are Incorrect.'}
            ACCESSCODE = 400
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
    return json.dumps(RESPONSE), 200


######################################################## BMC Setup Configuration #############################################################

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
        RESPONSE = {'config': {'bmcsetup': {} }}
        for BMC in BMCSETUP:
            BMCNAME = BMC['name']
            del BMC['name']
            del BMC['id']
            RESPONSE['config']['bmcsetup'][BMCNAME] = BMC
        ACCESSCODE = 200
    else:
        logger.error('No BMC Setup is Avaiable.')
        RESPONSE = {'message': 'No BMC Setup is Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE



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
        RESPONSE = {'config': {'bmcsetup': {} }}
        for BMC in BMCSETUP:
            BMCNAME = BMC['name']
            del BMC['name']
            del BMC['id']
            RESPONSE['config']['bmcsetup'][BMCNAME] = BMC
        ACCESSCODE = 200
    else:
        logger.error('No BMC Setup is Avaiable.')
        RESPONSE = {'message': 'No BMC Setup is Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE



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
    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
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
                RESPONSE = {'message': 'BMC Setup Created Successfully.'}
                ACCESSCODE = 201
            if UPDATE:
                where = [{"column": "id", "value": BMCID}]
                result = Database().update('bmcsetup', row, where)
                RESPONSE = {'message': 'BMC Setup Updated Successfully.'}
                ACCESSCODE = 204
        else:
            RESPONSE = {'message': 'Bad Request; Columns are Incorrect.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE

    return json.dumps(DATA), ACCESSCODE



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
    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
    if REQUEST:
        DATA = REQUEST['config']['bmcsetup'][bmcname]
        if 'newbmcname' in DATA:
            DATA['name'] = DATA['newbmcname']
            NEWBMCNAME = DATA['newbmcname']
            del DATA['newbmcname']
        else:
            RESPONSE = {'message': 'Kindly Provide the New BMC Name.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE
        CHECKBMC = Database().get_record(None, 'bmcsetup', f' WHERE `name` = "{bmcname}";')
        if CHECKBMC:
            CHECKNEWBMC = Database().get_record(None, 'bmcsetup', f' WHERE `name` = "{NEWBMCNAME}";')
            if CHECKNEWBMC:
                RESPONSE = {'message': f'{NEWBMCNAME} Already Present in Database.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
            else:
                CREATE = True  
        else:
            RESPONSE = {'message': f'{bmcname} Not Present in Database.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE
        BMCCOLUMNS = Database().get_columns('bmcsetup')
        COLUMNCHECK = Helper().checkin_list(DATA, BMCCOLUMNS)
        row = Helper().make_rows(DATA)
        if COLUMNCHECK:
            if CREATE:                    
                result = Database().insert('bmcsetup', row)
                RESPONSE = {'message': 'BMC Setup Created Successfully.'}
                ACCESSCODE = 201
        else:
            RESPONSE = {'message': 'Bad Request; Columns are Incorrect.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE

    return json.dumps(DATA), ACCESSCODE


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
        RESPONSE = {'message': 'BMC Setup Removed Successfully.'}
        ACCESSCODE = 204
    else:
        RESPONSE = {'message': f'{switch} Not Present in Database.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE



######################################################## Switch Configuration #############################################################

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
        RESPONSE = {'config': {'switch': { } }}
        for SWITCH in SWITCHES:
            SWITCHNAME = SWITCH['name']
            SWITCHIP = Database().get_record(None, 'ipaddress', f' WHERE id = {SWITCH["ipaddress"]}')
            logger.debug(f'With Switch {SWITCHNAME} attached IP ROWs {SWITCHIP}')
            if SWITCHIP:
                SWITCH['ipaddress'] = SWITCHIP[0]["ipaddress"]
            del SWITCH['id']
            del SWITCH['name']
            RESPONSE['config']['switch'][SWITCHNAME] = SWITCH
        logger.info("Avaiable Switches are {}.".format(SWITCHES))
        ACCESSCODE = 200
    else:
        logger.error('No Switch is Avaiable.')
        RESPONSE = {'message': 'No Switch is Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


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
        RESPONSE = {'config': {'switch': { } }}
        for SWITCH in SWITCHES:
            SWITCHNAME = SWITCH['name']
            SWITCHIP = Database().get_record(None, 'ipaddress', f' WHERE id = {SWITCH["ipaddress"]}')
            logger.debug(f'With Switch {SWITCHNAME} attached IP ROWs {SWITCHIP}')
            if SWITCHIP:
                SWITCH['ipaddress'] = SWITCHIP[0]["ipaddress"]
            del SWITCH['id']
            del SWITCH['name']
            RESPONSE['config']['switch'][SWITCHNAME] = SWITCH
        logger.info("Avaiable Switches are {}.".format(SWITCHES))
        ACCESSCODE = 200
    else:
        logger.error('No Switch is Avaiable.')
        RESPONSE = {'message': 'No Switch is Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


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
    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
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
                    RESPONSE = {'message': 'Switch Created Successfully.'}
                    ACCESSCODE = 201
                if UPDATE:
                    where = [{"column": "id", "value": SWITCHID}]
                    result = Database().update('switch', row, where)
                    RESPONSE = {'message': 'Switch Updated Successfully.'}
                    ACCESSCODE = 204
            else:
                RESPONSE = {'message': 'Bad Request; Columns are Incorrect.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
        else:
            RESPONSE = {'message': 'Bad Request; IP Address Already Exist in The Database.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE

    return json.dumps(DATA), ACCESSCODE



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
    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
    if REQUEST:
        DATA = REQUEST['config']['switch'][switch]
        if 'newswitchname' in DATA:
            DATA['name'] = DATA['newswitchname']
            NEWSWITCHNAME = DATA['newswitchname']
            del DATA['newswitchname']
        else:
            RESPONSE = {'message': 'Kindly Provide the New Switch Name.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE
        CHECKSWITCH = Database().get_record(None, 'switch', f' WHERE `name` = "{NEWSWITCHNAME}";')
        if CHECKSWITCH:
            RESPONSE = {'message': f'{NEWSWITCHNAME} Already Present in Database.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE
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
                    RESPONSE = {'message': 'Switch Created Successfully.'}
                    ACCESSCODE = 201
            else:
                RESPONSE = {'message': 'Bad Request; Columns are Incorrect.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
        else:
            RESPONSE = {'message': 'Bad Request; IP Address Already Exist in The Database.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE

    return json.dumps(DATA), ACCESSCODE



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
        RESPONSE = {'message': 'Switch Removed Successfully.'}
        ACCESSCODE = 204
    else:
        RESPONSE = {'message': f'{switch} Not Present in Database.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE
    

######################################################## Other Devices Configuration #############################################################


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
        RESPONSE = {'config': {'otherdev': { } }}
        for DEVICE in DEVICES:
            DEVICENAME = DEVICE['name']
            DEVICEIP = Database().get_record(None, 'ipaddress', f' WHERE id = {DEVICE["ipaddress"]}')
            logger.debug(f'With Device {DEVICENAME} attached IP ROWs {DEVICEIP}')
            if DEVICEIP:
                DEVICE['ipaddress'] = DEVICEIP[0]["ipaddress"]
            del DEVICE['id']
            del DEVICE['name']
            RESPONSE['config']['otherdev'][DEVICENAME] = DEVICE
        logger.info("Avaiable Devices are {}.".format(DEVICES))
        ACCESSCODE = 200
    else:
        logger.error('No Device is Avaiable.')
        RESPONSE = {'message': 'No Device is Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


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
        RESPONSE = {'config': {'otherdev': { } }}
        for DEVICE in DEVICES:
            DEVICENAME = DEVICE['name']
            DEVICEIP = Database().get_record(None, 'ipaddress', f' WHERE id = {DEVICE["ipaddress"]}')
            logger.debug(f'With Device {DEVICENAME} attached IP ROWs {DEVICEIP}')
            if DEVICEIP:
                DEVICE['ipaddress'] = DEVICEIP[0]["ipaddress"]
            del DEVICE['id']
            del DEVICE['name']
            RESPONSE['config']['otherdev'][DEVICENAME] = DEVICE
        logger.info("Avaiable Devices are {}.".format(DEVICES))
        ACCESSCODE = 200
    else:
        logger.error('No Device is Avaiable.')
        RESPONSE = {'message': 'No Device is Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


@config_blueprint.route("/config/otherdev/<string:device>", methods=['POST'])
@token_required
def config_otherdev_post(device=None):
    """
    Input - Device Name
    Output - Create or Update Device.
    """
    DATA = {}
    CREATE, UPDATE = False, False
    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
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
                    RESPONSE = {'message': 'Device Created Successfully.'}
                    ACCESSCODE = 201
                if UPDATE:
                    where = [{"column": "id", "value": DEVICEID}]
                    result = Database().update('otherdevices', row, where)
                    RESPONSE = {'message': 'Device Updated Successfully.'}
                    ACCESSCODE = 204
            else:
                RESPONSE = {'message': 'Bad Request; Columns are Incorrect.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
        else:
            RESPONSE = {'message': 'Bad Request; IP Address Already Exist in The Database.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE

    return json.dumps(DATA), ACCESSCODE



@config_blueprint.route("/config/otherdev/<string:device>/_clone", methods=['POST'])
@token_required
def config_otherdev_clone(device=None):
    """
    Input - Device ID or Name
    Output - Clone The Device.
    """
    DATA = {}
    CREATE = False
    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
    if REQUEST:
        DATA = REQUEST['config']['otherdev'][device]
        if 'newotherdevname' in DATA:
            DATA['name'] = DATA['newotherdevname']
            NEWDEVICENAME = DATA['newotherdevname']
            del DATA['newotherdevname']
        else:
            RESPONSE = {'message': 'Kindly Provide the New Device Name.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE
        CHECKDEVICE = Database().get_record(None, 'otherdevices', f' WHERE `name` = "{NEWDEVICENAME}";')
        if CHECKDEVICE:
            RESPONSE = {'message': f'{NEWDEVICENAME} Already Present in Database.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE
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
                    RESPONSE = {'message': 'Device Cloned Successfully.'}
                    ACCESSCODE = 201
            else:
                RESPONSE = {'message': 'Bad Request; Columns are Incorrect.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
        else:
            RESPONSE = {'message': 'Bad Request; IP Address Already Exist in The Database.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE

    return json.dumps(DATA), ACCESSCODE



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
        RESPONSE = {'message': 'Device Removed Successfully.'}
        ACCESSCODE = 204
    else:
        RESPONSE = {'message': f'{device} Not Present in Database.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


######################################################## Network Configuration #############################################################


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
        RESPONSE = {'config': {'network': {} }}
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
            RESPONSE['config']['network'][NWK['name']] = NWK
        ACCESSCODE = 200
    else:
        logger.error('No Networks is Avaiable.')
        RESPONSE = {'message': 'No Networks is Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


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
        RESPONSE = {'config': {'network': {} }}
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
            RESPONSE['config']['network'][NWK['name']] = NWK
        ACCESSCODE = 200
    else:
        logger.error(f'Network {name} is Not Avaiable.')
        RESPONSE = {'message': f'Network {name} is Not Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


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
    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
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
                    RESPONSE = {'message': f'{NEWNETWORKNAME} Already Present in Database, Choose Another Name Or Delete {NEWNETWORKNAME}.'}
                    ACCESSCODE = 400
                    return json.dumps(RESPONSE), ACCESSCODE
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
                RESPONSE = {'message': f'Incorrect Network IP: {DATA["network"]}.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
        if 'gateway' in DATA:
            GWDETAILS = Helper().check_ip_range(DATA['gateway'], DATA['network']+'/'+DATA['subnet'])
            if not GWDETAILS:
                RESPONSE = {'message': f'Incorrect Gateway IP: {DATA["gateway"]}.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
        if 'ns_ip' in DATA:
            NSIPDETAILS = Helper().check_ip_range(DATA['ns_ip'], DATA['network']+'/'+DATA['subnet'])
            if not NSIPDETAILS:
                RESPONSE = {'message': f'Incorrect NS IP: {DATA["ns_ip"]}.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
        if 'ntp_server' in DATA:
            NTPDETAILS = Helper().check_ip_range(DATA['ntp_server'], DATA['network']+'/'+DATA['subnet'])
            if not NTPDETAILS:
                RESPONSE = {'message': f'Incorrect NTP Server IP: {DATA["ntp_server"]}.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
        if 'dhcp' in DATA:
            if 'dhcp_range_begin' in DATA:
                DHCPSTARTDETAILS = Helper().check_ip_range(DATA['dhcp_range_begin'], DATA['network']+'/'+DATA['subnet'])
                if not DHCPSTARTDETAILS:
                    RESPONSE = {'message': f'Incorrect DHCP Start Range IP: {DATA["dhcp_range_begin"]}.'}
                    ACCESSCODE = 400
                    return json.dumps(RESPONSE), ACCESSCODE
            else:
                RESPONSE = {'message': f'DHCP Start Range is a Required Parameter.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
            if 'dhcp_range_end' in DATA:
                DHCPENDDETAILS = Helper().check_ip_range(DATA['dhcp_range_end'], DATA['network']+'/'+DATA['subnet'])
                if not DHCPENDDETAILS:
                    RESPONSE = {'message': f'Incorrect DHCP End Range IP: {DATA["dhcp_range_end"]}.'}
                    ACCESSCODE = 400
                    return json.dumps(RESPONSE), ACCESSCODE
            else:
                RESPONSE = {'message': f'DHCP End Range is a Required Parameter.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
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
                RESPONSE = {'message': 'Network Created Successfully.'}
                ACCESSCODE = 201
            if UPDATE:
                where = [{"column": "id", "value": NETWORKID}]
                result = Database().update('network', row, where)
                RESPONSE = {'message': 'Network Updated Successfully.'}
                ACCESSCODE = 204
        else:
            RESPONSE = {'message': 'Bad Request; Columns are Incorrect.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE

    return json.dumps(DATA), ACCESSCODE


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
    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
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
                    RESPONSE = {'message': f'{NEWNETWORKNAME} Already Present in Database, Choose Another Name Or Delete {NEWNETWORKNAME}.'}
                    ACCESSCODE = 400
                    return json.dumps(RESPONSE), ACCESSCODE
                else:
                    DATA['name'] = DATA['newnetname']
                    del DATA['newnetname']
            CREATE = True
        else:
            RESPONSE = {'message': f'Bad Request; Network {name} is Not Present in Database.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE
        if 'network' in DATA:
            NWKIP = Helper().check_ip(DATA['network'])
            if NWKIP:
                NWKDETAILS = Helper().get_network_details(DATA['network'])
                DATA['network'] = NWKIP
                DATA['subnet'] = NWKDETAILS['subnet']
            else:
                RESPONSE = {'message': f'Incorrect Network IP: {DATA["network"]}.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
        if 'gateway' in DATA:
            GWDETAILS = Helper().check_ip_range(DATA['gateway'], DATA['network']+'/'+DATA['subnet'])
            if not GWDETAILS:
                RESPONSE = {'message': f'Incorrect Gateway IP: {DATA["gateway"]}.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
        if 'ns_ip' in DATA:
            NSIPDETAILS = Helper().check_ip_range(DATA['ns_ip'], DATA['network']+'/'+DATA['subnet'])
            if not NSIPDETAILS:
                RESPONSE = {'message': f'Incorrect NS IP: {DATA["ns_ip"]}.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
        if 'ntp_server' in DATA:
            NTPDETAILS = Helper().check_ip_range(DATA['ntp_server'], DATA['network']+'/'+DATA['subnet'])
            if not NTPDETAILS:
                RESPONSE = {'message': f'Incorrect NTP Server IP: {DATA["ntp_server"]}.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
        if 'dhcp' in DATA:
            if 'dhcp_range_begin' in DATA:
                DHCPSTARTDETAILS = Helper().check_ip_range(DATA['dhcp_range_begin'], DATA['network']+'/'+DATA['subnet'])
                if not DHCPSTARTDETAILS:
                    RESPONSE = {'message': f'Incorrect DHCP Start Range IP: {DATA["dhcp_range_begin"]}.'}
                    ACCESSCODE = 400
                    return json.dumps(RESPONSE), ACCESSCODE
            else:
                RESPONSE = {'message': f'DHCP Start Range is a Required Parameter.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
            if 'dhcp_range_end' in DATA:
                DHCPENDDETAILS = Helper().check_ip_range(DATA['dhcp_range_end'], DATA['network']+'/'+DATA['subnet'])
                if not DHCPENDDETAILS:
                    RESPONSE = {'message': f'Incorrect DHCP End Range IP: {DATA["dhcp_range_end"]}.'}
                    ACCESSCODE = 400
                    return json.dumps(RESPONSE), ACCESSCODE
            else:
                RESPONSE = {'message': f'DHCP End Range is a Required Parameter.'}
                ACCESSCODE = 400
                return json.dumps(RESPONSE), ACCESSCODE
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
                RESPONSE = {'message': 'Network Created Successfully.'}
                ACCESSCODE = 201
        else:
            RESPONSE = {'message': 'Bad Request; Columns are Incorrect.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE

    return json.dumps(DATA), ACCESSCODE


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
        RESPONSE = {'message': 'Network Removed Successfully.'}
        ACCESSCODE = 204
    else:
        RESPONSE = {'message': f'Network {name} Not Present in Database.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


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
                RESPONSE = {'config': {'network': {ipaddr: {'status': 'taken'} } } }
                ACCESSCODE = 200
            else:
                RESPONSE = {'config': {'network': {ipaddr: {'status': 'free'} } } }
                ACCESSCODE = 200
        else:
            RESPONSE = {'message': f'{ipaddr} Is Not In The Range.'}
            ACCESSCODE = 404
            return json.dumps(RESPONSE), ACCESSCODE
    else:
        RESPONSE = {'message': f'Network {name} Not Present in Database.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


@config_blueprint.route("/config/network/<string:name>/_nextfreeip", methods=['GET'])
@token_required
def config_network_nextip(name=None):
    """
    Input - Network Name
    Process - Find The Next Available IP on the Netwok.
    Output - Next Available IP on the Netwok.
    """
    RESPONSE = {'config': {'network': {name: {'nextip': '10.141.0.2'} } } }
    if RESPONSE:
        RESPONSE = {'config': {'network': {name: {'nextip': '10.141.0.2'} } } }
        ACCESSCODE = 200
    else:
        RESPONSE = {'message': f'Network {name} Not Present in Database.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


######################################################## Secrets Configuration #############################################################


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
        RESPONSE = {'config': {'secrets': {} }}
        ACCESSCODE = 200
    else:
        logger.error('Secrets are not Avaiable.')
        RESPONSE = {'message': 'Secrets are not Avaiable.'}
        ACCESSCODE = 404
    if NODESECRETS:
        RESPONSE['config']['secrets']['node'] = {}
        for NODE in NODESECRETS:
            NODENAME = Database().getname_byid('node', NODE['nodeid'])
            if NODENAME not in RESPONSE['config']['secrets']['node']:
                RESPONSE['config']['secrets']['node'][NODENAME] = []
            del NODE['nodeid']
            del NODE['id']
            NODE['content'] = Helper().decrypt_string(NODE['content'])
            RESPONSE['config']['secrets']['node'][NODENAME].append(NODE)
    if GROUPSECRETS:
        RESPONSE['config']['secrets']['group'] = {}
        for GROUP in GROUPSECRETS:
            GROUPNAME = Database().getname_byid('group', GROUP['groupid'])
            if GROUPNAME not in RESPONSE['config']['secrets']['group']:
                RESPONSE['config']['secrets']['group'][GROUPNAME] = []
            del GROUP['groupid']
            del GROUP['id']
            GROUP['content'] = Helper().decrypt_string(GROUP['content'])
            RESPONSE['config']['secrets']['group'][GROUPNAME].append(GROUP)
    return json.dumps(RESPONSE), ACCESSCODE


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
            RESPONSE = {'config': {'secrets': {} }}
            ACCESSCODE = 200
        else:
            logger.error(f'Secrets are not Avaiable for Node {name}.')
            RESPONSE = {'message': f'Secrets are not Avaiable for Node {name}.'}
            ACCESSCODE = 404
        if NODESECRETS:
            RESPONSE['config']['secrets']['node'] = {}
            for NODE in NODESECRETS:
                NODENAME = Database().getname_byid('node', NODE['nodeid'])
                if NODENAME not in RESPONSE['config']['secrets']['node']:
                    RESPONSE['config']['secrets']['node'][NODENAME] = []
                del NODE['nodeid']
                del NODE['id']
                NODE['content'] = Helper().decrypt_string(NODE['content'])
                RESPONSE['config']['secrets']['node'][NODENAME].append(NODE)
        if GROUPSECRETS:
            RESPONSE['config']['secrets']['group'] = {}
            for GROUP in GROUPSECRETS:
                GROUPNAME = Database().getname_byid('group', GROUP['groupid'])
                if GROUPNAME not in RESPONSE['config']['secrets']['group']:
                    RESPONSE['config']['secrets']['group'][GROUPNAME] = []
                del GROUP['groupid']
                del GROUP['id']
                GROUP['content'] = Helper().decrypt_string(GROUP['content'])
                RESPONSE['config']['secrets']['group'][GROUPNAME].append(GROUP)
    else:
        logger.error(f'Node {name} is not Avaiable.')
        RESPONSE = {'message': f'Node {name} is not Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


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
    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
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
                logger.error('Kindly provide at least one secret.')
                RESPONSE = {'message': 'Kindly provide at least one secret.'}
                ACCESSCODE = 404
        else:
            logger.error(f'Node {name} is not Avaiable.')
            RESPONSE = {'message': f'Node {name} is not Avaiable.'}
            ACCESSCODE = 404

        if CREATE == True and UPDATE == True:
            RESPONSE = {'message': f'Node {name} Secrets Created & Updated Successfully.'}
            ACCESSCODE = 201
        elif CREATE == True and UPDATE == False:
            RESPONSE = {'message': f'Node {name} Secret Created Successfully.'}
            ACCESSCODE = 201
        elif CREATE == False and UPDATE == True:
            RESPONSE = {'message': f'Node {name} Secret Updated Successfully.'}
            ACCESSCODE = 201
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
    return json.dumps(RESPONSE), ACCESSCODE


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
            RESPONSE = {'config': {'secrets': {'node': {name: [] } } } }
            ACCESSCODE = 200
            del SECRET[0]['nodeid']
            del SECRET[0]['id']
            SECRET[0]['content'] = Helper().decrypt_string(SECRET[0]['content'])
            RESPONSE['config']['secrets']['node'][name] = SECRET
        else:
            logger.error(f'Secret {secret} is Unavaiable for Node {name}.')
            RESPONSE = {'message': f'Secret {secret} is Unavaiable for Node {name}.'}
            ACCESSCODE = 404
    else:
        logger.error(f'Node {name} is not Avaiable.')
        RESPONSE = {'message': f'Node {name} is not Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


@config_blueprint.route("/config/secrets/node/<string:name>/<string:secret>", methods=['POST'])
@token_required
def config_post_node_secret(name=None, secret=None):
    """
    Input - Node Name & Payload
    Process - Create Or Update Node Secrets.
    Output - None.
    """
    DATA = {}
    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
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
                        RESPONSE = {'message': f'Node {name} Secret {secret} Updated Successfully.'}
                        ACCESSCODE = 204
                else:
                    logger.error(f'Node {name}, Secret {secret} is Unavaiable.')
                    RESPONSE = {'message': f'Node {name}, Secret {secret} is Unavaiable.'}
                    ACCESSCODE = 404
            else:
                logger.error('Kindly provide at least one secret.')
                RESPONSE = {'message': 'Kindly provide at least one secret.'}
                ACCESSCODE = 404
        else:
            logger.error(f'Node {name} is not Avaiable.')
            RESPONSE = {'message': f'Node {name} is not Avaiable.'}
            ACCESSCODE = 404
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
    return json.dumps(RESPONSE), ACCESSCODE


@config_blueprint.route("/config/secrets/node/<string:name>/<string:secret>/_clone", methods=['POST'])
@token_required
def config_clone_node_secret(name=None, secret=None):
    """
    Input - Node Name & Payload
    Process - Create Or Update Node Secrets.
    Output - None.
    """
    DATA = {}
    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
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
                            logger.error(f'Secret {NEWSECRETNAME} Already Present..')
                            RESPONSE = {'message': f'Secret {NEWSECRETNAME} Already Present..'}
                            ACCESSCODE = 404 
                        else:
                            NODESECRETSCOLUMNS = Database().get_columns('nodesecrets')
                            COLUMNCHECK = Helper().checkin_list(DATA[0], NODESECRETSCOLUMNS)
                            if COLUMNCHECK:
                                SECRETID = SECRETDATA[0]['id']
                                DATA[0]['content'] = Helper().encrypt_string(DATA[0]['content'])
                                row = Helper().make_rows(DATA[0])
                                Database().insert('nodesecrets', row)
                                RESPONSE = {'message': f'Node {name} Secret {secret} Clone Successfully to {NEWSECRETNAME}.'}
                                ACCESSCODE = 204
                    else:
                        logger.error('Kindly Pass the New Secret Name.')
                        RESPONSE = {'message': 'Kindly Pass the New Secret Name.'}
                        ACCESSCODE = 404
                else:
                    logger.error(f'Node {name}, Secret {secret} is Unavaiable.')
                    RESPONSE = {'message': f'Node {name}, Secret {secret} is Unavaiable.'}
                    ACCESSCODE = 404
            else:
                logger.error('Kindly provide at least one secret.')
                RESPONSE = {'message': 'Kindly provide at least one secret.'}
                ACCESSCODE = 404
        else:
            logger.error(f'Node {name} is not Avaiable.')
            RESPONSE = {'message': f'Node {name} is not Avaiable.'}
            ACCESSCODE = 404
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
    return json.dumps(RESPONSE), ACCESSCODE


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
            RESPONSE = {'message': f'Secret {secret} Deleted From Node {name}.'}
            ACCESSCODE = 204
        else:
            logger.error(f'Secret {secret} is Unavaiable for Node {name}.')
            RESPONSE = {'message': f'Secret {secret} is Unavaiable for Node {name}.'}
            ACCESSCODE = 404
    else:
        logger.error(f'Node {name} is not Avaiable.')
        RESPONSE = {'message': f'Node {name} is not Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


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
            RESPONSE = {'config': {'secrets': {'group': {name: [] } } } }
            for GRP in GROUPSECRETS:
                del GRP['groupid']
                del GRP['id']
                GRP['content'] = Helper().decrypt_string(GRP['content'])
                RESPONSE['config']['secrets']['group'][name].append(GRP)
                ACCESSCODE = 200
        else:
            logger.error(f'Secrets are not Avaiable for Group {name}.')
            RESPONSE = {'message': f'Secrets are not Avaiable for Group {name}.'}
            ACCESSCODE = 404
    else:
        logger.error(f'Group {name} is not Avaiable.')
        RESPONSE = {'message': f'Group {name} is not Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


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
    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
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
                logger.error('Kindly provide at least one secret.')
                RESPONSE = {'message': 'Kindly provide at least one secret.'}
                ACCESSCODE = 404
        else:
            logger.error(f'Group {name} is not Avaiable.')
            RESPONSE = {'message': f'Group {name} is not Avaiable.'}
            ACCESSCODE = 404

        if CREATE == True and UPDATE == True:
            RESPONSE = {'message': f'Group {name} Secrets Created & Updated Successfully.'}
            ACCESSCODE = 204
        elif CREATE == True and UPDATE == False:
            RESPONSE = {'message': f'Group {name} Secret Created Successfully.'}
            ACCESSCODE = 201
        elif CREATE == False and UPDATE == True:
            RESPONSE = {'message': f'Group {name} Secret Updated Successfully.'}
            ACCESSCODE = 204
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
    return json.dumps(RESPONSE), ACCESSCODE


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
            RESPONSE = {'config': {'secrets': {'group': {name: [] } } } }
            ACCESSCODE = 200
            del SECRET[0]['groupid']
            del SECRET[0]['id']
            SECRET[0]['content'] = Helper().decrypt_string(SECRET[0]['content'])
            RESPONSE['config']['secrets']['group'][name] = SECRET
        else:
            logger.error(f'Secret {secret} is Unavaiable for Group {name}.')
            RESPONSE = {'message': f'Secret {secret} is Unavaiable for Group {name}.'}
            ACCESSCODE = 404
    else:
        logger.error(f'Group {name} is not Avaiable.')
        RESPONSE = {'message': f'Group {name} is not Avaiable.'}
        ACCESSCODE = 404
    return json.dumps(RESPONSE), ACCESSCODE


@config_blueprint.route("/config/secrets/group/<string:name>/<string:secret>", methods=['POST'])
@token_required
def config_post_group_secret(name=None, secret=None):
    """
    Input - Group Name & Payload
    Process - Create Or Update Group Secrets.
    Output - None.
    """
    DATA = {}
    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
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
                        RESPONSE = {'message': f'Group {name} Secret {secret} Updated Successfully.'}
                        ACCESSCODE = 204
                else:
                    logger.error(f'Group {name}, Secret {secret} is Unavaiable.')
                    RESPONSE = {'message': f'Group {name}, Secret {secret} is Unavaiable.'}
                    ACCESSCODE = 404
            else:
                logger.error('Kindly provide at least one secret.')
                RESPONSE = {'message': 'Kindly provide at least one secret.'}
                ACCESSCODE = 404
        else:
            logger.error(f'Group {name} is not Avaiable.')
            RESPONSE = {'message': f'Group {name} is not Avaiable.'}
            ACCESSCODE = 404
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
    return json.dumps(RESPONSE), ACCESSCODE


@config_blueprint.route("/config/secrets/group/<string:name>/<string:secret>/_clone", methods=['POST'])
@token_required
def config_clone_group_secret(name=None, secret=None):
    """
    Input - Group Name & Payload
    Process - Clone Group Secrets.
    Output - None.
    """
    DATA = {}
    REQUESTCHECK = Helper().check_json(request.data)
    if REQUESTCHECK:
        REQUEST = request.get_json(force=True)
    else:
        RESPONSE = {'message': 'Bad Request.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE
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
                            logger.error(f'Secret {NEWSECRETNAME} Already Present..')
                            RESPONSE = {'message': f'Secret {NEWSECRETNAME} Already Present..'}
                            ACCESSCODE = 404 
                        else:
                            GRPSECRETSCOLUMNS = Database().get_columns('groupsecrets')
                            COLUMNCHECK = Helper().checkin_list(DATA[0], GRPSECRETSCOLUMNS)
                            if COLUMNCHECK:
                                SECRETID = SECRETDATA[0]['id']
                                DATA[0]['content'] = Helper().encrypt_string(DATA[0]['content'])
                                row = Helper().make_rows(DATA[0])
                                Database().insert('groupsecrets', row)
                                RESPONSE = {'message': f'Group {name} Secret {secret} Clone Successfully to {NEWSECRETNAME}.'}
                                ACCESSCODE = 204
                    else:
                        logger.error('Kindly Pass the New Secret Name.')
                        RESPONSE = {'message': 'Kindly Pass the New Secret Name.'}
                        ACCESSCODE = 404
                else:
                    logger.error(f'Group {name}, Secret {secret} is Unavaiable.')
                    RESPONSE = {'message': f'Group {name}, Secret {secret} is Unavaiable.'}
                    ACCESSCODE = 404
            else:
                logger.error('Kindly provide at least one secret.')
                RESPONSE = {'message': 'Kindly provide at least one secret.'}
                ACCESSCODE = 404
        else:
            logger.error(f'Group {name} is not Avaiable.')
            RESPONSE = {'message': f'Group {name} is not Avaiable.'}
            ACCESSCODE = 404
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
    return json.dumps(RESPONSE), ACCESSCODE


# @config_blueprint.route("/config/secrets/node/<string:name>/<string:secret>/_delete", methods=['GET'])
# @token_required
# def config_node_secret_delete(name=None, secret=None):
#     """
#     Input - Node Name & Secret Name
#     Output - Success or Failure
#     """
#     NODE = Database().get_record(None, 'node', f' WHERE name = "{name}"')
#     if NODE:
#         NODEID  = NODE[0]['id']
#         SECRET = Database().get_record(None, 'nodesecrets', f' WHERE nodeid = "{NODEID}" AND name = "{secret}"')
#         if SECRET:
#             Database().delete_row('nodesecrets', [{"column": "nodeid", "value": NODEID}, {"column": "name", "value": secret}])
#             RESPONSE = {'message': f'Secret {secret} Deleted From Node {name}.'}
#             ACCESSCODE = 204
#         else:
#             logger.error(f'Secret {secret} is Unavaiable for Node {name}.')
#             RESPONSE = {'message': f'Secret {secret} is Unavaiable for Node {name}.'}
#             ACCESSCODE = 404
#     else:
#         logger.error(f'Node {name} is not Avaiable.')
#         RESPONSE = {'message': f'Node {name} is not Avaiable.'}
#         ACCESSCODE = 404
#     return json.dumps(RESPONSE), ACCESSCODE