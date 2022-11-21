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