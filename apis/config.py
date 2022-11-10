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

logger = Log.get_logger()

config_blueprint = Blueprint('config', __name__)


"""
Input - None
Process - Fetch the list of avaiable Nodes.
Output - Return the List Of Nodes.
"""
@config_blueprint.route("/config/node", methods=['GET'])
def config_node():
    nodes = True
    if nodes:
        logger.info("Avaiable Nodes => {}".format(str(nodes)))
        response = {"message": "Avaiable Nodes => {}".format(str(nodes))}
        code = 200
    else:
        logger.error("Nodes aren't Avaiable.")
        response = {"message": "Nodes aren't Avaiable."}
        code = 404
    return json.dumps(response), code


"""
Input - Node ID or Name
Process - Fetch the node host information.
Output - Node Info.
"""
@config_blueprint.route("/config/node/<string:node>", methods=['GET'])
def config_node_get(node=None):
    nodes = True
    if nodes:
        logger.info("Node Information => {}".format(str(nodes)))
        response = {"message": "Node Information => {}".format(str(nodes))}
        code = 200
    else:
        logger.error("Node Is Not Exist.")
        response = {"message": "Node Is Not Exist."}
        code = 404
    return json.dumps(response), code


"""
Input - Node ID or Name
Process - Create OR Update the Node.
Output - Create OR Update Info.
"""
@config_blueprint.route("/config/node/<string:node>", methods=['POST'])
@token_required
def config_node_post(node=None):
    create = True
    update = False
    if create:
        logger.info("Node {} Created Successfully.".format(str(node)))
        response = {"message": "Node {} Created Successfully.".format(str(node))}
        code = 201
    elif update:
        logger.info("Node {} Updated Successfully.".format(str(node)))
        response = {"message": "Node {} Updated Successfully.".format(str(node))}
        code = 200
    else:
        logger.error("Node Is Not Exist.")
        response = {"message": "Node Is Not Exist."}
        code = 404
    return json.dumps(response), code


"""
Input - Node ID or Name
Process - Delete the Node.
Output - Delete Info.
"""
@config_blueprint.route("/config/node/<string:node>/remove", methods=['POST'])
@token_required
def config_node_remove(node=None):
    remove = True
    if remove:
        logger.info("Node {} Removed Successfully.".format(str(node)))
        response = {"message": "Node {} Removed Successfully.".format(str(node))}
        code = 204
    else:
        logger.error("Node Is Not Exist.")
        response = {"message": "Node Is Not Exist."}
        code = 404
    return json.dumps(response), code


"""
Input - Node ID or Name
Process - Fetch the List the network interfaces of the Node.
Output - Network Interfaces.
"""
@config_blueprint.route("/config/node/<string:node>/interfaces", methods=['GET'])
def config_node_interfaces_get(node=None):
    interfaces = True
    if interfaces:
        logger.info("Node {} Have Network Interfaces {}.".format(str(node), str(interfaces)))
        response = {"message": "Node {} Have Network Interfaces {}.".format(str(node), str(interfaces))}
        code = 204
    else:
        logger.error("Node {} Doesn't have any Network Interfaces.".format(str(node)))
        response = {"message": "Node {} Doesn't have any Network Interfaces.".format(str(node))}
        code = 404
    return json.dumps(response), code


"""
Input - Node ID or Name
Process - Updates the interface array for the Node. {Note that this overrides the group}
Output - Network Interfaces.
"""
@config_blueprint.route("/config/node/<string:node>/interfaces", methods=['POST'])
@token_required
def config_node_interfaces_post(node=None):
    create = True
    update = False
    interface = True
    if create:
        logger.info("Network Interfaces {} Is Created for Node {}.".format(str(interfaces), str(node)))
        response = {"message": "Network Interfaces {} Is Created for Node {}.".format(str(interfaces), str(node))}
        code = 201
    elif update:
        logger.info("Network Interfaces {} Is Updated for Node {}.".format(str(interfaces), str(node)))
        response = {"message": "Network Interfaces {} Is Updated for Node {}.".format(str(interfaces), str(node))}
        code = 200
    else:
        logger.error("Node {} Doesn't have any Network Interfaces.".format(str(node)))
        response = {"message": "Node {} Doesn't have any Network Interfaces.".format(str(node))}
        code = 404
    return json.dumps(response), code


"""
Input - None
Process - Fetch The List Of Groups.
Output - Group List.
"""
@config_blueprint.route("/config/group", methods=['GET'])
def config_group():
    groups = True
    if groups:
        logger.info("Avaiable Groups => {}".format(str(groups)))
        response = {"message": "Avaiable Groups => {}".format(str(groups))}
        code = 200
    else:
        logger.error("Groups aren't Avaiable.")
        response = {"message": "Groups aren't Avaiable."}
        code = 404
    return json.dumps(response), code


"""
Input - Group ID or Name
Process - Fetch The Information Of The Groups.
Output - Group Information.
"""
@config_blueprint.route("/config/group/<string:group>", methods=['GET'])
def config_group_get(group=None):
    groupdetail = True
    if groupdetail:
        logger.info("Group {} Details is {}.".format(group, str(groupdetail)))
        response = {"message": "Group {} Details is {}.".format(group, str(groupdetail))}
        code = 200
    else:
        logger.error("Group is Not Exist.")
        response = {"message": "Group is Not Exist."}
        code = 404
    return json.dumps(response), code


"""
Input - Group ID or Name
Process - Create Or Update The Groups.
Output - Group Information.
"""
@config_blueprint.route("/config/group/<string:group>", methods=['POST'])
@token_required
def config_group_post(group=None):
    create = True
    update = False
    if create:
        logger.info("Group {} Created Successfully.".format(group))
        response = {"message": "Group {} Created Successfully.".format(group)}
        code = 201
    elif update:
        logger.info("Group {} Updated Successfully.".format(group))
        response = {"message": "Group {} Updated Successfully.".format(group)}
        code = 200
    else:
        logger.error("Group is Not Exist.")
        response = {"message": "Group is Not Exist."}
        code = 404
    return json.dumps(response), code


"""
Input - Group ID or Name
Process - Delete The Groups.
Output - Group Information.
"""
@config_blueprint.route("/config/group/<string:group>/remove", methods=['POST'])
@token_required
def config_group_remove(group=None):
    remove = True
    if remove:
        logger.info("Group {} Deleted Successfully.".format(group))
        response = {"message": "Group {} Deleted Successfully.".format(group)}
        code = 204
    else:
        logger.error("Group is Not Exist.")
        response = {"message": "Group is Not Exist."}
        code = 404
    return json.dumps(response), code


"""
Input - Group ID or Name
Process - Fetch List the network interfaces of the Group.
Output - Network Interface List.
"""
@config_blueprint.route("/config/group/<string:group>/interfaces", methods=['GET'])
def config_group_interfaces_get(group=None):
    interfaces = True
    if interfaces:
        logger.info("Group {} Have Network Interfaces => {}.".format(group, str(interfaces)))
        response = {"message": "Group {} Have Network Interfaces => {}.".format(group, str(interfaces))}
        code = 200
    else:
        logger.error("Group {} Don't Have Any Network Interfaces.".format(group))
        response = {"message": "Group {} Don't Have Any Network Interfaces.".format(group)}
        code = 404
    return json.dumps(response), code


"""
Input - Group ID or Name
Process - Create or Update network interfaces of the Group. {BOOTIF and BMC are reserved}
Output - Network Interface Info.
"""
@config_blueprint.route("/config/group/<string:group>/interfaces", methods=['POST'])
@token_required
def config_group_interfaces_post(group=None):
    create = True
    update = False
    interfaces = True
    if create:
        logger.info("Network Interfaces {} Created For The Group {}.".format(str(interfaces), group))
        response = {"message": "Network Interfaces {} Created For The Group {}.".format(str(interfaces), group)}
        code = 201
    elif update:
        logger.info("Network Interfaces {} Updated For The Group {}.".format(str(interfaces), group))
        response = {"message": "Network Interfaces {} Updated For The Group {}.".format(str(interfaces), group)}
        code = 200
    else:
        logger.error("Group {} Don't Have Any Network Interfaces.".format(group))
        response = {"message": "Group {} Don't Have Any Network Interfaces.".format(group)}
        code = 404
    return json.dumps(response), code


"""
Input - OS Image ID or Name
Process - Fetch the OS Image information.
Output - OSImage Info.
"""
@config_blueprint.route("/config/osimage/<string:name>", methods=['GET'])
def config_osimage_get(name=None):
    osimage = True
    if osimage:
        logger.info("OS Image {} information is: {}".format(name, str(osimage)))
        response = {"message": "OS Image {} information is: {}".format(name, str(osimage))}
        code = 200
    else:
        logger.error("OS Image Doesn't Exist.")
        response = {"message": "OS Image Doesn't Exist."}
        code = 404
    return json.dumps(response), code


"""
Input - OS Image ID or Name
Process - Create or Update the OS Image information.
Output - OSImage Info.
"""
@config_blueprint.route("/config/osimage/<string:name>", methods=['POST'])
@token_required
def config_osimage_post(name=None):
    create = True
    update = False
    if create:
        logger.info("OS Image {} Created Successfully.".format(name))
        response = {"message": "OS Image {} Created Successfully.".format(name)}
        code = 201
    elif update:
        logger.info("OS Image {} Updated Successfully.".format(name))
        response = {"message": "OS Image {} Updated Successfully.".format(name)}
        code = 200
    else:
        logger.error("OS Image Creation Failed.")
        response = {"message": "OS Image Creation Failed."}
        code = 404
    return json.dumps(response), code


"""
Input - OS Image ID or Name
Process - Delete the OS Image.
Output - OSImage Info.
"""
@config_blueprint.route("/config/osimage/<string:name>/remove", methods=['GET'])
@validate_access
def config_osimage_remove(name=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
        remove = True
        if remove:
            logger.info("OS Image {} Deleted Successfully.".format(name))
            response = {"message": "OS Image {} Deleted Successfully.".format(name)}
            code = 204
        else:
            logger.error("OS Image Is Not Exist.")
            response = {"message": "OS Image Is Not Exist."}
            code = 404
    else:
        logger.error("Need a Valid Token to Perform this action.")
        response = {"message": "Need a Valid Token to Perform this action."}
        code = 401
    return json.dumps(response), code


"""
Input - OS Image ID or Name
Process - Manually Pack the OS Image.
Output - Success or Failure.
"""
@config_blueprint.route("/config/osimage/<string:name>/pack", methods=['GET'])
@validate_access
def config_osimage_pack(name=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
        pack = True
        if pack:
            logger.info("OS Image {} Packed Successfully.".format(name))
            response = {"message": "OS Image {} Packed Successfully.".format(name)}
            code = 204
        else:
            logger.error("OS Image Is Not Exist.")
            response = {"message": "OS Image Is Not Exist."}
            code = 404
    else:
        logger.error("Need a Valid Token to Perform this action.")
        response = {"message": "Need a Valid Token to Perform this action."}
        code = 401
    return json.dumps(response), code


"""
Input - OS Image ID or Name
Process - Fetch The Kernel Version.
Output - Kernel Version.
"""
@config_blueprint.route("/config/osimage/<string:name>/kernel", methods=['GET'])
@validate_access
def config_osimage_kernel_get(name=None):
    kernel = True
    if kernel:
        logger.info("OS Image {} Kernel is: {}".format(name, str(kernel)))
        response = {"message": "OS Image {} Kernel is: {}".format(name, str(kernel))}
        code = 200
    else:
        logger.error("OS Image Is Not Exist.")
        response = {"message": "OS Image Is Not Exist."}
        code = 404
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


"""
Input - None
Process - Fetch The Cluster Information.
Output - Cluster Information.
"""
@config_blueprint.route("/config/cluster", methods=['GET'])
def config_cluster():
    cluster = True
    if cluster:
        logger.info("Cluster Information: {}".format(str(cluster)))
        response = {"message": "Cluster Information: {}".format(str(cluster))}
        code = 200
    else:
        logger.error("Cluster Is Not Exist.")
        response = {"message": "Cluster Is Not Exist."}
        code = 404
    return json.dumps(response), code


"""
Input - None
Process - Fetch The list of configured settings.
Output - List Of BMC Setup.
"""
@config_blueprint.route("/config/bmcsetup", methods=['GET'])
@validate_access
def config_bmcsetup(**kwargs):
    bmcsetup = False
    bmcsetupname = False
    if "access" in kwargs:
        access = "admin"
        bmcsetup = True
    else:
        bmcsetupname = False
    if bmcsetup:
        logger.info("List Of BMC Setup is: {}.".format(bmcsetup))
        response = {"message": "List Of BMC Setup is: {}.".format(bmcsetup)}
        code = 200
    elif bmcsetupname:
        logger.info("BMC Setup Name is: {}.".format(bmcsetup))
        response = {"message": "BMC Setup Name is: {}.".format(bmcsetup)}
        code = 200
    else:
        logger.error("BMC Setup Is Not Exist.")
        response = {"message": "BMC Setup Is Not Exist."}
        code = 404
    return json.dumps(response), code


"""
Input - BMC Setup ID or Name
Process - Fetch The BMC Setup information.
Output - BMC Setup Information.
"""
@config_blueprint.route("/config/bmcsetup/<string:bmcname>", methods=['GET'])
@validate_access
def config_bmcsetup_get(bmcname=None, **kwargs):
    bmcsetup = False
    bmcsetupname = False
    if "access" in kwargs:
        access = "admin"
        bmcsetup = True
    else:
        bmcsetupname = False
    if bmcsetup:
        logger.info("BMC Setup is: {}.".format(bmcsetup))
        response = {"message": "BMC Setup is: {}.".format(bmcsetup)}
        code = 200
    elif bmcsetupname:
        logger.info("BMC Setup Name is: {}.".format(bmcsetup))
        response = {"message": "BMC Setup Name is: {}.".format(bmcsetup)}
        code = 200
    else:
        logger.error("BMC Setup Is Not Exist.")
        response = {"message": "BMC Setup Is Not Exist."}
        code = 404
    return json.dumps(response), code


"""
Input - BMC Setup ID or Name
Process - Create or Update BMC Setup information.
Output - Success or Failure.
"""
@config_blueprint.route("/config/bmcsetup/<string:bmcname>", methods=['POST'])
@token_required
def config_bmcsetup_post(bmcname=None):
    create = True
    update = False
    if create:
        logger.info("BMC Setup {} Created Successfully.".format(bmcname))
        response = {"message": "BMC Setup {} Created Successfully.".format(bmcname)}
        code = 201
    elif update:
        logger.info("BMC Setup {} Updated Successfully.".format(bmcname))
        response = {"message": "BMC Setup {} Updated Successfully.".format(bmcname)}
        code = 200
    else:
        logger.error("BMC Setup Is Not Exist.")
        response = {"message": "BMC Setup Is Not Exist."}
        code = 404
    return json.dumps(response), code


"""
Input - BMC Setup ID or Name
Process - Fetch BMC Setup and Credentials.
Output - BMC Name And Credentials.
"""
@config_blueprint.route("/config/bmcsetup/<string:bmcname>/credentials", methods=['GET'])
@validate_access
def config_bmcsetup_credentials_get(bmcname=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
        bmcsetup = True
        if bmcsetup:
            logger.info("BMC Setup Name and Credentials is: {}".format(bmcsetup))
            response = {"message": "BMC Setup Name and Credentials is: {}".format(bmcsetup)}
            code = 200
        else:
            logger.error("BMC Setup Is Not Exist.")
            response = {"message": "BMC Setup Is Not Exist."}
            code = 404
    else:
        logger.error("Need a Valid Token to Perform this action.")
        response = {"message": "Need a Valid Token to Perform this action."}
        code = 401
    return json.dumps(response), code


"""
Input - BMC Setup ID or Name
Process - Update The BMC Setup Credentials.
Output - Success or Failure.
"""
@config_blueprint.route("/config/bmcsetup/<string:bmcname>/credentials", methods=['POST'])
@token_required
def config_bmcsetup_credentials_post(bmcname=None):
    update = True
    if update:
        logger.info("BMC Setup Credentials Updated Successfully.")
        response = {"message": "BMC Setup Credentials Updated Successfully."}
        code = 200
    else:
        logger.error("BMC Setup Name is Missing.")
        response = {"message": "BMC Setup Name is Missing."}
        code = 404
    return json.dumps(response), code


"""
Input - BMC Setup ID or Name
Process - Delete The BMC Setup Credentials.
Output - Success or Failure.
"""
@config_blueprint.route("/config/bmcsetup/<string:bmcname>/remove", methods=['GET'])
@validate_access
def config_bmcsetup_remove(bmcname=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
        remove = True
        if remove:
            logger.info("BMC Setup {} Removed Successfully.".format(bmcname))
            response = {"message": "BMC Setup {} Removed Successfully.".format(bmcname)}
            code = 200
        else:
            logger.error("BMC Setup Name is Missing.")
            response = {"message": "BMC Setup Name is Missing."}
            code = 404
    else:
        logger.error("Need a Valid Token to Perform this action.")
        response = {"message": "Need a Valid Token to Perform this action."}
        code = 401
    return json.dumps(response), code

######################################################## Switch Configuration #############################################################
"""
Input - None
Process - Fetch The List Of Switches.
Output - Switches.
"""
@config_blueprint.route("/config/switch", methods=['GET'])
@token_required
def config_switch():
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


"""
Input - Switch ID or Name
Process - Fetch The Switch Information.
Output - Switch Details.
"""
@config_blueprint.route("/config/switch/<string:switch>", methods=['GET'])
@token_required
def config_switch_get(switch=None):
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


"""
Input - Switch ID or Name
Process - Fetch The Switch Information.
Output - Switch Details.
"""
@config_blueprint.route("/config/switch/<string:switch>", methods=['POST'])
# @token_required
def config_switch_post(switch=None):
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
        if COLUMNCHECK:
            if CREATE:
                if 'ipaddress' in DATA:
                    IPRECORD = Database().get_record(None, 'ipaddress', ' WHERE `ipaddress` = "{}";'.format(DATA['ipaddress']))
                    if IPRECORD:
                        RESPONSE = {'message': 'Bad Request; IP Address Already Exist in The Database.'}
                        ACCESSCODE = 400
                        return json.dumps(RESPONSE), ACCESSCODE
                    else:
                        SUBNET = Helper().get_subnet(DATA['ipaddress'])
                        row = [
                                {"column": 'ipaddress', "value": DATA['ipaddress']},
                                {"column": 'network', "value": DATA['network']},
                                {"column": 'subnet', "value": SUBNET}
                                ]
                        result = Database().insert('ipaddress', row)
                        SUBNETRECORD = Database().get_record(None, 'ipaddress', ' WHERE `ipaddress` = "{}";'.format(DATA['ipaddress']))
                        DATA['ipaddress'] = SUBNETRECORD[0]['id']
                row = []
                for KEY, VALUE in DATA.items():
                    row.append({"column": KEY, "value": VALUE})
                result = Database().insert('switch', row)
                RESPONSE = {'message': 'Switch Created Successfully.'}
                ACCESSCODE = 204
            if UPDATE:
                if 'ipaddress' in DATA:
                    IPRECORD = Database().get_record(None, 'ipaddress', ' WHERE `ipaddress` = "{}";'.format(DATA['ipaddress']))
                    if IPRECORD:
                        RESPONSE = {'message': 'Bad Request; IP Address Already Exist in The Database.'}
                        ACCESSCODE = 400
                        return json.dumps(RESPONSE), ACCESSCODE
                    else:
                        SUBNET = Helper().get_subnet(DATA['ipaddress'])
                        row = [
                                {"column": 'ipaddress', "value": DATA['ipaddress']},
                                {"column": 'network', "value": DATA['network']},
                                {"column": 'subnet', "value": SUBNET}
                                ]
                        result = Database().insert('ipaddress', row)
                        SUBNETRECORD = Database().get_record(None, 'ipaddress', ' WHERE `ipaddress` = "{}";'.format(DATA['ipaddress']))
                        DATA['ipaddress'] = SUBNETRECORD[0]['id']
                row = []
                for KEY, VALUE in DATA.items():
                    row.append({"column": KEY, "value": VALUE})
                    where = [{"column": "id", "value": SWITCHID}]
                result = Database().update('switch', row, where)
                RESPONSE = {'message': 'Switch Updated Successfully.'}
                ACCESSCODE = 204
        else:
            RESPONSE = {'message': 'Bad Request; Columns are Incorrect.'}
            ACCESSCODE = 400
            return json.dumps(RESPONSE), ACCESSCODE
    else:
        RESPONSE = {'message': 'Bad Request; Did not received Data.'}
        ACCESSCODE = 400
        return json.dumps(RESPONSE), ACCESSCODE

    ACCESSCODE = 200
    return json.dumps(DATA), ACCESSCODE












    #     DATA = REQUEST['config']['switch'][switch]
    #     if 'readcommunity' in DATA:
    #         DATA['read'] = DATA['readcommunity']
    #         del DATA['readcommunity']
    #     if 'rwcommunity' in DATA:
    #         DATA['rw'] = DATA['rwcommunity']
    #         del DATA['rwcommunity']
    #     if 'comment' in DATA:
    #         DATA['comments'] = DATA['comment']
    #         del DATA['comment']
    #     if 'newswitchname' in DATA:
    #         UPDATE = True
    #         DATA['name'] = DATA['newswitchname']
    #         DATA['action'] = 'update'
    #         del DATA['newswitchname']
    #     elif 'network' in DATA and 'ipaddress' in DATA and 'newswitchname' not in DATA:
    #         CREATE = True
    #     else:
    #         UPDATE = True
    #         DATA['action'] = 'update'
    # if CREATE:
    #     if 'ipaddress' in DATA:
    #         IPADDR = DATA['ipaddress']
    #         IPRECORD = Database().get_record(None, 'ipaddress', f' WHERE `ipaddress` = "{IPADDR}";')
    #         if IPRECORD:
    #             DATA['ipaddress'] = IPRECORD[0]['id']
    #         else:
    #             row.append({"column": 'ipaddress', "value": IPADDR})
    #             result = Database().insert('ipaddress', row)
    #             ### ---------------------->> TODO --------- Last Inset ID With Pyodbc
    #             DATA['ipaddress'] = result
    #     for KEY, VALUE in DATA.items():
    #         row.append({"column": KEY, "value": VALUE})
    #     result = Database().insert('switch', row)
    #     logger.info("Switch Created Successfully")
    #     ACCESSCODE = 204
    #     RESPONSE = {'message': 'Created Successfully.'}
    # elif UPDATE:
    #     if 'ipaddress' in DATA:
    #         IPADDR = DATA['ipaddress']
    #         IPRECORD = Database().get_record(None, 'ipaddress', f' WHERE `ipaddress` = "{IPADDR}";')
    #         if IPRECORD:
    #             DATA['ipaddress'] = IPRECORD[0]['id']
    #         else:
    #             row.append({"column": 'ipaddress', "value": IPADDR})
    #             result = Database().insert('ipaddress', row)
    #             ### ---------------------->> TODO --------- Last Inset ID With Pyodbc
    #             DATA['ipaddress'] = result
    #     for KEY, VALUE in DATA.items():
    #         row.append({"column": KEY, "value": VALUE})
    #     where = [{"column": "name", "value": DATA['name']}]
    #     result = Database().update('switch', row, where)
    #     logger.info("Switch Created Successfully")
    #     ACCESSCODE = 204
    #     RESPONSE = {'message': 'Updated Successfully.'}
    # else:
    #     logger.error('No Switch is Avaiable.')
    #     RESPONSE = {'message': 'No Switch is Avaiable.'}
    #     ACCESSCODE = 404
    # return json.dumps(RESPONSE), ACCESSCODE

"""
Input - Switch ID or Name
Process - Delete The Switch.
Output - Success or Failure.
"""
@config_blueprint.route("/config/switch/<string:switch>/_clone", methods=['GET'])
@validate_access
def config_switch_clone(switch=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
        remove = True
        if remove:
            logger.info("Switch () Is Deleted Successfully.".format(switch))
            response = {"message": "Switch () Is Deleted Successfully.".format(switch)}
            code = 200
        else:
            logger.error("Switch {} Is Not Exist.".format(switch))
            response = {"message": "Switch {} Is Not Exist.".format(switch)}
            code = 404
    else:
        logger.error("Need a Valid Token to Perform this action.")
        response = {"message": "Need a Valid Token to Perform this action."}
        code = 401
    return json.dumps(response), code


"""
Input - Switch ID or Name
Process - Delete The Switch.
Output - Success or Failure.
"""
@config_blueprint.route("/config/switch/<string:switch>/remove", methods=['GET'])
@validate_access
def config_switch_remove(switch=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
        remove = True
        if remove:
            logger.info("Switch () Is Deleted Successfully.".format(switch))
            response = {"message": "Switch () Is Deleted Successfully.".format(switch)}
            code = 200
        else:
            logger.error("Switch {} Is Not Exist.".format(switch))
            response = {"message": "Switch {} Is Not Exist.".format(switch)}
            code = 404
    else:
        logger.error("Need a Valid Token to Perform this action.")
        response = {"message": "Need a Valid Token to Perform this action."}
        code = 401
    return json.dumps(response), code
    
"""
Input - Device ID or Name
Process - Fetch The List Of Devices.
Output - Devices.
"""
@config_blueprint.route("/config/otherdev/<string:device>", methods=['GET'])
def config_otherdev_get(device=None):
    devicedetails = True
    if devicedetails:
        logger.info("Other Device List is: {}".format(str(devicedetails)))
        response = {"message": "Other Device List is: {}".format(str(devicedetails))}
        code = 200
    else:
        logger.error("Device {} Is Not Exist.".format(switch))
        response = {"message": "Device {} Is Not Exist.".format(switch)}
        code = 404
    return json.dumps(response), code


"""
Input - Device ID or Name
Process - Delete The Other Device.
Output - Success Or Failure.
"""
@config_blueprint.route("/config/otherdev/<string:device>/remove", methods=['GET'])
@validate_access
def config_otherdev_remove(device=None, **kwargs):
    if "access" in kwargs:
        access = "admin"
        remove = True
        if remove:
            logger.info("Device () Is Deleted Successfully.".format(device))
            response = {"message": "Device () Is Deleted Successfully.".format(device)}
            code = 200
        else:
            logger.error("Device {} Is Not Exist.".format(device))
            response = {"message": "Device {} Is Not Exist.".format(device)}
            code = 404
    else:
        logger.error("Need a Valid Token to Perform this action.")
        response = {"message": "Need a Valid Token to Perform this action."}
        code = 401
    return json.dumps(response), code