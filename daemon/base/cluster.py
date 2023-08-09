#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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


from json import dumps
from common.constant import CONFIGFILE
from utils.log import Log
from utils.database import Database
from utils.service import Service
from utils.helper import Helper


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
        This method will return all the osimage in detailed format.
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


    def update_cluster(self, http_request=None):
        """
        This method will update the cluster information.
        """
        status=False
        response="Internal error"
        items = {'debug': False, 'security': False, 'createnode_ondemand': True}
        request_data = http_request.data
        if request_data:
            data = request_data['config']['cluster']
            cluster_columns = Database().get_columns('cluster')
            cluster_check = Helper().compare_list(data, cluster_columns)
            if cluster_check:
                cluster = Database().get_record(None, 'cluster', None)
                if cluster:
                    if 'ntp_server' in data and data['ntp_server']:
                        temp = data['ntp_server']
                        temp = temp.replace(' ',',')
                        temp = temp.replace(',,',',')
                        for ipaddress in temp.split(','):
                            if not Helper().check_ip(ipaddress):
                                status=False
                                return status, f'{ipaddress} is an invalid NTP server IP'
                        data['ntp_server'] = temp
                    if 'nameserver_ip' in data and data['nameserver_ip']:
                        temp = data['nameserver_ip']
                        temp = temp.replace(' ',',')
                        temp = temp.replace(',,',',')
                        for ipaddress in temp.split(','):
                            if not Helper().check_ip(ipaddress):
                                status=False
                                return status, f'{ipaddress} is an invalid name server IP'
                        data['nameserver_ip'] = temp
                    if 'forwardserver_ip' in data and data['forwardserver_ip']:
                        temp = data['forwardserver_ip']
                        temp = temp.replace(' ',',')
                        temp = temp.replace(',,',',')
                        for ipaddress in temp.split(','):
                            if not Helper().check_ip(ipaddress):
                                status=False
                                return status, f'{ipaddress} is an invalid forwarder IP'
                        data['forwardserver_ip'] = temp

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
