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
from utils.status import Status
from utils.service import Service
from utils.queue import Queue
from utils.filter import Filter

LOGGER = Log.get_logger()
config_blueprint = Blueprint('config', __name__)

############################# Node configuration #############################

# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@config_blueprint.route('/config/node', methods=['GET'])
###@token_required
def config_node():
    """
    Input - None
    Output - Return the list of nodes.
    """
    # ---------------------------- NOTE NOTE NOTE ---------------------------
    # we collect all needed info from all tables at once and use dicts to collect data/info
    # A join is not really suitable as there are too many permutations in where the below
    # is way more efficient. -Antoine
    # -----------------------------------------------------------------------
    nodes = Database().get_record(None, 'node', None)
    groups = Database().get_record(None, 'group', None)
    osimages = Database().get_record(None, 'osimage', None)
    switches = Database().get_record(None, 'switch', None)
    bmcsetups = Database().get_record(None, 'bmcsetup', None)
    group=Helper().convert_list_to_dict(groups,'id')
    LOGGER.info("stop")
    osimage=Helper().convert_list_to_dict(osimages,'id')
    switch=Helper().convert_list_to_dict(switches,'id')
    bmcsetup=Helper().convert_list_to_dict(bmcsetups,'id')
    if nodes:
        items={
           'prescript':'<empty>',
           'partscript':'<empty>',
           'postscript':'<empty>',
           'setupbmc':False,
           'netboot':False,
           'localinstall':False,
           'bootmenu':False,
           'provision_method':'torrent',
           'provision_fallback':'http',
           'provision_interface':'BOOTIF'}

        response = {'config': {'node': {} }}
        for node in nodes:
            node_name = node['name']
            nodeid = node['id']

            groupid={}
            if 'groupid' in node and node['groupid'] in group.keys():
                node['group']=group[node['groupid']]['name']
                groupid=node['groupid']
                if node['osimageid']:
                    node['osimage']='!!Invalid!!'
                    if node['osimageid'] in osimage.keys():
                        node['osimage']=osimage[node['osimageid']]['name'] or None
                elif 'osimageid' in group[groupid] and group[groupid]['osimageid'] in osimage.keys():
                    node['osimage']=osimage[group[groupid]['osimageid']]['name'] or None
                else:
                    node['osimage']=None

                if node['bmcsetupid']: 
                    node['bmcsetup']='!!Invalid!!'
                    if node['bmcsetupid'] in bmcsetup.keys():
                        node['bmcsetup']=bmcsetup[node['bmcsetupid']]['name'] or None
                elif 'bmcsetupid' in group[groupid] and group[groupid]['bmcsetupid'] in bmcsetup.keys():
                    node['bmcsetup']=bmcsetup[group[groupid]['bmcsetupid']]['name'] or None
                else:
                    node['bmcsetup']=None
            else:
                node['group']='!!Invalid!!'

            for item in items:
                if groupid and item in group[groupid]:
                    node[item]=str(node[item]) or str(group[groupid][item]) or items[item]
                else:
                    node[item]=str(node[item]) or items[item]

            node['switch']=None
            if node['switchid']:
                node['switch']='!!Invalid!!'
                if node['switchid'] in switch.keys():
                    node['switch']=switch[node['switchid']]['name'] or None

            node['tpm_present']=False
            if node['tpm_uuid'] or node['tpm_sha256'] or node['tpm_pubkey']:
                node['tpm_present']=True

            del node['id']
            del node['bmcsetupid']
            del node['groupid']
            del node['osimageid']
            del node['switchid']

            node['bootmenu'] = Helper().make_bool(node['bootmenu'])
            node['localboot'] = Helper().make_bool(node['localboot'])
            node['localinstall'] = Helper().make_bool(node['localinstall'])
            node['netboot'] = Helper().make_bool(node['netboot'])
            node['service'] = Helper().make_bool(node['service'])
            node['setupbmc'] = Helper().make_bool(node['setupbmc'])
            node_interface = Database().get_record_join(['nodeinterface.interface','ipaddress.ipaddress','nodeinterface.macaddress','network.name as network','nodeinterface.options'], ['network.id=ipaddress.networkid','ipaddress.tablerefid=nodeinterface.id'],['tableref="nodeinterface"',f"nodeinterface.nodeid='{nodeid}'"])
            if node_interface:
                node['interfaces'] = []
                for interface in node_interface:
                    interface['options']=interface['options'] or ""
                    node['interfaces'].append(interface)
            response['config']['node'][node_name] = node
        LOGGER.info('Provided list of all nodes.')
        access_code = 200
    else:
        LOGGER.error('No nodes are available.')
        response = {'message': 'No nodes are available.'}
        access_code = 404
 
    return json.dumps(response), access_code


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
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
                                           'group.provision_method AS group_provision_method',
                                           'group.provision_fallback AS group_provision_fallback',
                                           'group.provision_interface AS group_provision_interface'], ['group.id=node.groupid','osimage.id=group.osimageid'],f"node.name='{name}'")
    if nodefull:
        nodes[0].update(nodefull[0])
    node=nodes[0]
    if node:
        response = {'config': {'node': {} }}
        nodename = node['name']
        nodeid = node['id']

        if node['bmcsetupid']:
            node['bmcsetup'] = Database().getname_byid('bmcsetup', node['bmcsetupid']) or '!!Invalid!!'
        elif 'group_bmcsetupid' in node and node['group_bmcsetupid']:
            node['bmcsetup']= Database().getname_byid('bmcsetup', node['group_bmcsetupid']) + f" ({node['group']})"
        if 'group_bmcsetupid' in node:
            del node['group_bmcsetupid']

        if node['osimageid']:
            node['osimage'] = Database().getname_byid('osimage', node['osimageid']) or '!!Invalid!!'
        elif 'group_osimage' in node and node['group_osimage']:
            node['osimage']=node['group_osimage']+f" ({node['group']})"
        if 'group_osimage' in node:
            del node['group_osimage']

        if node['switchid']:
            node['switch'] = Database().getname_byid('switch', node['switchid'])

        if not node['groupid']:
            node['group']='!!Invalid!!'

        # below section shows what's configured for the node, or the group, or a default fallback

        items={
           'prescript':'<empty>',
           'partscript':'<empty>',
           'postscript':'<empty>',
           'setupbmc':False,
           'netboot':False,
           'localinstall':False,
           'bootmenu':False,
           'provision_method':'torrent',
           'provision_fallback':'http',
           'provision_interface':'BOOTIF'}

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

        node['interfaces'] = []

        node_interface = Database().get_record_join(['nodeinterface.interface','ipaddress.ipaddress','nodeinterface.macaddress','network.name as network','nodeinterface.options'], ['network.id=ipaddress.networkid','ipaddress.tablerefid=nodeinterface.id'],['tableref="nodeinterface"',f"nodeinterface.nodeid='{nodeid}'"])
        if node_interface:
            for interface in node_interface:
                interfacename,*_ = (node['provision_interface'].split(' ')+[None]) # we skim off parts that we added for clarity in above section (e.g. (default)). also works if there's no additional info
                if interface['interface'] == interfacename and interface['network']: # if it is my prov interf then it will get that domain as a FQDN.
                    node['hostname'] = nodename + '.' + interface['network']
                interface['options'] = interface['options'] or ""
                node['interfaces'].append(interface)

#        Commented out since we do not need it but i left it as we _might_ use it one day
#        group_interface = Database().get_record_join(['groupinterface.interface','network.name as network'], ['network.id=groupinterface.networkid','groupinterface.groupid=node.groupid'],[f"node.id='{nodeid}'"])
#        if group_interface:
#            for interface in group_interface:
#                add_if=True
#                for check_interface in node['interfaces']:
#                    if check_interface['interface'] == interface['interface']:
#                        # the node has the same interface so we ditch the group one
#                        add_if=False
#                        break
#                if add_if:
#                    interfacename,*_ = (node['provision_interface'].split(' ')+[None]) # we skim off parts that we added for clarity in above section (e.g. (default)). also works if there's no additional info
#                    if interface['interface'] == interfacename and interface['network']: # if it is my prov interf then it will get that domain as a FQDN.
#                        node['hostname'] = nodename + '.' + interface['network'] 
#                    interface['interface'] += f" ({node['group']})"
#                    node['interfaces'].append(interface)

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
    items={ # minimal required items with defaults
       'setupbmc':False,
       'netboot':False,
       'localinstall':False,
       'bootmenu':False,
       'service':False,
       'localboot':False
    }
    create, update = False, False

    if Helper().check_json(request.data):
        request_data = Filter().validate_input(request.get_json(force=True))
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
        name = name.replace('_','-')
        node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if node:
            nodeid = node[0]['id']
            if 'newnodename' in data:  # is mentioned as newhostname in design documents!
                nodename_new = data['newnodename'].replace('_','-')
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
        else:
            if 'newnodename' in data:
                response = {'message': f'{nodename_new} is not allowed while creating a new node.'}
                access_code = 400
                return json.dumps(response), access_code
            create = True

        data['name'] = data['name'].replace('_','-')

        for item in items:
            if item in data: 
                data[item] = data[item] or items[item]
                if isinstance(items[item], bool):
                    data[item]=str(Helper().make_boolnum(data[item]))
            else:
                data[item] = items[item]
                if isinstance(items[item], bool):
                    data[item]=str(Helper().make_boolnum(data[item]))
            if (not data[item]) and (item not in items):
                del data[item]

        # True means: cannot be empty if supplied. False means: can only be empty or correct
        checks={'bmcsetup':False,'group':True,'osimage':False,'switch':False}
        for check in checks.keys():
            if check in data:
                check_name = data[check]
                if data[check] == "" and checks[check] is False:
                    data[check+'id']=""
                else:
                    data[check+'id'] = Database().getid_byname(check, check_name)
                    if (not data[check+'id']):
                        access_code = 400
                        response = {'message': f'{check} {check_name} is not known or valid.'}
                        return json.dumps(response), access_code
                del data[check]

        interfaces=None
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
                if nodeid and 'groupid' in data and data['groupid']:
                    # ----> GROUP interface. WIP. pending
                    group_interfaces = Database().get_record_join(['groupinterface.interface','network.name as network','groupinterface.options'], ['network.id=groupinterface.networkid'], [f"groupinterface.groupid={data['groupid']}"])
                    if group_interfaces:
                        for group_interface in group_interfaces:
                            result,mesg = Config().node_interface_config(nodeid,group_interface['interface'],None,group_interface['options'])
                            if result:
                                ips=[]
                                avail=None
                                network = Database().get_record_join(['ipaddress.ipaddress','ipaddress.networkid as networkid','network.network','network.subnet'], ['network.id=ipaddress.networkid'], [f"network.name='{group_interface['network']}'"])
                                if network:
                                    for ip in network:
                                        ips.append(ip['ipaddress'])
#                                    ## ---> we do not ping nodes as it will take time if we add bulk nodes, it'll take 1s per node.
#                                    ret=0
#                                    max=5 # we try to ping for X ips, if none of these are free, something else is going on (read: rogue devices)....
#                                    while(max>0 and ret!=1):
#                                        avail=Helper().get_available_ip(network[0]['network'],network[0]['subnet'],ips)
#                                        ips.append(avail)
#                                        output,ret=Helper().runcommand(f"ping -w1 -c1 {avail}", True, 3)
#                                        max-=1
    
                                    avail=Helper().get_available_ip(network[0]['network'],network[0]['subnet'],ips)
                                    if avail:
                                        ipaddress=avail
                                        result,mesg = Config().node_interface_ipaddress_config(nodeid,group_interface['interface'],ipaddress,group_interface['network'])
            if interfaces:
                access_code = 204
                for interface in interfaces:
                    # Antoine
                    interface_name = interface['interface']
                    macaddress,network,options=None,None,None
                    if 'macaddress' in interface.keys():
                        macaddress=interface['macaddress']
                    if 'options' in interface.keys():
                        options=interface['options']
                    result,mesg = Config().node_interface_config(nodeid,interface_name,macaddress,options)
                    if result and 'ipaddress' in interface.keys():
                        ipaddress=interface['ipaddress']
                        if 'network' in interface.keys():
                            network=interface['network']
                        result,mesg = Config().node_interface_ipaddress_config(nodeid,interface_name,ipaddress,network)
                        
                    if result is False:
                        response = {'message': f"{mesg}"}
                        access_code = 500
                        return json.dumps(response), access_code

 
            Service().queue('dhcp','restart')
            Service().queue('dns','restart')
            # below might look as redundant but is added to prevent a possible race condition when many nodes are added in a loop.
            # the below tasks ensures that even the last node will be included in dhcp/dns
            Queue().add_task_to_queue(f'dhcp:restart','housekeeper','__node_post__')
            Queue().add_task_to_queue(f'dns:restart','housekeeper','__node_post__')

        else:
            response = {'message': 'Bad Request; Columns are incorrect.'}
            access_code = 400
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
    return json.dumps(response), access_code



# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@config_blueprint.route('/config/node/<string:name>/_clone', methods=['POST'])
@token_required
def config_node_clone(name=None):
    """
    Input - Node name
    Process - Create or update the groups.
    Output - Node information.
    """
    data = {}
    items={
       'setupbmc':False,
       'netboot':False,
       'localinstall':False,
       'bootmenu':False,
       'service':False,
       'localboot':False
    }

    if Helper().check_json(request.data):
        request_data = Filter().validate_input(request.get_json(force=True))
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        if 'node' not in request_data['config'].keys():
            response = {'message': 'Bad Request.'}
            access_code = 400
            return json.dumps(response), access_code

        srcnodename=name
        newnodename=None
        data = request_data['config']['node'][name]
        name = name.replace('_','-')
        node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        if node:
            nodeid = node[0]['id']
            if 'newnodename' in data: 
                newnodename = data['newnodename'].replace('_','-')
                where = f' WHERE `name` = "{newnodename}"'
                newnode_check = Database().get_record(None, 'node', where)
                if newnode_check:
                    response = {'message': f'{newnodename} already present in database.'}
                    access_code = 400
                    return json.dumps(response), access_code
                else:
                    data['name'] = data['newnodename']
                    del data['newnodename']
            else:
                response = {'message': f'Bad Request; Destination node name not supplied.'}
                access_code = 400
                return json.dumps(response), access_code
        else:
            response = {'message': f'Bad Request; Source node {name} does not exist.'}
            access_code = 400
            return json.dumps(response), access_code

        data['name'] = data['name'].replace('_','-')

        del node[0]['id']
        del node[0]['status']
        for item in node[0]:
            if item in data:  # we copy from another node unless we supply
                data[item] = data[item] or node[0][item] or None
            else:
                data[item] = node[0][item] or None
            if item in items:
                data[item] = data[item] or items[item]
            if (not data[item]) and (item not in items):
                del data[item]
            elif item in items and isinstance(items[item], bool):
                data[item]=str(Helper().make_boolnum(data[item]))

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

        interfaces=None
        if 'interfaces' in data:
            interfaces = data['interfaces']
            del data['interfaces']


        node_columns = Database().get_columns('node')
        columns_check = Helper().checkin_list(data, node_columns)
        if columns_check:
            newnodeid=None
            row = Helper().make_rows(data)
            newnodeid = Database().insert('node', row)
            if not newnodeid:
                response = {'message': f'Node {newnodename} could not be created due to possible property clash.'}
                access_code = 500
                return json.dumps(response), access_code

            response = {'message': f'Node {name} created successfully.'}
            access_code = 201

            node_interfaces = Database().get_record_join(['nodeinterface.interface','ipaddress.ipaddress','nodeinterface.macaddress','network.name as network','nodeinterface.options'], ['network.id=ipaddress.networkid','ipaddress.tablerefid=nodeinterface.id'],['tableref="nodeinterface"',f"nodeinterface.nodeid='{nodeid}'"])

            if interfaces:
                for interface in interfaces:
                    # Antoine
                    interface_name = interface['interface']
                    for node_interface in node_interfaces:
                        # delete interfaces we overwrite
                        if interface_name == node_interface['interface']:
                            del node_interfaces[node_interface] 
                    macaddress,network=None,None
                    if 'macaddress' in interface.keys():
                        macaddress=interface['macaddress']
                    if 'options' in interface.keys():
                        options=interface['options']
                    result,mesg = Config().node_interface_config(newnodeid,interface_name,macaddress,options)
                    if result and 'ipaddress' in interface.keys():
                        ipaddress=interface['ipaddress']
                        if 'network' in interface.keys():
                            network=interface['network']
                        result,mesg = Config().node_interface_ipaddress_config(nodeid,interface_name,ipaddress,network)
                        
                    if result is False:
                        response = {'message': f"{mesg}"}
                        access_code = 500
                        return json.dumps(response), access_code

            for node_interface in node_interfaces:       
                interface_name = node_interface['interface']
                interface_options=node_interface['options']
                result,mesg = Config().node_interface_config(newnodeid,interface_name,None,interface_options)
                if result and 'ipaddress' in node_interface.keys():
                    if 'network' in node_interface.keys():
                        networkname=node_interface['network']
                        ips=[]
                        avail=None
                        network = Database().get_record_join(['ipaddress.ipaddress','ipaddress.networkid as networkid','network.network','network.subnet'], ['network.id=ipaddress.networkid'], [f"network.name='{networkname}'"])
                        if network:
                            for ip in network:
                                ips.append(ip['ipaddress'])
                            ret=0
                            max=5 # we try to ping for X ips, if none of these are free, something else is going on (read: rogue devices)....
                            while(max>0 and ret!=1):
                                avail=Helper().get_available_ip(network[0]['network'],network[0]['subnet'],ips)
                                ips.append(avail)
                                output,ret=Helper().runcommand(f"ping -w1 -c1 {avail}", True, 3)
                                max-=1
    
                            if avail:
                                ipaddress=avail
                                result,mesg = Config().node_interface_ipaddress_config(newnodeid,interface_name,ipaddress,networkname)
                    
                                if result is False:
                                    response = {'message': f"{mesg}"}
                                    access_code = 500
                                    return json.dumps(response), access_code

            #Service().queue('dhcp','restart') # do we need dhcp restart? MAC is wiped on new NIC so no real need i guess
            Service().queue('dns','restart')

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
        # ----
        Service().queue('dns','restart')
        Service().queue('dhcp','restart')
        # below might look as redundant but is added to prevent a possible race condition when many nodes are added in a loop.
        # the below tasks ensures that even the last node will be included in dhcp/dns
        Queue().add_task_to_queue(f'dhcp:restart','housekeeper','__node_delete__')
        Queue().add_task_to_queue(f'dns:restart','housekeeper','__node_delete__')
        # ----
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
        node_interfaces = Database().get_record_join(['network.name as network','nodeinterface.macaddress','nodeinterface.interface','ipaddress.ipaddress','nodeinterface.options'], ['ipaddress.tablerefid=nodeinterface.id','network.id=ipaddress.networkid'], ['tableref="nodeinterface"',f"nodeinterface.nodeid='{nodeid}'"])
        if node_interfaces:
            my_interface = []
            for interface in node_interfaces:
                interface['options']=interface['options'] or ""
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
        request_data = Filter().validate_input(request.get_json(force=True))
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
                    macaddress,network,options=None,None,None
                    if 'macaddress' in interface.keys():
                        macaddress=interface['macaddress']
                    if 'options' in interface.keys():
                        options=interface['options']
                    result,mesg = Config().node_interface_config(nodeid,interface_name,macaddress,options)
                    if result and 'ipaddress' in interface.keys():
                        ipaddress=interface['ipaddress']
                        if 'network' in interface.keys():
                            network=interface['network']
                        result,mesg = Config().node_interface_ipaddress_config(nodeid,interface_name,ipaddress,network,options)

                    if result is False:
                        response = {'message': f"{mesg}"}
                        access_code = 500
                    else:
                        Service().queue('dhcp','restart')
                        Service().queue('dns','restart')
                        # below might look as redundant but is added to prevent a possible race condition when many nodes are added in a loop.
                        # the below tasks ensures that even the last node will be included in dhcp/dns
                        Queue().add_task_to_queue(f'dhcp:restart','housekeeper','__node_interface_post__')
                        Queue().add_task_to_queue(f'dns:restart','housekeeper','__node_interface_post__')
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
        node_interfaces = Database().get_record_join(['network.name as network','nodeinterface.macaddress','nodeinterface.interface','ipaddress.ipaddress','nodeinterface.options'], ['ipaddress.tablerefid=nodeinterface.id','network.id=ipaddress.networkid'], ['tableref="nodeinterface"',f"nodeinterface.nodeid='{nodeid}'"])
        if node_interfaces:
            my_interface = []
            for interface in node_interfaces:
                interface['options']=interface['options'] or ""
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
            # ---
            Service().queue('dhcp','restart')
            Service().queue('dns','restart')
            # below might look as redundant but is added to prevent a possible race condition when many nodes are added in a loop.
            # the below tasks ensures that even the last node will be included in dhcp/dns
            Queue().add_task_to_queue(f'dhcp:restart','housekeeper','__node_interface_delete__')
            Queue().add_task_to_queue(f'dns:restart','housekeeper','__node_interface_delete__')
            # ---
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

# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
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
            grp_interface = Database().get_record_join(['groupinterface.interface','network.name as network','groupinterface.options'], ['network.id=groupinterface.networkid'], [f"groupid = '{grpid}'"])
            if grp_interface:
                grp['interfaces'] = []
                for ifx in grp_interface:
                    ifx['options']=ifx['options'] or ""
                    grp['interfaces'].append(ifx)
            del grp['id']
            grp['setupbmc'] = Helper().make_bool(grp['setupbmc'])
            grp['netboot'] = Helper().make_bool(grp['netboot'])
            grp['localinstall'] = Helper().make_bool(grp['localinstall'])
            grp['bootmenu'] = Helper().make_bool(grp['bootmenu'])
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


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@config_blueprint.route("/config/group/<string:name>", methods=['GET'])
###@token_required
def config_group_get(name=None):
    """
    Input - Group Name
    Process - Fetch the Group information.
    Output - Group Info.
    """
    # things we have to set for a group
    items={
       'prescript':'<empty>',
       'partscript':'<empty>',
       'postscript':'<empty>',
       'setupbmc':False,
       'netboot':False,
       'localinstall':False,
       'bootmenu':False,
       'provision_interface':'BOOTIF'
    }

    groups = Database().get_record(None, 'group', f' WHERE name = "{name}"')
    if groups:
        response = {'config': {'group': {} }}
        for grp in groups:
            grpname = grp['name']
            grpid = grp['id']
            grp_interface = Database().get_record_join(['groupinterface.interface','network.name as network','groupinterface.options'], ['network.id=groupinterface.networkid'], [f"groupid = '{grpid}'"])
            if grp_interface:
                grp['interfaces'] = []
                for ifx in grp_interface:
                    ifx['options']=ifx['options'] or ""
                    grp['interfaces'].append(ifx)
            del grp['id']
            for item in items.keys():
                if item in grp:
                    if isinstance(items[item], bool):
                        grp[item]=str(Helper().make_bool(grp[item]))
                    grp[item] = grp[item] or str(items[item]+' (default)')
                else:
                    if isinstance(items[item], bool):
                        grp[item]=str(Helper().make_bool(grp[item]))
                    grp[item] = str(items[item]+' (default)')

#            grp['setupbmc'] = Helper().make_bool(grp['setupbmc'])
#            grp['netboot'] = Helper().make_bool(grp['netboot'])
#            grp['localinstall'] = Helper().make_bool(grp['localinstall'])
#            grp['bootmenu'] = Helper().make_bool(grp['bootmenu'])
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
@token_required
def config_group_post(name=None):
    """
    Input - Group ID or Name
    Process - Create Or Update The Groups.
    Output - Group Information.
    """
    data = {}
    # things we have to set for a group
    items={
       'prescript':'',
       'partscript':'',
       'postscript':'',
       'setupbmc':False,
       'netboot':False,
       'localinstall':False,
       'bootmenu':False,
       'provision_interface':'BOOTIF'
    }
    create, update = False, False

    if Helper().check_json(request.data):
        request_data = Filter().validate_input(request.get_json(force=True))
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
        else:
            if 'newgroupname' in data:
                response = {'message': f'{newgrpname} is not allwoed while creating a new group.'}
                access_code = 400
                return json.dumps(response), access_code
            create = True

        for item in items:
            if item in data:  # pending
                LOGGER.debug(f"{item} in data [{data[item]}]")
                data[item] = data[item]
            else:
                LOGGER.debug(f"{item} in other [{grp[0][item]}] or [{items[item]}]")
                data[item] = grp[0][item] or items[item]
            if isinstance(items[item], bool):
                data[item]=str(Helper().make_boolnum(data[item]))

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
        newinterface=None
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
                    ifname = ifx['interface']
                    grp_clause = f'groupid = "{grpid}"'
                    network_clause = f'networkid = "{network}"'
                    interface_clause = f'interface = "{ifname}"'
                    where = f' WHERE {grp_clause} AND {network_clause} AND {interface_clause}'
                    check_interface = Database().get_record(None, 'groupinterface', where)
                    if not check_interface:
                        row = Helper().make_rows(ifx)
                        result = Database().insert('groupinterface', row)
                        LOGGER.info(f'Interface created => {result} .')
                        ## below section takes care (in the background), the adding/renaming/deleting. for adding nextfree ip-s will be selected. time consuming therefor background
                        queue_id,queue_response = Queue().add_task_to_queue(f'add_interface_to_group_nodes:{name}:{ifname}','group_interface')
                        next_id = Queue().next_task_in_queue('group_interface')
                        if queue_id == next_id:
                            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                            executor.submit(Config().update_interface_on_group_nodes,name)
                            executor.shutdown(wait=False)
                            #Config().update_interface_on_group_nodes(name)

        else:
            response = {'message': 'Bad Request; Columns are incorrect.'}
            access_code = 400
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
    return json.dumps(response), access_code


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@config_blueprint.route("/config/group/<string:name>/_clone", methods=['POST'])
@token_required
def config_group_clone(name=None):
    """
    Input - Group ID or Name
    Process - Create Or Update The Groups.
    Output - Group Information.
    """
    data = {}
    # things we have to set for a group
    items={
       'prescript':'',
       'partscript':'',
       'postscript':'',
       'setupbmc':False,
       'netboot':False,
       'localinstall':False,
       'bootmenu':False,
    }

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
                newgroupname = data['newgroupname']
                where = f' WHERE `name` = "{newgroupname}"'
                checknewgrp = Database().get_record(None, 'group', where)
                if checknewgrp:
                    response = {'message': f'{newgroupname} Already present in database.'}
                    access_code = 400
                    return json.dumps(response), access_code
                data['name'] = data['newgroupname']
                del data['newgroupname']
            else:
                response = {'message': f'Bad Request; Destination group name not supplied.'}
                access_code = 400
                return json.dumps(response), access_code
        else:
            response = {'message': f'Bad Request; Source group {name} does not exist.'}
            access_code = 400
            return json.dumps(response), access_code

        del grp[0]['id']
        for item in grp[0]:
            if item in data:  # pending
                LOGGER.debug(f"{item} in data [{data[item]}] or grp [{grp[0][item]}]")
                data[item] = data[item] or grp[0][item] or None
            else:
                LOGGER.debug(f"{item} in other [{grp[0][item]}]")
                data[item] = grp[0][item] or None
            if item in items:
                data[item] = data[item] or items[item]
            if (not data[item]) and (item not in items):
                del data[item]
            elif item in items and isinstance(items[item], bool):
                data[item]=str(Helper().make_boolnum(data[item]))

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
        newinterface=None
        if 'interfaces' in data:
            newinterface = data['interfaces']
            del data['interfaces']

        grpcolumns = Database().get_columns('group')
        columncheck = Helper().checkin_list(data, grpcolumns)
        if columncheck:
            row = Helper().make_rows(data)
            newgroupid = Database().insert('group', row)
            if not newgroupid:
                response = {'message': f'Node {newgroupname} could not be created due to possible property clash.'}
                access_code = 500
                return json.dumps(response), access_code

            response = {'message': f'Group {name} created.'}
            access_code = 201

            grp_interfaces = Database().get_record_join(['groupinterface.interface','network.name as network','network.id as networkid','groupinterface.options'], ['network.id=groupinterface.networkid'], [f"groupid = '{grpid}'"])

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
                    ifname = ifx['interface']
                    for grp_ifx in grp_interfaces:
                        if grp_ifx['interface'] == ifname:
                            del group_interfaces[grp_ifx]
                    row = Helper().make_rows(ifx)
                    result = Database().insert('groupinterface', row)

            for grp_ifx in grp_interfaces:
                ifx={}
                ifx['networkid']=grp_ifx['networkid']
                ifx['interface']=grp_ifx['interface']
                ifx['options']=grp_ifx['options']
                ifx['groupid']=newgroupid
                row = Helper().make_rows(ifx)
                result = Database().insert('groupinterface', row)

        else:
            response = {'message': 'Bad Request; Columns are incorrect.'}
            access_code = 400
    else:
        response = {'message': 'Bad Request; Did not received data.'}
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
            grp_interface = Database().get_record_join(['groupinterface.interface','network.name as network'], ['network.id=groupinterface.networkid'], [f"groupid = '{groupid}'"])
            if grp_interface:
                grp_interfaces = []
                for ifx in grp_interface:
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


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
@config_blueprint.route("/config/group/<string:name>/interfaces", methods=['POST'])
@token_required
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
                    if (not 'network' in ifx) or (not 'interface' in ifx):
                        response = {'message': f'Bad Request; interface and/or network not specified.'}
                        access_code = 400
                        return json.dumps(response), access_code
                    network = Database().getid_byname('network', ifx['network'])
                    if network is None:
                        response = {'message': f'Bad Request; Network {network} not exist.'}
                        access_code = 400
                        return json.dumps(response), access_code
                    else:
                        ifx['networkid'] = network
                        ifx['groupid'] = grpid
                        del ifx['network']
                    interface = ifx['interface']
                    grp_clause = f'groupid = "{grpid}"'
                    network_clause = f'networkid = "{network}"'
                    interface_clause = f'interface = "{interface}"'
                    where = f' WHERE {grp_clause} AND {network_clause} AND {interface_clause}'
                    interface_check = Database().get_record(None, 'groupinterface', where)
                    if not interface_check:
                        row = Helper().make_rows(ifx)
                        Database().insert('groupinterface', row)
                    response = {'message': 'Interface updated.'}
                    access_code = 204
                    ## below section takes care (in the background), the adding/renaming/deleting. for adding nextfree ip-s will be selected. time consuming therefor background
                    queue_id,queue_response = Queue().add_task_to_queue(f'add_interface_to_group_nodes:{name}:{interface}','group_interface')
                    next_id = Queue().next_task_in_queue('group_interface')
                    if queue_id == next_id:
                        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                        executor.submit(Config().update_interface_on_group_nodes,name)
                        executor.shutdown(wait=False)
                        #Config().update_interface_on_group_nodes(name)
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
        where = f' WHERE `interface` = "{interface}" AND `groupid` = "{groupid}"'
        group_interface = Database().get_record(None, 'groupinterface', where)
        if group_interface:
            where = [{"column": "id", "value": group_interface[0]['id']}]
            Database().delete_row('groupinterface', where)
            ## below section takes care (in the background), the adding/renaming/deleting. for adding nextfree ip-s will be selected. time consuming therefor background
            queue_id,queue_response = Queue().add_task_to_queue(f'delete_interface_from_group_nodes:{name}:{interface}','group_interface')
            next_id = Queue().next_task_in_queue('group_interface')
            if queue_id == next_id:
#                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
#                executor.submit(Config().update_interface_on_group_nodes,name)
#                executor.shutdown(wait=False)
                Config().update_interface_on_group_nodes(name)
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



# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
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

    queue_id,queue_response = Queue().add_task_to_queue(f'pack_n_tar_osimage:{name}','osimage',request_id)
    if not queue_id:
        LOGGER.info(f"config_osimage_pack GET cannot get queue_id")
        response= {"message": f'OS image {name} pack queuing failed.'}
        return json.dumps(response), code
 
    if queue_response != "added": # this means we already have an equal request in the queue
        code=200
        response = {"message": f"osimage pack for {name} already queued", "request_id": queue_response}
        LOGGER.info(f"my repsonse [{response}]")
        return json.dumps(response), code

    LOGGER.info(f"config_osimage_pack GET added task to queue: {queue_id}")
    Status().add_message(request_id,"luna",f"queued pack osimage {name} with queue_id {queue_id}")

    next_id = Queue().next_task_in_queue('osimage')
    if queue_id == next_id:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        executor.submit(OsImage().pack_n_tar_mother,name,request_id)
        executor.shutdown(wait=False)

    # we should check after a few seconds if there is a status update for us.
    # if so, that means mother is taking care of things

    sleep(1)
    status = Database().get_record(None , 'status', f' WHERE request_id = "{request_id}"')
    if status:
        code=200
        response = {"message": f"osimage pack for {name} queued", "request_id": request_id}
    LOGGER.info(f"my response [{response}]")
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


# BELOW SEGMENT HAS BEEN TESTED AND CONFIRMED WORKING BY ANTOINE ON APRIL 3 2023
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
        if cluster[0]['createnode_ondemand']:
            cluster[0]['createnode_ondemand'] = True
        else:
            cluster[0]['createnode_ondemand'] = False
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
    items={
       'debug':False,
       'security':False,
       'createnode_ondemand':True
    }
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
                if 'ntp_server' in data and data['ntp_server']:
                    temp=data['ntp_server'];
                    temp=temp.replace(' ',',')
                    temp=temp.replace(',,',',')
                    data['ntp_server']=temp
                if 'nameserver_ip' in data and data['nameserver_ip']:
                    temp=data['nameserver_ip'];
                    temp=temp.replace(' ',',')
                    temp=temp.replace(',,',',')
                    data['nameserver_ip']=temp
                if 'forwardserver_ip' in data and data['forwardserver_ip']:
                    temp=data['forwardserver_ip'];
                    temp=temp.replace(' ',',')
                    temp=temp.replace(',,',',')
                    data['forwardserver_ip']=temp

                for item in items:
                    if item in data:
                        data[item] = data[item] or items[item]
                        if isinstance(items[item], bool):
                            data[item]=str(Helper().make_boolnum(data[item]))
                    else:
                        data[item] = items[item]
                        if isinstance(items[item], bool):
                            data[item]=str(Helper().make_boolnum(data[item]))
                    if (not data[item]) and (item not in items):
                        del data[item]

                where = [{"column": "id", "value": cluster[0]['id']}]
                row = Helper().make_rows(data)
                Database().update('cluster', row, where)
                Service().queue('dns','restart')
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
    return json.dumps(response), access_code


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
            #Antoine
            switch_ips = Database().get_record_join(['network.name as network','ipaddress.ipaddress'], ['ipaddress.tablerefid=switch.id','network.id=ipaddress.networkid'], ['tableref="switch"',f"tablerefid='{switch['id']}'"])
            del switch['id']
            response['config']['switch'][switchname] = switch
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
@token_required
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
        switch = switch.replace('_','-')
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
        data['name'] = data['name'].replace('_','-')

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
        else:
            Service().queue('dhcp','restart')
            Service().queue('dns','restart')
        return json.dumps(response), access_code

    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(data), access_code



@config_blueprint.route("/config/switch/<string:switch>/_clone", methods=['POST'])
@token_required
def config_switch_clone(switch=None):
    """
    Input - Switch ID or Name
    Process - Delete The Switch.
    Output - Success or Failure.
    """
    data = {}
    create = False
    srcswitch=None
    ipaddress,networkname = None,None
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['switch'][switch]
        srcswitch=data['name']
        if 'newswitchname' in data:
            data['name'] = data['newswitchname']
            newswitchname = data['newswitchname'].replace('_','-')
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
            ipaddress=data['ipaddress']
            del data['ipaddress']
        if 'network' in data:
            networkname=data['network']
            del data['network']

        data['name'] = data['name'].replace('_','-')
        switchcolumns = Database().get_columns('switch')
        columncheck = Helper().checkin_list(data, switchcolumns)
        if data:
            if columncheck:
                if create:
                    switch = Database().get_record(None, 'switch', f' WHERE `name` = "{srcswitch}"')
                    del switch[0]['id']
                    for key in switch[0]:
                        if key not in data:
                            data[key]=switch[0][key]

                    row = Helper().make_rows(data)
                    newswitchid=Database().insert('switch', row)
                    if not newswitchid:
                        response = {'message': 'Bad Request; switch not cloned due to clashing config.'}
                        access_code = 400
                        LOGGER.info(f"my response: {response}")
                        return json.dumps(response), access_code
   
                    access_code = 201
                    network=None
                    if networkname:
                        network = Database().get_record_join(['ipaddress.ipaddress','ipaddress.networkid as networkid','network.network','network.subnet'], ['network.id=ipaddress.networkid'], [f"network.name='{networkname}'"])
                    else:
                        network = Database().get_record_join(['ipaddress.ipaddress','ipaddress.networkid as networkid','network.name as networkname','network.network','network.subnet'],['network.id=ipaddress.networkid','ipaddress.tablerefid=switch.id'],[f'switch.name="{srcswitch}"','ipaddress.tableref="switch"'])
                        if network:
                            data['network'] = network[0]['networkname']
                            networkname=data['network']

                    if not ipaddress:
                        ips=[]
                        avail=None
                        if not network:
                            network = Database().get_record_join(['ipaddress.ipaddress','ipaddress.networkid as networkid','network.network','network.subnet'], ['network.id=ipaddress.networkid'], [f"network.name='{networkname}'"])
                            if network:
                                networkname = network[0]['networkname']
                        for ip in network:
                            ips.append(ip['ipaddress'])

                        if network:
                            ret=0
                            max=10 # we try to ping for 10 ips, if none of these are free, something else is going on (read: rogue devices)....
                            while(max>0 and ret!=1):
                                avail=Helper().get_available_ip(network[0]['network'],network[0]['subnet'],ips)
                                ips.append(avail)
                                output,ret=Helper().runcommand(f"ping -w1 -c1 {avail}", True, 3)
                                max-=1
    
                            if avail:
                                ipaddress=avail
                        else:
                            response = {'message': 'Bad Request; please supply network and ipaddress.'}
                            access_code = 400
                            LOGGER.info(f"my response: {response}")
                            return json.dumps(response), access_code

                    result,mesg=Config().device_ipaddress_config(newswitchid,'switch',ipaddress,networkname)

                    if result is False:
                        Database().delete_row('switch', [{"column": "id", "value": newswitchid}])  # roll back
                        access_code=400
                        response = {'message': f"{mesg}"}
                    else:
                        Service().queue('dhcp','restart')
                        Service().queue('dns','restart')
                        response = {'message': 'Switch created.'}

            else:
                response = {'message': 'Bad Request; Columns are incorrect.'}
                access_code = 400
                #return json.dumps(response), access_code
        else:
            response = {'message': 'Bad Request; Not enough information provided.'}
            access_code = 400
            #return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
        #return json.dumps(response), access_code

    LOGGER.info(f"my response: {response}")
    return json.dumps(data), access_code



@config_blueprint.route("/config/switch/<string:switch>/_delete", methods=['GET'])
@token_required
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
            #Antoine
            otherdev_ips = Database().get_record_join(['network.name as network','ipaddress.ipaddress'], ['ipaddress.tablerefid=otherdevices.id','network.id=ipaddress.networkid'], ['tableref="otherdevices"',f"tablerefid='{device['id']}'"])
            del device['id']
            response['config']['otherdev'][devicename] = device
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
@token_required
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
        device = device.replace('_','-')
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
        data['name'] = data['name'].replace('_','-')

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
        else:
            Service().queue('dhcp','restart')
            Service().queue('dns','restart')
        return json.dumps(response), access_code

    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(data), access_code



@config_blueprint.route("/config/otherdev/<string:device>/_clone", methods=['POST'])
@token_required
def config_otherdev_clone(device=None):
    """
    Input - Device ID or Name
    Output - Clone The Device.
    """
    data = {}
    create = False
    srcdevice=None
    ipaddress,networkname = None,None
    if Helper().check_json(request.data):
        request_data = request.get_json(force=True)
    else:
        response = {'message': 'Bad Request.'}
        access_code = 400
        return json.dumps(response), access_code
    if request_data:
        data = request_data['config']['otherdev'][device]
        srcdevice=data['name']
        if 'newotherdevname' in data:
            data['name'] = data['newotherdevname']
            newdevicename = data['newotherdevname'].replace('_','-')
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
            ipaddress=data['ipaddress']
            del data['ipaddress']
        if 'network' in data:
            networkname=data['network']
            del data['network']
        data['name'] = data['name'].replace('_','-')
        devicecolumns = Database().get_columns('otherdevices')
        columncheck = Helper().checkin_list(data, devicecolumns)

        if data:
            if columncheck:
                if create:
                    otherdevice = Database().get_record(None, 'otherdevices', f' WHERE `name` = "{srcdevice}"')
                    del otherdevice[0]['id']
                    for key in otherdevice[0]:
                        if key not in data:
                            data[key]=otherdevice[0][key]

                    row = Helper().make_rows(data)
                    newdeviceid=Database().insert('otherdevices', row)
                    if not newdeviceid:
                        response = {'message': 'Bad Request; device not cloned due to clashing config.'}
                        access_code = 400
                        LOGGER.info(f"my response: {response}")
                        return json.dumps(response), access_code
 
                    access_code = 201
                    network=None
                    if networkname:
                        network = Database().get_record_join(['ipaddress.ipaddress','ipaddress.networkid as networkid','network.network','network.subnet'], ['network.id=ipaddress.networkid'], [f"network.name='{networkname}'"])
                    else:
                        network = Database().get_record_join(['ipaddress.ipaddress','ipaddress.networkid as networkid','network.name as networkname','network.network','network.subnet'],['network.id=ipaddress.networkid','ipaddress.tablerefid=otherdevices.id'],[f'otherdevices.name="{srcdevice}"','ipaddress.tableref="otherdevices"'])
                        if network:
                            networkname = network[0]['networkname']

                    if not ipaddress:
                        ips=[]
                        avail=None
                        if not network:
                            network = Database().get_record_join(['ipaddress.ipaddress','ipaddress.networkid as networkid','network.network','network.subnet'], ['network.id=ipaddress.networkid'], [f"network.name='{networkname}'"])
                            if network:
                                networkname = network[0]['networkname']
                        for ip in network:
                            ips.append(ip['ipaddress'])

                        if network:
                            ret=0
                            max=10 # we try to ping for 10 ips, if none of these are free, something else is going on (read: rogue devices)....
                            while(max>0 and ret!=1):
                                avail=Helper().get_available_ip(network[0]['network'],network[0]['subnet'],ips)
                                ips.append(avail)
                                output,ret=Helper().runcommand(f"ping -w1 -c1 {avail}", True, 3)
                                max-=1
 
                            if avail:
                                ipaddress=avail
                        else:
                            response = {'message': 'Bad Request; please supply network and ipaddress.'}
                            access_code = 400
                            LOGGER.info(f"my response: {response}")
                            return json.dumps(response), access_code

                    result,mesg=Config().device_ipaddress_config(newdeviceid,'otherdevices',ipaddress,networkname)

                    if result is False:
                        Database().delete_row('otherdevices', [{"column": "id", "value": newdeviceid}])  # roll back
                        access_code=400
                        response = {'message': f"{mesg}"}
                    else:
                        Service().queue('dhcp','restart')
                        Service().queue('dns','restart')
                        response = {'message': 'Device created.'}

            else:
                response = {'message': 'Bad Request; Columns are incorrect.'}
                access_code = 400
                return json.dumps(response), access_code
        else:
            response = {'message': 'Bad Request; Not enough details to create the device.'}
            access_code = 400
            return json.dumps(response), access_code
    else:
        response = {'message': 'Bad Request; Did not received data.'}
        access_code = 400
        return json.dumps(response), access_code

    return json.dumps(data), access_code



@config_blueprint.route("/config/otherdev/<string:device>/_delete", methods=['GET'])
@token_required
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
@token_required
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
        if 'nameserver_ip' in data:
            nsipdetails = Helper().check_ip_range(data['nameserver_ip'], data['network']+'/'+data['subnet'])
            if not nsipdetails:
                response = {'message': f'Incorrect Nameserver IP: {data["nameserver_ip"]}.'}
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
            Service().queue('dns','restart')
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
@token_required
def config_network_delete(name=None):
    """
    Input - Network Name
    Process - Delete The Network.
    Output - Success or Failure.
    """
    network = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
    if network:
        Database().delete_row('network', [{"column": "name", "value": name}])
        Service().queue('dns','restart')
        response = {'message': 'Network removed.'}
        access_code = 204
    else:
        response = {'message': f'Network {name} not present in database.'}
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
@token_required
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
@token_required
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
@token_required
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
@token_required
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
@token_required
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
                nodesecretcolumns = Database().get_columns('nodesecrets')
                columncheck = Helper().checkin_list(data[0], nodesecretcolumns)
                secretname = data[0]['name']
                where = f' WHERE nodeid = "{nodeid}" AND name = "{secretname}"'
                secret_data = Database().get_record(None, 'nodesecrets', where)
                if columncheck:
                    if secret_data:
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
                        data[0]['nodeid'] = nodeid
                        data[0]['content'] = Helper().encrypt_string(data[0]['content'])
                        row = Helper().make_rows(data[0])
                        result=Database().insert('nodesecrets', row)
                        if result:
                            response = {'message': f'Node {name} secret {secret} updated.'}
                            access_code = 204
                        else:
                            response = {'message': f'Node {name} secret {secret} update failed.'}
                            access_code = 500
                else:
                    LOGGER.error(f'Rows do not match columns for Group {name}, secret {secret}.')
                    response = {'message': f'Supplied columns do not match the requirements.'}
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
@token_required
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
@token_required
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
@token_required
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
@token_required
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
@token_required
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
@token_required
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
                grpsecretcolumns = Database().get_columns('groupsecrets')
                columncheck = Helper().checkin_list(data[0], grpsecretcolumns)
                secretname = data[0]['name']
                where = f' WHERE groupid = "{groupid}" AND name = "{secretname}"'
                secretdata = Database().get_record(None, 'groupsecrets', where)
                if columncheck:
                    if secretdata:
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
                        data[0]['groupid'] = groupid
                        data[0]['content'] = Helper().encrypt_string(data[0]['content'])
                        row = Helper().make_rows(data[0])
                        result=Database().insert('groupsecrets', row)
                        if result:
                            response = {'message': f'Group {name} secret {secret} updated.'}
                            access_code = 204
                        else:
                            response = {'message': f'Group {name} secret {secret} update failed.'}
                            access_code = 500
                else:
                    LOGGER.error(f'Rows do not match columns for Group {name}, secret {secret}.')
                    response = {'message': f'Supplied columns do not match the requirements.'}
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
@token_required
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
@token_required
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

    LOGGER.debug(f"control STATUS: request_id: [{request_id}]")
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
                            #Database().delete_row('status', [{"column": "request_id", "value": request_id}])
                            Status().del_messages(request_id)
                        else:
                            created,*_=(record['created'].split('.')+[None])
                            message.append(created+" :: "+record['message'])
        response={'message': (';;').join(message) }
        Status().mark_messages_read(request_id)
        access_code = 200
    return json.dumps(response), access_code

