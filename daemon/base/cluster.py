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
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'


from common.constant import CONFIGFILE
from utils.log import Log
from utils.database import Database
from utils.service import Service
from utils.helper import Helper
from utils.tables import Tables


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
            if cluster[0]['nextnode_discover']:
                cluster[0]['nextnode_discover'] = True
            else:
                cluster[0]['nextnode_discover'] = False
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
                response['config']['cluster'][controller['hostname']] = controller
                status=True
        else:
            self.logger.error('No cluster is available.')
            response = 'No cluster is available'
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
                response[table]=Tables().export_table(table,sequence=False)
        return status, response


    def update_cluster(self, request_data=None):
        """
        This method will update the cluster information.
        """
        status=False
        response="Internal error"
        items = {'debug': False, 'security': False, 'createnode_ondemand': True, 'nextnode_discover': False}
        if request_data:
            data = request_data['config']['cluster']
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
