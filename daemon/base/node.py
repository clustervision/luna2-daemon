#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Node Class, to filter and make data set for nodes.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

from base64 import b64decode, b64encode
from json import dumps
from utils.database import Database
from utils.log import Log
from utils.config import Config
from utils.service import Service
from utils.queue import Queue
from utils.helper import Helper
from utils.monitor import Monitor


class Node():
    """
    This class is responsible for all operations on node.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()


    def get_all_nodes(self):
        """This method will return all the nodes in detailed format."""
        nodes = Database().get_record(None, 'node', None)
        groups = Database().get_record(None, 'group', None)
        osimages = Database().get_record(None, 'osimage', None)
        switches = Database().get_record(None, 'switch', None)
        bmcsetups = Database().get_record(None, 'bmcsetup', None)
        group = Helper().convert_list_to_dict(groups, 'id')
        osimage = Helper().convert_list_to_dict(osimages, 'id')
        switch = Helper().convert_list_to_dict(switches, 'id')
        bmcsetup = Helper().convert_list_to_dict(bmcsetups, 'id')
        cluster = Database().get_record(None, 'cluster', None)
        if nodes:
            items = {
                'prescript': '<empty>',
                'partscript': '<empty>',
                'postscript': '<empty>',
                'setupbmc': False,
                'netboot': False,
                'localinstall': False,
                'bootmenu': False,
                'provision_method': 'torrent',
                'provision_fallback': 'http',
                'provision_interface': 'BOOTIF'
            }

            response = {'config': {'node': {} }}
            for node in nodes:
                node_name = node['name']
                nodeid = node['id']
                groupid = {}
                if 'groupid' in node and node['groupid'] in group.keys():
                    node['group'] = group[node['groupid']]['name']
                    groupid = node['groupid']
                    if node['osimageid']:
                        node['osimage'] = '!!Invalid!!'
                        if node['osimageid'] in osimage.keys():
                            node['osimage'] = osimage[node['osimageid']]['name'] or None
                    elif 'osimageid' in group[groupid] and group[groupid]['osimageid'] in osimage.keys():
                        node['osimage'] = osimage[group[groupid]['osimageid']]['name'] or None
                    else:
                        node['osimage'] = None
                    if node['bmcsetupid']:
                        node['bmcsetup'] = '!!Invalid!!'
                        if node['bmcsetupid'] in bmcsetup.keys():
                            node['bmcsetup'] = bmcsetup[node['bmcsetupid']]['name'] or None
                    elif 'bmcsetupid' in group[groupid] and group[groupid]['bmcsetupid'] in bmcsetup.keys():
                        node['bmcsetup'] = bmcsetup[group[groupid]['bmcsetupid']]['name'] or None
                    else:
                        node['bmcsetup'] = None
                else:
                    node['group'] = '!!Invalid!!'
                # -------------
                for item in items.keys():
                    if cluster and item in cluster[0] and isinstance(items[item], bool):
                        cluster[0][item] = str(Helper().make_bool(cluster[0][item]))
                    if groupid and item in group[groupid] and isinstance(items[item], bool):
                        group[groupid][item] = str(Helper().make_bool(group[groupid][item]))
                    if cluster and item in cluster[0] and ((not group) or (not groupid) or (not item in group[groupid]) or (not group[groupid][item])) and not node[item]:
                        node[item] = cluster[0][item] or items[item]
                    else:
                        if groupid and item in group[groupid] and not node[item]:
                            node[item] = group[groupid][item] or items[item]
                        else:
                            if isinstance(items[item], bool):
                                node[item] = str(Helper().make_bool(node[item]))
                            node[item] = node[item] or items[item]
                # -------------
                node['switch'] = None
                if node['switchid']:
                    node['switch'] = '!!Invalid!!'
                    if node['switchid'] in switch.keys():
                        node['switch'] = switch[node['switchid']]['name'] or None
                node['tpm_present'] = False
                if node['tpm_uuid'] or node['tpm_sha256'] or node['tpm_pubkey']:
                    node['tpm_present']=True
                del node['id']
                del node['bmcsetupid']
                del node['groupid']
                del node['osimageid']
                del node['switchid']

                node['status'], *_ = Monitor().installer_state(node['status'])

                node['bootmenu'] = Helper().make_bool(node['bootmenu'])
                node['localboot'] = Helper().make_bool(node['localboot'])
                node['localinstall'] = Helper().make_bool(node['localinstall'])
                node['netboot'] = Helper().make_bool(node['netboot'])
                node['service'] = Helper().make_bool(node['service'])
                node['setupbmc'] = Helper().make_bool(node['setupbmc'])
                node['interfaces']=[]
                node_interface = Database().get_record_join(
                    ['nodeinterface.interface','ipaddress.ipaddress','nodeinterface.macaddress','network.name as network','nodeinterface.options'],
                    ['network.id=ipaddress.networkid','ipaddress.tablerefid=nodeinterface.id'],
                    ['tableref="nodeinterface"',f"nodeinterface.nodeid='{nodeid}'"]
                )
                node['hostname'] = node['name']
                if node_interface:
                    node['interfaces'] = []
                    for interface in node_interface:
                        interfacename, *_ = (node['provision_interface'].split(' ')+[None])
                        # we skim off parts that we added for clarity in above section
                        # (e.g. (default)). also works if there's no additional info
                        if interface['interface'] == interfacename and interface['network']:
                            # if it is my prov interf then it will get that domain as a FQDN.
                            node['hostname'] = node['name'] + '.' + interface['network']
                        if not interface['options']:
                            del interface['options']
                        node['interfaces'].append(interface)
                response['config']['node'][node_name] = node
            self.logger.info('Provided list of all nodes.')
        else:
            self.logger.error('No nodes are available.')
            response = {'message': 'No nodes are available'}
            return False, response
        return True, response
        #return dumps(response), access_code



    def get_node(self, name=None):
        """This method will return requested node in detailed format."""
        nodes = Database().get_record(None, 'node', f' WHERE name = "{name}"')
        all_nodes = Database().get_record_join(
            [
                'node.*',
                'group.name AS group',
                'osimage.name AS group_osimage',
                'group.setupbmc AS group_setupbmc',
                'group.bmcsetupid AS group_bmcsetupid',
                'group.prescript AS group_prescript',
                'group.partscript AS group_partscript',
                'group.postscript AS group_postscript',
                'group.netboot AS group_netboot',
                'group.localinstall AS group_localinstall',
                'group.bootmenu AS group_bootmenu',
                'group.provision_method AS group_provision_method',
                'group.provision_fallback AS group_provision_fallback',
                'group.provision_interface AS group_provision_interface'
            ],
            ['group.id=node.groupid','osimage.id=group.osimageid'],
            f"node.name='{name}'"
        )
        if all_nodes and nodes:
            nodes[0].update(all_nodes[0])
        if nodes:
            node = nodes[0]
            response = {'config': {'node': {} }}
            nodename = node['name']
            nodeid = node['id']
            if node['bmcsetupid']:
                node['bmcsetup'] = Database().getname_byid('bmcsetup', node['bmcsetupid']) or '!!Invalid!!'
            elif 'group_bmcsetupid' in node and node['group_bmcsetupid']:
                node['bmcsetup'] = Database().getname_byid('bmcsetup', node['group_bmcsetupid']) + f" ({node['group']})"
            if 'group_bmcsetupid' in node:
                del node['group_bmcsetupid']
            if node['osimageid']:
                node['osimage'] = Database().getname_byid('osimage', node['osimageid']) or '!!Invalid!!'
            elif 'group_osimage' in node and node['group_osimage']:
                node['osimage'] = node['group_osimage']+f" ({node['group']})"
            if 'group_osimage' in node:
                del node['group_osimage']
            if node['switchid']:
                node['switch'] = Database().getname_byid('switch', node['switchid'])
            if not node['groupid']:
                node['group']='!!Invalid!!'

            cluster = Database().get_record(None, 'cluster', None)
            if cluster:
                node['cluster_provision_method'] = cluster[0]['provision_method']
                node['cluster_provision_fallback'] = cluster[0]['provision_fallback']

            # below section shows what's configured for the node, or the group, or a default fallback
            items = {
                # 'prescript': '<empty>',
                # 'partscript': '<empty>',
                # 'postscript': '<empty>',
                'setupbmc': False,
                'netboot': False,
                'localinstall': False,
                'bootmenu': False,
                'provision_method': 'torrent',
                'provision_fallback': 'http',
                'provision_interface': 'BOOTIF'
            }
            for item in items.keys():
                if 'cluster_'+item in node and isinstance(items[item], bool):
                    node['cluster_'+item] = str(Helper().make_bool(node['cluster_'+item]))
                if 'group_'+item in node and isinstance(items[item], bool):
                    node['group_'+item] = str(Helper().make_bool(node['group_'+item]))
                if 'cluster_'+item in node and node['cluster_'+item] and ((not 'group_'+item in node) or (not node['group_'+item])) and not node[item]:
                    node['cluster_'+item] += f" (cluster)"
                    node[item] = node[item] or node['cluster_'+item] or str(items[item]+' (default)')
                else:
                    if 'group_'+item in node and node['group_'+item] and not node[item]:
                        node['group_'+item] += f" ({node['group']})"
                        node[item] = node[item] or node['group_'+item] or str(items[item]+' (default)')
                    else:
                        if isinstance(items[item], bool):
                            node[item] = str(Helper().make_bool(node[item]))
                        node[item] = node[item] or str(items[item])+' (default)'
                if 'group_'+item in node:
                    del node['group_'+item]
                if 'cluster_'+item in node:
                    del node['cluster_'+item]
            # same as above but now specifically base64
            b64items = {'prescript': '<empty>', 'partscript': '<empty>', 'postscript': '<empty>'}
            try:
                for item in b64items.keys():
                    if 'group_'+item in node and node['group_'+item] and not node[item]:
                        data = b64decode(node['group_'+item])
                        data = data.decode("ascii")
                        data = f"({node['group']}) {data}"
                        group_data = b64encode(data.encode())
                        group_data = group_data.decode("ascii")
                        node[item] = node[item] or group_data
                    else:
                        default_str = str(b64items[item]+' (default)')
                        default_data = b64encode(default_str.encode())
                        default_data = default_data.decode("ascii")
                        node[item] = node[item] or default_data
                    if 'group_'+item in node:
                        del node['group_'+item]
            except Exception as exp:
                self.logger.error(f"{exp}")

            del node['id']
            del node['bmcsetupid']
            del node['groupid']
            del node['osimageid']
            del node['switchid']
            node['status'], *_ = Monitor().installer_state(node['status'])
            node['service'] = Helper().make_bool(node['service'])
            node['setupbmc'] = Helper().make_bool(node['setupbmc'])
            node['localboot'] = Helper().make_bool(node['localboot'])
            node['interfaces'] = []
            node_interface = Database().get_record_join(
                ['nodeinterface.interface', 'ipaddress.ipaddress', 'nodeinterface.macaddress', 'network.name as network', 'nodeinterface.options'],
                ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id'],
                ['tableref="nodeinterface"', f"nodeinterface.nodeid='{nodeid}'"]
            )
            node['hostname'] = nodename
            if node_interface:
                for interface in node_interface:
                    interfacename, *_ = (node['provision_interface'].split(' ')+[None])
                    # we skim off parts that we added for clarity in above section
                    # (e.g. (default)). also works if there's no additional info
                    if interface['interface'] == interfacename and interface['network']:
                        # if it is my prov interf then it will get that domain as a FQDN.
                        node['hostname'] = nodename + '.' + interface['network']
                    if not interface['options']:
                        del interface['options']
                    node['interfaces'].append(interface)

            response['config']['node'][nodename] = node
            self.logger.info(f'Provided details for node {name}.')
            access_code = 200
        else:
            self.logger.error(f'Node {name} is not available.')
            response = {'message': f'Node {name} is not available'}
            return False, response
        return True, response


    def update_node(self, name=None, http_request=None):
        """This method will return update requested node."""
        data = {}
        items = {
            # 'setupbmc': False,
            # 'netboot': False,
            # 'localinstall': False,
            # 'bootmenu': False,
            'service': False,
            'localboot': False
        }
        # minimal required items with defaults. we do inherit things from e.g. groups. but that's
        # real time and not here
        create, update = False, False
        access_code = 400
        request_data = http_request.data
        if request_data:
            if 'node' not in request_data['config'].keys():
                response = {'message': 'Bad Request'}
                access_code = 400
                return dumps(response), access_code

            data = request_data['config']['node'][name]
            node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
            if node:
                nodeid = node[0]['id']
                if 'newnodename' in data: # is mentioned as newhostname in design documents!
                    nodename_new = data['newnodename']
                    where = f' WHERE `name` = "{nodename_new}"'
                    node_check = Database().get_record(None, 'node', where)
                    if node_check:
                        response = {'message': f'{nodename_new} already present in database'}
                        access_code = 404
                        return dumps(response), access_code
                    else:
                        data['name'] = data['newnodename']
                        del data['newnodename']
                update = True
            else:
                if 'newnodename' in data:
                    nodename_new = data['newnodename']
                    response = {'message': f'{nodename_new} is not allowed while creating a new node'}
                    access_code = 400
                    return dumps(response), access_code
                create = True

            for item in items:
                if item in data:
                    data[item] = data[item] or items[item]
                    if isinstance(items[item], bool):
                        data[item] = str(Helper().make_boolnum(data[item]))
                elif create:
                    data[item] = items[item]
                    if isinstance(items[item], bool):
                        data[item] = str(Helper().make_boolnum(data[item]))
                if item in data and (not data[item]) and (item not in items):
                    del data[item]

            # True means: cannot be empty if supplied. False means: can only be empty or correct
            checks = {'bmcsetup': False, 'group': True, 'osimage': False, 'switch': False}
            for check in checks.keys():
                if check in data:
                    check_name = data[check]
                    if data[check] == "" and checks[check] is False:
                        data[check+'id']=""
                    else:
                        data[check+'id'] = Database().getid_byname(check, check_name)
                        if (not data[check+'id']):
                            access_code = 404
                            response = {'message': f'{check} {check_name} is not known or valid'}
                            return dumps(response), access_code
                    del data[check]

            interfaces = None
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
                    response = {'message': f'Node {name} updated successfully'}
                    access_code = 204
                if create:
                    if not 'groupid' in data:
                        # ai, we DO need this for new nodes...... kind of.
                        # we agreed on this. pending?
                        access_code = 400
                        response = {'message': 'group name is required for new nodes'}
                        return dumps(response), access_code
                    data['name'] = name
                    row = Helper().make_rows(data)
                    nodeid = Database().insert('node', row)
                    response = {'message': f'Node {name} created successfully'}
                    access_code = 201
                    if nodeid and 'groupid' in data and data['groupid']:
                        # ----> GROUP interface. WIP. pending. should work but i keep it WIP
                        group_interfaces = Database().get_record_join(
                            ['groupinterface.interface','network.name as network','groupinterface.options'],
                            ['network.id=groupinterface.networkid'],
                            [f"groupinterface.groupid={data['groupid']}"]
                        )
                        if group_interfaces:
                            for group_interface in group_interfaces:
                                result, mesg = Config().node_interface_config(
                                    nodeid,
                                    group_interface['interface'],
                                    None,
                                    group_interface['options']
                                )
                                if result:
                                    ips = Config().get_all_occupied_ips_from_network(group_interface['network'])
                                    network = Database().get_record(None, 'network', f" WHERE `name` = \"{group_interface['network']}\"")
                                    if network:
                                        avail = Helper().get_available_ip(network[0]['network'], network[0]['subnet'], ips)
                                        if avail:
                                            result, mesg = Config().node_interface_ipaddress_config(
                                                nodeid,
                                                group_interface['interface'],
                                                avail,
                                                group_interface['network']
                                            )
                                        # we do not ping nodes as it will take time if we add bulk
                                        # nodes, it'll take 1s per node. code block removal pending?
                                        # ret=0
                                        # max=5
                                        # we try to ping for X ips, if none of these are free,
                                        # something else is going on (read: rogue devices)....
                                        # while(max>0 and ret!=1):
                                        #     avail=Helper().get_available_ip(network[0]['network'], network[0]['subnet'],ips)
                                        #     ips.append(avail)
                                        #     output, ret = Helper().runcommand(f"ping -w1 -c1 {avail}", True, 3)
                                        #     max-= 1

                if interfaces:
                    for interface in interfaces:
                        # Antoine
                        interface_name = interface['interface']
                        ipaddress,macaddress,network,options=None,None,None,None
                        if 'macaddress' in interface.keys():
                            macaddress = interface['macaddress']
                        if 'options' in interface.keys():
                            options = interface['options']
                        if 'network' in interface.keys():
                            network = interface['network']
                        result, mesg = Config().node_interface_config(nodeid, interface_name, macaddress, options)
                        if result:
                            if not 'ipaddress' in interface.keys():
                                existing = Database().get_record_join(
                                    ['ipaddress.ipaddress'],
                                    ['nodeinterface.nodeid=node.id','ipaddress.tablerefid=nodeinterface.id'],
                                    [f"node.name='{name}'","ipaddress.tableref='nodeinterface'",f"nodeinterface.interface='{interface_name}'"]
                                )
                                if existing:
                                    ipaddress = existing[0]['ipaddress']
                                else:
                                    ips = Config().get_all_occupied_ips_from_network(network)
                                    network_details = Database().get_record(None, 'network', f" WHERE `name` = '{network}'")
                                    if network_details:
                                        avail = Helper().get_available_ip(network_details[0]['network'], network_details[0]['subnet'], ips)
                                        if avail:
                                            ipaddress = avail
                            else:
                                ipaddress=interface['ipaddress']
                            result, mesg = Config().node_interface_ipaddress_config(nodeid, interface_name, ipaddress, network)

                        if result is False:
                            response = {'message': f'{mesg}'}
                            access_code = 404
                            return dumps(response), access_code

                Service().queue('dhcp','restart')
                Service().queue('dns','restart')
                # below might look as redundant but is added to prevent a possible race condition
                # when many nodes are added in a loop.
                # the below tasks ensures that even the last node will be included in dhcp/dns
                Queue().add_task_to_queue('dhcp:restart', 'housekeeper', '__node_post__')
                Queue().add_task_to_queue('dns:restart', 'housekeeper', '__node_post__')
            else:
                response = {'message': 'Bad Request; Columns are incorrect'}
                access_code = 400
        else:
            response = {'message': 'Bad Request; Did not received data'}
            access_code = 400
        return dumps(response), access_code


    def clone_node(self, name=None, http_request=None):
        """This method will clone a node."""
        data = {}
        items = {'service': False, 'localboot': False}
        request_data = http_request.data
        if request_data:
            if 'node' not in request_data['config'].keys():
                response = {'message': 'Bad Request'}
                access_code = 400
                return dumps(response), access_code

            newnodename=None
            data = request_data['config']['node'][name]
            node = Database().get_record(None, 'node', f' WHERE name = "{name}"')
            if node:
                nodeid = node[0]['id']
                if 'newnodename' in data: 
                    newnodename = data['newnodename']
                    where = f' WHERE `name` = "{newnodename}"'
                    node_check = Database().get_record(None, 'node', where)
                    if node_check:
                        response = {'message': f'{newnodename} already present in database'}
                        access_code = 404
                        return dumps(response), access_code
                    else:
                        data['name'] = data['newnodename']
                        del data['newnodename']
                else:
                    response = {'message': 'Bad Request; Destination node name not supplied'}
                    access_code = 400
                    return dumps(response), access_code
            else:
                response = {'message': f'Bad Request; Source node {name} does not exist'}
                access_code = 400
                return dumps(response), access_code

            del node[0]['id']
            del node[0]['status']
            for item in node[0]:
                if not item in data:  # we copy from another node unless we supply
                    data[item] = node[0][item]
                    if item in items and isinstance(items[item], bool):
                        data[item] = str(Helper().make_boolnum(data[item]))
                elif item in items:
                    data[item] = items[item]
                    if isinstance(items[item], bool):
                        data[item] = str(Helper().make_boolnum(data[item]))
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
                            access_code = 404
                            response = {'message': f'{check} {check_name} is not known or valid'}
                            return dumps(response), access_code
                    del data[check]
            interfaces = None
            if 'interfaces' in data:
                interfaces = data['interfaces']
                del data['interfaces']
            node_columns = Database().get_columns('node')
            columns_check = Helper().checkin_list(data, node_columns)
            if columns_check:
                new_nodeid=None
                row = Helper().make_rows(data)
                new_nodeid = Database().insert('node', row)
                if not new_nodeid:
                    response = {'message': f'Node {newnodename} could not be created due to possible property clash'}
                    access_code = 404
                    return dumps(response), access_code
                response = {'message': f'Node {name} created successfully'}
                access_code = 201
                node_interfaces = Database().get_record_join(
                    ['nodeinterface.interface', 'ipaddress.ipaddress', 'nodeinterface.macaddress', 'network.name as network', 'nodeinterface.options'],
                    ['network.id=ipaddress.networkid', 'ipaddress.tablerefid=nodeinterface.id'],
                    ['tableref="nodeinterface"', f"nodeinterface.nodeid='{nodeid}'"]
                )
                if interfaces:
                    for interface in interfaces:
                        # Antoine
                        interface_name = interface['interface']
                        for node_interface in node_interfaces:
                            # delete interfaces we overwrite
                            if interface_name == node_interface['interface']:
                                del node_interfaces[node_interface]
                        macaddress, network = None, None
                        if 'macaddress' in interface.keys():
                            macaddress = interface['macaddress']
                        if 'options' in interface.keys():
                            options = interface['options']
                        result,mesg = Config().node_interface_config(new_nodeid, interface_name, macaddress, options)
                        if result and 'ipaddress' in interface.keys():
                            ipaddress = interface['ipaddress']
                            if 'network' in interface.keys():
                                network = interface['network']
                            result,mesg = Config().node_interface_ipaddress_config(new_nodeid, interface_name, ipaddress, network)
                            
                        if result is False:
                            response = {'message': f'{mesg}'}
                            access_code = 404
                            return dumps(response), access_code

                for node_interface in node_interfaces:
                    interface_name = node_interface['interface']
                    interface_options = node_interface['options']
                    result, mesg = Config().node_interface_config(new_nodeid, interface_name, None, interface_options )
                    if result and 'ipaddress' in node_interface.keys():
                        if 'network' in node_interface.keys():
                            networkname = node_interface['network']
                            ips = Config().get_all_occupied_ips_from_network(networkname)
                            network = Database().get_record(None, 'network', f' WHERE `name` = "{networkname}"')
                            if network:
                                ret, avail = 0, None
                                max_count = 5
                                # we try to ping for X ips, if none of these are free, something
                                # else is going on (read: rogue devices)....
                                while(max_count>0 and ret!=1):
                                    avail = Helper().get_available_ip(network[0]['network'],network[0]['subnet'],ips)
                                    ips.append(avail)
                                    _, ret = Helper().runcommand(f"ping -w1 -c1 {avail}", True, 3)
                                    max_count -= 1

                                if avail:
                                    result,mesg = Config().node_interface_ipaddress_config(new_nodeid, interface_name, avail, networkname)
                                    if result is False:
                                        response = {'message': f'{mesg}'}
                                        access_code = 404
                                        return dumps(response), access_code
                # Service().queue('dhcp','restart')
                # do we need dhcp restart? MAC is wiped on new NIC so no real need i guess. pending
                Service().queue('dns','restart')
            else:
                response = {'message': 'Bad Request; Columns are incorrect'}
                access_code = 400
        else:
            response = {'message': 'Bad Request; Did not received data'}
            access_code = 400
        return dumps(response), access_code


    def delete_node(self, name=None):
        """This method will delete a node."""
        node = Database().get_record(None, 'node', f' WHERE `name` = "{name}"')
        if node:
            nodeid = node[0]['id']
            Database().delete_row('node', [{"column": "name", "value": name}])
            ipaddress = Database().get_record_join(
                ['ipaddress.id'],
                ['ipaddress.tablerefid=nodeinterface.id'],
                ['tableref="nodeinterface"',f"nodeinterface.nodeid='{nodeid}'"]
            )
            if ipaddress:
                for node_ip in ipaddress:
                    Database().delete_row('ipaddress', [{"column": "id", "value": node_ip['id']}])
            Database().delete_row('nodeinterface', [{"column": "nodeid", "value": nodeid}])
            Database().delete_row('nodesecrets', [{"column": "nodeid", "value": nodeid}])
            Service().queue('dns', 'restart')
            Service().queue('dhcp', 'restart')
            # below might look redundant but is added to prevent a possible race condition
            # when many nodes are added in a loop.
            # the below tasks ensures that even the last node will be included in dhcp/dns
            Queue().add_task_to_queue('dhcp:restart', 'housekeeper', '__node_delete__')
            Queue().add_task_to_queue('dns:restart', 'housekeeper', '__node_delete__')
            response = {'message': f'Node {name} with all its interfaces removed'}
            access_code = 204
        else:
            response = {'message': f'Node {name} not present in database'}
            access_code = 404
        return dumps(response), access_code
