#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Network Class will handle all network operations.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

from json import dumps
from concurrent.futures import ThreadPoolExecutor
from utils.queue import Queue
from utils.database import Database
from utils.log import Log
from utils.helper import Helper
from utils.config import Config
from utils.service import Service


class Network():
    """
    This class is responsible for all operations for network.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()


    def get_all_networks(self):
        """
        This method will return all the network in detailed format.
        """
        networks = Database().get_record(None, 'network', None)
        if networks:
            response = {'config': {'network': {} }}
            for network in networks:
                network['network'] = Helper().get_network(network['network'], network['subnet'])
                del network['id']
                del network['subnet']
                network['dhcp'] = Helper().make_bool(network['dhcp'])
                if not network['dhcp']:
                    del network['dhcp_range_begin']
                    del network['dhcp_range_end']
                    network['dhcp'] = False
                else:
                    network['dhcp'] = True
                response['config']['network'][network['name']] = network
            access_code = 200
        else:
            self.logger.error('No networks is available.')
            response = {'message': 'No networks is available'}
            access_code = 404
        return dumps(response), access_code


    def get_network(self, name=None):
        """
        This method will return requested network in detailed format.
        """
        networks = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
        if networks:
            response = {'config': {'network': {} }}
            for network in networks:
                network['network'] = Helper().get_network(network['network'], network['subnet'])
                del network['id']
                del network['subnet']
                network['dhcp'] = Helper().make_bool(network['dhcp'])
                if not network['dhcp']:
                    del network['dhcp_range_begin']
                    del network['dhcp_range_end']
                    network['dhcp'] = False
                else:
                    network['dhcp'] = True
                response['config']['network'][name] = network
            access_code = 200
        else:
            self.logger.error(f'Network {name} is not available.')
            response = {'message': f'Network {name} is not available'}
            access_code = 404
        return dumps(response), access_code


    def update_network(self, name=None, http_request=None):
        """
        This method will create or update a network.
        """
        data = {}
        create, update = False, False
        request_data = http_request.data
        if request_data:
            data = request_data['config']['network'][name]
            data['name'] = name
            network = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
            if network:
                networkid = network[0]['id']
                if 'newnetname' in request_data['config']['network'][name]:
                    newnetname = request_data['config']['network'][name]['newnetname']
                    where = f' WHERE `name` = "{newnetname}"'
                    check_network = Database().get_record(None, 'network', where)
                    if check_network:
                        response = {'message': f'{newnetname} already present in database'}
                        access_code = 404
                        return dumps(response), access_code
                    else:
                        data['name'] = data['newnetname']
                        del data['newnetname']
                update = True
            else:
                create = True
            used_ips, dhcp_size, redistribute_ipaddress = 0, 0, None
            if 'network' in data:
                network_ip = Helper().check_ip(data['network'])
                if network_ip:
                    network_details = Helper().get_network_details(data['network'])
                    data['network'] = network_ip
                    data['subnet'] = network_details['subnet']
                    used_ips = Helper().get_quantity_occupied_ipaddress_in_network(name)
                    if network:
                        if (network[0]['network'] != data['network']) or (network[0]['subnet'] != data['subnet']):
                            redistribute_ipaddress = True
                            self.logger.info("We will redistribute ip addresses")
                            if 'gateway' not in data:
                                data['gateway'] = ''
                                # we have to remove the gateway if we did not get a new one and an
                                # existing is in place. should we warn the user? pending
                else:
                    response = {'message': f'Incorrect network IP: {data["network"]}'}
                    access_code = 404
                    return dumps(response), access_code
            elif network:
                # we fetch what we have from the DB
                data['network'] = network[0]['network']
                data['subnet'] = network[0]['subnet']
            else:
                message = 'Not enough details provided. network/subnet in CIDR notation expected'
                response = {'message': message}
                access_code = 404
                return dumps(response), access_code
            if 'gateway' in data:
                gateway_details = Helper().check_ip_range(
                    data['gateway'],
                    data['network'] + '/' + data['subnet']
                )
                if (not gateway_details) and data['gateway'] != '':
                    response = {'message': f'Incorrect gateway IP: {data["gateway"]}'}
                    access_code = 404
                    return dumps(response), access_code
            if 'nameserver_ip' in data:
                nsip_details = Helper().check_ip_range(
                    data['nameserver_ip'],
                    data['network'] + '/' + data['subnet']
                )
                if (not nsip_details) and data['nameserver_ip'] != '':
                    response = {'message': f'Incorrect Nameserver IP: {data["nameserver_ip"]}'}
                    access_code = 404
                    return dumps(response), access_code
            if 'ntp_server' in data:
                subnet = data['network'] + '/' + data['subnet']
                ntp_details = Helper().check_ip_range(data['ntp_server'], subnet)
                if (not ntp_details) and data['ntp_server'] != '':
                    response = {'message': f'Incorrect NTP Server IP: {data["ntp_server"]}'}
                    access_code = 404
                    return dumps(response), access_code
            if 'dhcp' in data:
                data['dhcp'] = Helper().bool_to_string(data['dhcp'])
                self.logger.info(f"dhcp is set to {data['dhcp']}")
                if 'dhcp_range_begin' in data:
                    subnet = data['network']+'/'+data['subnet']
                    dhcp_start_details = Helper().check_ip_range(data['dhcp_range_begin'], subnet)
                    if not dhcp_start_details:
                        response = {'message': f'Incorrect dhcp start: {data["dhcp_range_begin"]}'}
                        access_code = 404
                        return dumps(response), access_code
                elif data['dhcp'] != "0":
                    response = {'message': 'DHCP start range is a required parameter'}
                    access_code = 400
                    return dumps(response), access_code
                if 'dhcp_range_end' in data:
                    subnet = data['network']+'/'+data['subnet']
                    dhcp_end_details = Helper().check_ip_range(data['dhcp_range_end'], subnet)
                    if not dhcp_end_details:
                        response = {'message': f'Incorrect dhcp end: {data["dhcp_range_end"]}'}
                        access_code = 404
                        return dumps(response), access_code
                elif data['dhcp'] != "0":
                    response = {'message': 'DHCP end range is a required parameter'}
                    access_code = 400
                    return dumps(response), access_code
                if data['dhcp'] == "1":
                    dhcp_size = Helper().get_ip_range_size(
                        data['dhcp_range_begin'],
                        data['dhcp_range_end']
                    )
                    redistribute_ipaddress = True
                    # to make sure we do not overlap with existing node ip configs
            else:
                if network:
                    data['dhcp'] = network[0]['dhcp']
                    data['dhcp_range_begin'] = network[0]['dhcp_range_begin']
                    data['dhcp_range_end'] = network[0]['dhcp_range_end']
                    dhcp_size = Helper().get_ip_range_size(
                        data['dhcp_range_begin'],
                        data['dhcp_range_end']
                    )
                else:
                    data['dhcp'] = 0
                    data['dhcp_range_begin'] = ""
                    data['dhcp_range_end'] = ""

            network_columns = Database().get_columns('network')
            column_check = Helper().compare_list(data, network_columns)
            if column_check:
                row = Helper().make_rows(data)
                if create:
                    Database().insert('network', row)
                    response = {'message': f'Network {name} created successfully'}
                    access_code = 201
                if update:
                    if redistribute_ipaddress:
                        nwk_size = Helper().get_network_size(data['network'], data['subnet'])
                        avail = nwk_size - dhcp_size
                        if avail < used_ips:
                            message = f'The proposed network config allows for {nwk_size} ip '
                            message += f'addresses. DHCP range will occupy {dhcp_size} ip '
                            message += 'addresses. The request will not accomodate for the '
                            message += f'currently  {used_ips} in use ip addresses.'
                            response = {'message': message}
                            access_code = 404
                            return dumps(response), access_code
                    where = [{"column": "id", "value": networkid}]
                    Database().update('network', row, where)
                    # TWANNIE
                    if redistribute_ipaddress:
                        Config().update_dhcp_range_on_network_change(name)
                        # below section takes care (in the background), adding/renaming/deleting.
                        # for adding next free ip-s will be selected.
                        # time consuming therefor background
                        queue_id, _ = Queue().add_task_to_queue(
                            f'update_all_interface_ipaddress:{name}',
                            'network_change'
                        )
                        next_id = Queue().next_task_in_queue('network_change')
                        if queue_id == next_id:
                            executor = ThreadPoolExecutor(max_workers=1)
                            executor.submit(
                                Config().update_interface_ipaddress_on_network_change,
                                name
                            )
                            executor.shutdown(wait=False)
                            # Config().update_interface_ipaddress_on_network_change(name)
                    response = {'message': f'Network {name} updated successfully'}
                    access_code = 204
                Service().queue('dns','restart')
                Service().queue('dhcp','restart')
                # technically only needed when dhcp changes, but it doesn't hurt to just do it
            else:
                response = {'message': 'Columns are incorrect'}
                access_code = 400
                return dumps(response), access_code
        else:
            response = {'message': 'Did not received data'}
            access_code = 400
            return dumps(response), access_code
        return dumps(response), access_code


    def delete_network(self, name=None):
        """
        This method will delete a network.
        """
        network = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
        if network:
            Database().delete_row('network', [{"column": "name", "value": name}])
            Service().queue('dns','restart')
            response = {'message': 'Network removed'}
            access_code = 204
        else:
            response = {'message': f'Network {name} not present in database'}
            access_code = 404
        return dumps(response), access_code


    def network_ip(self, name=None, ipaddress=None):
        """
        This method will identifies the requested ipaddress is available or not.
        """
        network = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
        if network:
            ip_with_subnet = network[0]['network'] + '/' + network[0]['subnet']
            ip_detail = Helper().check_ip_range(ipaddress, ip_with_subnet)
            if ip_detail:
                where = f' WHERE ipaddress = "{ipaddress}"'
                check_ip = Database().get_record(None, 'ipaddress', where)
                if check_ip:
                    response = {'config': {'network': {ipaddress: {'status': 'taken'} } } }
                    access_code = 200
                else:
                    response = {'config': {'network': {ipaddress: {'status': 'free'} } } }
                    access_code = 200
            else:
                response = {'message': f'{ipaddress} is not in the range'}
                access_code = 404
                return dumps(response), access_code
        else:
            response = {'message': f'Network {name} not present in database'}
            access_code = 404
        return dumps(response), access_code


    def next_free_ip(self, name=None):
        """
        This method will identify the next available ipaddress on a network.
        """
        response = {'message': f'Network {name} not present in database'}
        access_code = 404
        #Antoine
        ips = Config().get_all_occupied_ips_from_network(name)
        network = Database().get_record(None, 'network', f' WHERE `name` = "{name}"')
        avail = None
        if network:
            response = {'message': f'Network {name} has no free addresses'}
            ret = 0
            max_count = 10
            # we try to ping for 10 ips, if none of these are free, something else is going on
            # (read: rogue devices)....
            while(max_count > 0 and ret != 1):
                avail = Helper().get_available_ip(network[0]['network'], network[0]['subnet'], ips)
                ips.append(avail)
                _,ret = Helper().runcommand(f"ping -w1 -c1 {avail}", True, 3)
                max_count-=1
        if avail:
            response = {'config': {'network': {name: {'nextip': avail} } } }
            access_code = 200
        else:
            response = {'message': f'network {name} does not provide for any free IP address'}
        return dumps(response), access_code


    def taken_ip(self, name=None):
        """
        This method will identify the all taken ipaddress on a network.
        """
        # TODO ->
        # Need to convert in Join query.
        # Get ipaddress from ipaddress table and device name which have the network name provided.
        # device can be node, controller, switch, otherdevices. Remember nodeinterface table.
        taken = []
        network_id = Database().id_by_name('network', name)
        if network_id:
            where = f' WHERE `networkid` = "{network_id}"'
            ip_list = Database().get_record("*", 'ipaddress', where=where)
            if ip_list:
                for each in ip_list:
                    if 'interface' in each['tableref']:
                        tablerefid = each['tablerefid']
                        where = f' WHERE `id` = "{tablerefid}"'
                        nodeid = Database().get_record("*",'nodeinterface', where)
                        nodeid = nodeid[0]['nodeid']
                        device_name = Database().name_by_id('node', nodeid)
                    elif 'controller' in each['tableref']:
                        tablerefid = each['tablerefid']
                        where = f' WHERE `id` = "{tablerefid}"'
                        hostname = Database().get_record("*",'controller', where)
                        self.logger.info(hostname)
                        if hostname:
                            device_name = hostname[0]['hostname']
                        else:
                            device_name = "Controller has No Hostname"
                    else:
                        device_name = Database().name_by_id(each['tableref'], each['tablerefid'])
                    taken.append({'ipaddress': each['ipaddress'], 'device': device_name})
                    device_name = ""
                response = {'config': {'network': {name: {'taken': taken} } } }
                access_code = 200
                self.logger.info(response)
            else:
                response = {'message': f'All IP Address are free on Network {name}. None is Taken.'}
                access_code = 404

        else:
            response = {'message': f'Network {name} not present in database.'}
            access_code = 404
        return dumps(response), access_code
