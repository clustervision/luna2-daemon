#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>

"""
Cluster Class will handle all Cluster operations.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'


import json
from common.constant import CONFIGFILE
from utils.log import Log
from utils.database import Database
from utils.service import Service
from utils.helper import Helper
from utils.tables import Tables
from utils.controller import Controller


class Cluster():
    """
    This class is responsible for all operations for Cluster.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()


    def information(self):
        """
        This method will return all the cluster info in detailed format.
        """
        status=False
        cluster = Database().get_record(None, 'cluster', None)
        if cluster:
            cluster_id = cluster[0]['id']
            del cluster[0]['id']
            for item in ['debug','security','createnode_ondemand','createnode_macashost',
                         'nextnode_discover','packing_bootpause']:
                cluster[0][item] = Helper().make_bool(cluster[0][item])
            response = {'config': {'cluster': cluster[0] }}
            controllers = Database().get_record_join(
                ['controller.*', 'ipaddress.ipaddress'],
                ['ipaddress.tablerefid=controller.id', 'cluster.id=controller.clusterid'],
                ['tableref="controller"', f'cluster.id="{cluster_id}"']
            )
            for controller in controllers:
                del controller['id']
                del controller['clusterid']
                controller['luna_config'] = CONFIGFILE
                controller['shadow'] = Helper().make_bool(controller['shadow'])
                if not controller['shadow']:
                    del controller['shadow']
                if controller['beacon']:
                    response['config']['cluster']['controller'] = controller
                else:
                    response['config']['cluster'][controller['hostname']] = controller
                del controller['beacon']
                status=True
        else:
            self.logger.error('No cluster available.')
            response = 'No cluster available'
            status=False
        return status, response


    def export_config(self):
        """
        This method will export all database data. Used for backups.
        """
        status=False
        response="Internal error"
        tables = Tables().get_tables()+['ha']
        if tables:
            status=True
            response={}
            for table in tables:
                response[table]=Tables().export_table(table,sequence=True,structure=True)
        return status, response


    def import_config(self,data=None):
        """
        This method will import exported database config. Used importing backups.
        """
        status=False
        response="Invalid request. No suitable data provided"
        if data:
            try:
                self.logger.debug(f"DATA: {data} ::: {type(data)}")
                status, backup=self.export_config()
                if status and backup:
                    for table in data.keys():
                        status=Tables().import_table(table,data[table],emptyok=True)
                        if not status:
                            response=f"Error importing table {table}. Rolling back config import"
                            for table in backup:
                                Tables().import_table(table,backup[table],emptyok=True)
                            return status, response
                    response="Successfully imported config"
                else:
                    response="Could not make config backup before importing. Rolling back config import"
            except Exception as exp:
                status=False
                response="Unknown problem encountered importing config. Rolling back config import"
                self.logger.error(f"Error during config import: {exp}")
        return status, response


    def update_cluster(self, request_data=None):
        """
        This method will update the cluster information.
        """
        status=False
        response="Internal error"
        items = {'debug': False, 'security': False, 'createnode_ondemand': True,
                 'createnode_macashost': True, 'nextnode_discover': False}
        if request_data:
            data = request_data['config']['cluster']

            # renumbering controllers prepare. this could be tricky. - Antoine
            # for H/A things should be taken in consideration....
            if 'controller' in data:
                controller_name = Controller().get_beacon()
                if controller_name != 'controller':
                    data[controller_name] = data['controller']
                    del data['controller']
            controller_ips=[]
            controllers = Database().get_record_join(
                ['controller.hostname','ipaddress.ipaddress','ipaddress.ipaddress_ipv6',
                 'ipaddress.id as ipid','network.name as networkname','network.id as networkid',
                 'network.network','network.network_ipv6','network.subnet','network.subnet_ipv6'],
                ['ipaddress.tablerefid=controller.id','ipaddress.networkid=network.id'],
                ['tableref="controller"']
            )
            if controllers:
                for controller in controllers:
                    controller_details=None
                    if controller['hostname'] in data:
                        if controller['ipaddress'] == data[controller['hostname']] or controller['ipaddress_ipv6'] == data[controller['hostname']]:
                            self.logger.info(f"Not using new ip address {data[controller['hostname']]} for controller {controller['hostname']}")
                        else:
                            if Helper().check_if_ipv6(data[controller['hostname']]):
                                controller_details = Helper().check_ip_range(data[controller['hostname']], controller['network_ipv6'] + '/' + controller['subnet_ipv6'])
                            else:
                                controller_details = Helper().check_ip_range(data[controller['hostname']], controller['network'] + '/' + controller['subnet'])
                            if not controller_details:
                                status=False
                                ret_msg = f"Invalid request: Controller address mismatch with network {controller['networkname']} address/subnet. "
                                ret_msg += f"Please provide valid ip address for controller {controller['hostname']}"
                                return status, ret_msg
                            controller_ips.append({'ipaddress': data[controller['hostname']], 'id': controller['ipid'], 'hostname': controller['hostname']})
                            self.logger.info(f"Using new ip address {data[controller['hostname']]} for controller {controller['hostname']}")
                        del data[controller['hostname']]

            for controller in controller_ips:
                where = f"WHERE ipaddress='{controller['ipaddress']}' OR ipaddress_ipv6='{controller['ipaddress']}'"
                claship = Database().get_record(None, 'ipaddress', where)
                if claship:
                    status=False
                    ret_msg = f"Invalid request: Clashing ip address for controller {controller['hostname']} with existing ip address {controller['ipaddress']}"
                    return status, ret_msg
                row=None
                if Helper().check_if_ipv6(controller['ipaddress']):
                    row = Helper().make_rows({'ipaddress_ipv6': controller['ipaddress']})
                else:
                    row = Helper().make_rows({'ipaddress': controller['ipaddress']})
                where = [{"column": "id", "value": controller['id']}]
                status=Database().update('ipaddress', row, where)
                if not status:
                    status=False
                    ret_msg = f"Error updating ip address for controller {controller['hostname']}"
                    return status, ret_msg

            cluster_columns = Database().get_columns('cluster')
            cluster_check = Helper().compare_list(data, cluster_columns)
            if cluster_check:
                cluster = Database().get_record(None, 'cluster', None)
                if cluster:
                    if 'ntp_server' in data: 
                        if data['ntp_server']:
                            temp = data['ntp_server']
                            temp = temp.replace(' ',',')
                            temp = temp.replace(',,',',')
                            for ipaddress in temp.split(','):
                                if not Helper().check_ip(ipaddress):
                                    status=False
                                    return status, f'{ipaddress} is an invalid NTP server IP'
                            data['ntp_server'] = temp
                        else:
                            data['ntp_server'] = None
                    if 'nameserver_ip' in data:
                        if data['nameserver_ip']:
                            temp = data['nameserver_ip']
                            temp = temp.replace(' ',',')
                            temp = temp.replace(',,',',')
                            for ipaddress in temp.split(','):
                                if not Helper().check_ip(ipaddress):
                                    status=False
                                    return status, f'{ipaddress} is an invalid name server IP'
                            data['nameserver_ip'] = temp
                        else:
                            data['nameserver_ip'] = None
                    if 'forwardserver_ip' in data:
                        if data['forwardserver_ip']:
                            temp = data['forwardserver_ip']
                            temp = temp.replace(' ',',')
                            temp = temp.replace(',,',',')
                            for ipaddress in temp.split(','):
                                if not Helper().check_ip(ipaddress):
                                    status=False
                                    return status, f'{ipaddress} is an invalid forwarder IP'
                            data['forwardserver_ip'] = temp
                        else:
                            data['forwardserver_ip'] = None
                    if 'domain_search' in data:
                        if data['domain_search']:
                            temp = data['domain_search']
                            temp = temp.replace(' ',',')
                            temp = temp.replace(',,',',')
                            data['domain_search'] = temp
                        else:
                            data['domain_search'] = None

                    for key, value in items.items():
                        if key in data:
                            data[key] = str(data[key]) or value
                            if isinstance(value, bool):
                                data[key] = str(Helper().bool_to_string(data[key]))

                    where = [{"column": "id", "value": cluster[0]['id']}]
                    row = Helper().make_rows(data)
                    Database().update('cluster', row, where)
                    Service().queue('dns','reload')
                    Service().queue('dns','restart')
                    response = 'Cluster updated'
                    status=True
                else:
                    response = 'No cluster is available to update'
                    status=False
            else:
                response = 'Invalid request: Columns are incorrect'
                status=False
        else:
            response = 'Invalid request: Did not receive data'
            status=False
        return status, response
