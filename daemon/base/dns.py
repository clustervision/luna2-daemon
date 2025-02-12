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
Network Class will handle all network operations.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from utils.queue import Queue
from utils.database import Database
from utils.log import Log
from utils.helper import Helper
from utils.service import Service


class DNS():
    """
    This class is responsible for all additional DNS related matter.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()



    def get_dns(self, name=None):
        """
        This method will return requested additional dns record for the network.
        """
        status=False
        response=f"No entries for network {name}"
        dns = Database().get_record_join(['dns.*'],['dns.networkid=network.id'],[f"network.name='{name}'"])

        if dns:
            status=True
            response = {'config': {'dns': {name: [] }}}
            data=[]
            for host in dns:
                response['config']['dns'][name].append({ "host": host['host'], "ipaddress": host['ipaddress'] })
        else:
            network = Database().get_record(None, "network", f"WHERE `name`='{name}'")
            if not network:
                status=False
                response=f"Network {name} does not exist"
        return status, response


    def update_dns(self, name=None, request_data=None):
        """
        This method will create or update additional dns hosts for a network.
        """
        status=True
        response="Internal error"
        data = {}
        if request_data:
            data = request_data['config']['dns'][name]
            network = Database().get_record(None, "network", f"WHERE `name`='{name}'")
            if network:
                status=True
                response='DNS entries added or changed'
                networkid=network[0]['id']
                for entry in data:
                    if 'host' in entry and 'ipaddress' in entry:
                        host=entry['host']
                        ipaddress=entry['ipaddress']
                        valid_ip = Helper().check_ip(ipaddress)
                        if valid_ip:
                            ndata={}
                            ndata['host']=host
                            ndata['ipaddress']=ipaddress
                            ndata['networkid']=networkid
                            row = Helper().make_rows(ndata)
                            exist = Database().get_record(None, "dns", f"WHERE `host`='{host}' AND `networkid`='{networkid}'")
                            if exist:
                                where = [{"column": "id", "value": exist[0]['id']}]
                                Database().update('dns', row, where)
                            else:
                                Database().insert('dns', row)
                Service().queue('dns','reload')
            else:
                status=False
                response=f'Network {name} not present in database'
        else:
            status=False
            response='Invalid request: Did not receive data'
        return status, response


    def delete_dns(self, name=None, network=None):
        """
        This method deletes a single host entry for a network.
        """
        status=False
        response="Entry does not present in database"
        exist = Database().get_record_join(['dns.*'],['dns.networkid=network.id'],[f"dns.host='{name}'",f"network.name='{network}'"])
        if exist:
            Database().delete_row('dns', [{"column": "id", "value": exist[0]['id']}])
            status=True
            response="Entry removed"
            Service().queue('dns','reload')
        return status, response

