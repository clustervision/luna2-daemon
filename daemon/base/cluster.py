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
from utils.service import Service
from common.constant import CONFIGFILE
from utils.database import Database
from utils.log import Log
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
        """This method will return all the osimage in detailed format."""
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
            controllers = Database().get_record_join(
                ['controller.*', 'ipaddress.ipaddress'],
                ['ipaddress.tablerefid=controller.id', 'cluster.id=controller.clusterid'],
                ['tableref="controller"', f'cluster.id="{clusterid}"']
            )
            for controller in controllers:
                del controller['id']
                del controller['clusterid']
                controller['luna_config'] = CONFIGFILE
                response['config']['cluster'][controller['hostname']] = controller
                access_code = 200
        else:
            self.logger.error('No cluster is available.')
            response = {'message': 'No cluster is available'}
            access_code = 404
        return dumps(response), access_code


    def update_cluster(self, http_request=None):
        """This method will update the cluster information."""
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
                                response = {'message': f'{ipaddress} is an invalid NTP server IP'}
                                access_code = 404
                                return dumps(response), access_code
                        data['ntp_server'] = temp
                    if 'nameserver_ip' in data and data['nameserver_ip']:
                        temp = data['nameserver_ip']
                        temp = temp.replace(' ',',')
                        temp = temp.replace(',,',',')
                        for ipaddress in temp.split(','):
                            if not Helper().check_ip(ipaddress):
                                response = {'message': f'{ipaddress} is an invalid name server IP'}
                                access_code = 404
                                return dumps(response), access_code
                        data['nameserver_ip'] = temp
                    if 'forwardserver_ip' in data and data['forwardserver_ip']:
                        temp = data['forwardserver_ip']
                        temp = temp.replace(' ',',')
                        temp = temp.replace(',,',',')
                        for ipaddress in temp.split(','):
                            if not Helper().check_ip(ipaddress):
                                response = {'message': f'{ipaddress} is an invalid forwarder IP'}
                                access_code = 404
                                return dumps(response), access_code
                        data['forwardserver_ip'] = temp

                    for item in items:
                        if item in data:
                            data[item] = str(data[item]) or items[item]
                            if isinstance(items[item], bool):
                                data[item] = str(Helper().bool_to_string(data[item]))

                    where = [{"column": "id", "value": cluster[0]['id']}]
                    row = Helper().make_rows(data)
                    Database().update('cluster', row, where)
                    Service().queue('dns','restart')
                    response = {'message': 'Cluster updated'}
                    access_code = 204
                else:
                    response = {'message': 'No cluster is available to update'}
                    access_code = 404
            else:
                response = {'message': 'Bad Request; Columns are incorrect'}
                access_code = 400
        else:
            response = {'message': 'Bad Request; Did not received data'}
            access_code = 400
        return dumps(response), access_code
