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
This File is responsible to Check & Perform all bootstrap-related activity.
"""

__author__ = 'Sumit Sharma'
__copyright__ = 'Copyright 2022, Luna2 Project'
__license__ = 'GPL'
__version__ = '2.0'
__maintainer__ = 'Sumit Sharma'
__email__ = 'sumit.sharma@clustervision.com'
__status__ = 'Development'

import subprocess
import threading
import sys
from configparser import RawConfigParser
import os
import time
import hostlist
from common.constant import CONSTANT
from utils.helper import Helper

configParser = RawConfigParser()

TABLES = ['status', 'queue', 'osimage', 'osimagetag', 'nodesecrets', 'nodeinterface', 'bmcsetup','ha', 
          'monitor', 'ipaddress', 'groupinterface', 'roles', 'group', 'network', 'user', 'switch', 
          'otherdevices', 'controller', 'groupsecrets', 'node', 'cluster', 'tracker','dns','journal']

def db_status():
    """
    A validation method to check which db is configured.
    """
    sqlite, read, write = False, False, False
    code = 503
    if CONSTANT['DATABASE']['DRIVER'] == "SQLite3" or CONSTANT['DATABASE']['DRIVER'] == "SQLite":
        sqlite = True
    if sqlite and os.path.isfile(CONSTANT['DATABASE']['DATABASE']):
        if os.access(CONSTANT['DATABASE']['DATABASE'], os.R_OK):
            read = True
            code = 500
            try:
                file = open(CONSTANT['DATABASE']['DATABASE'], "a", encoding='utf-8')
                if file.writable():
                    write = True
                    code = 200
                    file.close()
                    sys.stderr.write("db_status: I can read the database file.\n")
            except Exception as exp:
                sys.stderr.write(f"{CONSTANT['DATABASE']['DATABASE']} has exception {exp}.\n")

            with open(CONSTANT['DATABASE']['DATABASE'],'r', encoding = "ISO-8859-1") as dbfile:
                header = dbfile.read(100)
                if header.startswith('SQLite format 3'):
                    read, write = True, True
                    code = 200
                    sys.stderr.write("db_status: I see SQLite3 header.\n")
                else:
                    read, write = False, False
                    code = 503
                    sys.stderr.write(f"db_status: {CONSTANT['DATABASE']['DATABASE']} is not SQLite3.\n")
        else:
            sys.stderr.write(f"db_status: DATABASE {CONSTANT['DATABASE']['DATABASE']} is not readable.\n")
    else:
        code = 501
        sys.stderr.write(f"db_status: {CONSTANT['DATABASE']['DATABASE']} does not exist.\n")
    if not sqlite:
        try:
            from utils.database import Database
            Database().get_cursor()
            read, write = True, True
            code = 200
            sys.stderr.write("db_status: Successfully tried to test a non-sqlite database\n")
        except Exception as error:
            sys.stderr.write(f"{CONSTANT['DATABASE']['DATABASE']} connection error: {error}.\n")
    response = {
        "driver": CONSTANT['DATABASE']['DRIVER'],
        "database": CONSTANT['DATABASE']['DATABASE'],
        "read": read,
        "write": write
    }
    sys.stderr.write(f"db_status: returning code = [{code}]\n")
    return response, code


def check_db():
    """
    some incredibly ugly stuff happens here
    for now only sqlite is supported as mysql requires a bit more work.... quite a bit.
    """
    status, code = db_status()
    sys.stderr.write(f"Got this back from db_status: {code} {status}\n")
    if code == 200:
        return True
    if code == 501: # means DB does not exist and we will create it
        sys.stderr.write(f"Will try to create {status['database']} with {status['driver']}\n")
        kill = lambda process: process.kill()
        output = None
        if status["driver"] == "SQLite" or status["driver"] == "SQLite3":
            command = f"sqlite3 {status['database']} \"create table init (id int); drop table init;\""
            my_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            my_timer = threading.Timer(10,kill,[my_process])
            try:
                my_timer.start()
                output = my_process.communicate()
                exit_code = my_process.wait()
            finally:
                my_timer.cancel()

            if exit_code == 0:
                return True
    return False

# --------------------------------------------------------------------------------
# Key call as we cannot import anything until we know for sure we have a database!
# --------------------------------------------------------------------------------
if check_db():
    from common.database_layout import *
    from utils.helper import Helper
    from utils.database import Database
    from utils.log import Log
    LOGGER = Log.get_logger()
else:
    sys.stderr.write("ERROR: i cannot initialize my database. This is fatal.\n")
    exit(127)


def check_db_tables():
    """
    This method will check whether the database is empty or not.
    """
    num = 0
    for table in TABLES:
        #result = Database().get_record(None, table, None)
        dbcolumns = Database().get_columns(table)
        if dbcolumns:
            num = num+1
            layout = get_database_tables_structure(table=table)
            for column in layout:
                if column['column'] not in dbcolumns:
                    LOGGER.error(f"fix database: column {column['column']} not found in table {table} and will be added")
                    Database().add_column(table, column)
        else:
            LOGGER.error(f'Database table {table} does not seem to exist and will be created')
            layout = get_database_tables_structure(table=table)
            Database().create(table, layout)
    if num == 0:
        # if we reach here this means nothing was there.
        return False
    return True


def create_database_tables(table=None):
    """
    This method will create DB table
    """
    for table in TABLES:
        layout = get_database_tables_structure(table=table)
        Database().create(table, layout)


def get_database_tables_structure(table=None):
    if not table:
        return
    if table == "status":
        return DATABASE_LAYOUT_status
    if table == "queue":
        return DATABASE_LAYOUT_queue
        #left in as an example what could be done - Antoine
        #Database().create("queue", DATABASE_LAYOUT_queue)
    if table == "osimage":
        return DATABASE_LAYOUT_osimage
    if table == "osimagetag":
        return DATABASE_LAYOUT_osimagetag
    if table == "nodesecrets":
        return DATABASE_LAYOUT_nodesecrets
    if table == "nodeinterface":
        return DATABASE_LAYOUT_nodeinterface
    if table == "bmcsetup":
        return DATABASE_LAYOUT_bmcsetup
    if table == "monitor":
        return DATABASE_LAYOUT_monitor
    if table == "ipaddress":
        return DATABASE_LAYOUT_ipaddress
    if table == "groupinterface":
        return DATABASE_LAYOUT_groupinterface
    if table == "roles":
        return DATABASE_LAYOUT_roles
    if table == "group":
        return DATABASE_LAYOUT_group
    if table == "network":
        return DATABASE_LAYOUT_network
    if table == "user":
        return DATABASE_LAYOUT_user
    if table == "switch":
        return DATABASE_LAYOUT_switch
    if table == "otherdevices":
        return DATABASE_LAYOUT_otherdevices
    if table == "controller":
        return DATABASE_LAYOUT_controller
    if table == "groupsecrets":
        return DATABASE_LAYOUT_groupsecrets
    if table == "node":
        return DATABASE_LAYOUT_node
    if table == "cluster":
        return DATABASE_LAYOUT_cluster
    if table == "tracker":
        return DATABASE_LAYOUT_tracker
    if table == "dns":
        return DATABASE_LAYOUT_dns
    if table == "journal":
        return DATABASE_LAYOUT_journal
    if table == "ha":
        return DATABASE_LAYOUT_ha


def cleanup_queue_and_status():
    """
    This method will clean the Queue"""
    Database().clear('queue',"subsystem!='housekeeper'") # we exclude housekeeper tasks being removed
    Database().clear('status')


def get_config(filename=None):
    """
    From ini file Section Name is a section here, Option Name is an
    option here and Option Value is an item here.
    Example: sections[HOSTS, NETWORKS], options[HOSTNAME, NODELIST],
    and values of options are item(10.141.255.254, node[001-004])
    CONTROLLER  = controller.cluster:10.141.255.251  <---- virtual IP
    CONTROLLER1 = controller1.cluster:10.141.255.254
    CONTROLLER2 = None
    """
    configParser.read(filename)
    Helper().check_section(filename, BOOTSTRAP)
    for section in configParser.sections():
        for (option, item) in configParser.items(section):
            globals()[option.upper()] = item
            if section in list(BOOTSTRAP.keys()):
                # commented out as it doesn't work as intended. pending
                #Helper().check_option(filename, section, option.upper(), BOOTSTRAP)
                LOGGER.info(f"SECTION: {section.upper()}, OPTION: {option.upper()}, ITEM: {item}")
                if option.upper() == 'CONTROLLER':
                    hostname,ip,*_=item.split(':')+[None]
                    hostname,*_=hostname.split('.')+[None]
                    if hostname and not ip and '.' in hostname:
                        # i guess we only have an IP and no hostname?
                        ip=hostname
                        hostname=option.lower()
                    if Helper().check_ip(ip):
                        BOOTSTRAP[section]['CONTROLLER'] = {}
                        BOOTSTRAP[section]['CONTROLLER']['IP'] = ip
                        BOOTSTRAP[section]['CONTROLLER']['HOSTNAME'] = hostname
                        LOGGER.info(f"CONTROLLER: {BOOTSTRAP[section]['CONTROLLER']}")
                elif option.upper() == 'NODELIST':
                    ### TODO Nodelist also check for the length
                    try:
                        item = hostlist.expand_hostlist(item)
                        BOOTSTRAP[section][option.upper()] = item
                    except Exception:
                        LOGGER.error(f'Invalid node list range: {item}, kindly use the numbers in incremental order.')
                elif 'NETWORKS' in section:
                    function,nwtype,network,dhcp,dhcprange,shared,*_ = item.split(':')+[None]+[None]+[None]+[None]+[None]
                    #Helper().get_netmask(item)  # <-- not used?
                    BOOTSTRAP[section][option.lower()]={}
                    BOOTSTRAP[section][option.lower()]['NETWORK'] = network
                    BOOTSTRAP[section][option.lower()]['TYPE'] = nwtype
                    BOOTSTRAP[section][option.lower()]['FUNCTION'] = function
                    if dhcp:
                        BOOTSTRAP[section][option.lower()]['DHCP'] = 1
                        if dhcprange:
                            BOOTSTRAP[section][option.lower()]['RANGE'] = dhcprange
                    if shared:
                        BOOTSTRAP[section][option.lower()]['SHARED'] = shared
                else:
                    skip=False
                    for num in range(1, 10):
                        if 'CONTROLLER'+str(num) in option.upper():
                            skip=True
                            if 'HA' not in BOOTSTRAP.keys():
                                BOOTSTRAP['HA']={}
                            BOOTSTRAP['HA']['ENABLED']=True
                            BOOTSTRAP[section]['CONTROLLER'+str(num)]={}
                            hostname,ip,*_=item.split(':')+[None]
                            hostname,*_=hostname.split('.')+[None]
                            # we don't expect a fqdn anywhere in the code!
                            # we generally look for 'controller'. BEWARE!
                            if hostname and not ip and '.' in hostname:
                                # i guess we only have an IP and no hostname?
                                ip=hostname
                                hostname=option.lower()
                            if Helper().check_ip(ip):
                                BOOTSTRAP[section]['CONTROLLER'+str(num)]['IP'] = ip
                                BOOTSTRAP[section]['CONTROLLER'+str(num)]['HOSTNAME'] = hostname
                                LOGGER.info(f"CONTROLLER{num}: {BOOTSTRAP[section]['CONTROLLER'+str(num)]}")
                    if not skip:
                        BOOTSTRAP[section][option.upper()] = item
                        LOGGER.info(f"DEVNULL1: {option.upper()}: {item}")
            else:
                BOOTSTRAP[section] = {}
                BOOTSTRAP[section][option.upper()] = item
                LOGGER.info(f"DEVNULL2: {option.upper()}: {item}")


def bootstrap(bootstrapfile=None):
    """
    Insert default data into the database.
    """
    get_config(bootstrapfile)
    LOGGER.info('###################### Bootstrap Start ######################')
#   below no longer needed but kept for old-time sake
#    create_database_tables()

    plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIR"]
    group_plugins = Helper().plugin_finder(f'{plugins_path}/group')
    group_plugin=Helper().plugin_load(group_plugins,'group','default')
    node_plugins = Helper().plugin_finder(f'{plugins_path}/node')
    node_plugin=Helper().plugin_load(node_plugins,'node','default')

    ha_enabled = 0
    if 'HA' in BOOTSTRAP.keys() and BOOTSTRAP['HA']['ENABLED'] is True:
        ha_enabled = 1
    ha_state = [{'column': 'enabled', 'value': ha_enabled},
                {'column': 'syncimages', 'value': '1'},
                {'column': 'insync', 'value': '0'},
                {'column': 'overrule', 'value': '0'},
                {'column': 'master', 'value': '0'}]
    Database().insert('ha', ha_state)

    defaultserver_ip=None
    if 'CONTROLLER' in BOOTSTRAP['HOSTS'].keys():  # the virtual host+ip
        defaultserver_ip=BOOTSTRAP['HOSTS']['CONTROLLER']['IP']
    default_cluster = [
            {'column': 'name', 'value': 'mycluster'},
            {'column': 'technical_contacts', 'value': 'root@localhost'},
            {'column': 'provision_method', 'value': 'torrent'},
            {'column': 'provision_fallback', 'value': 'http'},
            {'column': 'security', 'value': '0'},
            {'column': 'debug', 'value': '0'},
            {'column': 'createnode_ondemand', 'value': '1'},
            {'column': 'nextnode_discover', 'value': '0'},
            {'column': 'nameserver_ip', 'value': defaultserver_ip},
            {'column': 'ntp_server', 'value': defaultserver_ip}
        ]
    Database().insert('cluster', default_cluster)
    cluster = Database().get_record(None, 'cluster', None)
    clusterid = cluster[0]['id']
    network_functions={}
    for nwkx in BOOTSTRAP['NETWORKS'].keys():
        if BOOTSTRAP['NETWORKS'][nwkx] is None:
            continue
        nwtype = BOOTSTRAP['NETWORKS'][nwkx]['TYPE']
        network_functions[BOOTSTRAP['NETWORKS'][nwkx]['FUNCTION']] = nwkx
        network_details=Helper().get_network_details(BOOTSTRAP['NETWORKS'][nwkx]['NETWORK'])
        defaultgw_ip=None
        defaultgw_metric=None
        valid_ip = Helper().check_ip_range(
            defaultserver_ip,
            f"{network_details['network']}/{network_details['subnet']}"
        )
        if valid_ip:
            defaultgw_ip=defaultserver_ip
            defaultgw_metric="101"
        dhcp,dhcp_range_begin,dhcp_range_end=0,None,None
        if 'DHCP' in BOOTSTRAP['NETWORKS'][nwkx]:
            dhcp=1
            if 'RANGE' in BOOTSTRAP['NETWORKS'][nwkx]:
                dhcp_range_begin,dhcp_range_end,*_=BOOTSTRAP['NETWORKS'][nwkx]['RANGE'].split('-')+[None]
                if dhcp_range_end is None:
                    dhcp_range_begin=''
                    dhcp_range_end=''
        shared=None
        if 'SHARED' in BOOTSTRAP['NETWORKS'][nwkx]:
            shared=BOOTSTRAP['NETWORKS'][nwkx]['SHARED']
        default_network = [
                {'column': 'name', 'value': str(nwkx)},
                {'column': 'network', 'value': network_details['network']},
                {'column': 'subnet', 'value': network_details['subnet']},
                {'column': 'dhcp', 'value': dhcp},
                {'column': 'dhcp_range_begin', 'value': dhcp_range_begin},
                {'column': 'dhcp_range_end', 'value': dhcp_range_end},
                {'column': 'gateway', 'value': defaultgw_ip},
                {'column': 'gateway_metric', 'value': defaultgw_metric},
                {'column': 'shared', 'value': shared},
                {'column': 'zone', 'value': 'internal'},
                {'column': 'type', 'value': nwtype}
            ]
        Database().insert('network', default_network)
    networkid, networkname, bmcnetworkid, bmcnetworkname = None, None, None, None
    network = None
    if 'default' in network_functions:
        network = Database().get_record(None,'network',f"WHERE name = '{network_functions['default']}'")
    else:
        #dangerous assumption as id[0] doesn't have to be the primary network but we need to fallback onto something.
        network = Database().get_record(None, 'network', "WHERE name = 'cluster'")
    if network:
        networkid = network[0]['id']
        networkname = network[0]['name']
    if 'bmc' in network_functions:
        network = Database().get_record(None,'network',f"WHERE name = '{network_functions['bmc']}'")
    else:
        # also a bit dangerous but no choice
        network = Database().get_record(None,'network',"WHERE name = 'ipmi'")
    if network:
        bmcnetworkid = network[0]['id']
        bmcnetworkname = network[0]['name']

    # -------------------
    # section here to add the virtual controller named "controller"
    # Added. we are very flexible, as long as at least one host is called 'controller'(.cluster?)
    # ------------------
    """
    CONTROLLER  = controller.cluster:10.141.255.251  <---- virtual IP
    CONTROLLER1 = controller1.cluster:10.141.255.254
    CONTROLLER2 = None
    """
    taken_ips=[]
    bmctaken_ips=[]
    if 'CONTROLLER' in BOOTSTRAP['HOSTS'].keys():  # the virtual host+ip
        hostname=BOOTSTRAP['HOSTS']['CONTROLLER']['HOSTNAME']
        ip=BOOTSTRAP['HOSTS']['CONTROLLER']['IP']
        taken_ips.append(ip)
        default_controller = [
            {'column': 'hostname', 'value': hostname},
            {'column': 'serverport', 'value': BOOTSTRAP['HOSTS']['SERVERPORT']},
            {'column': 'clusterid', 'value': clusterid}
        ]
        controller_id=Database().insert('controller', default_controller)
        if controller_id:
            controller_ip = [
                {'column': 'tableref', 'value': 'controller'},
                {'column': 'tablerefid', 'value': controller_id},
                {'column': 'ipaddress', 'value': ip},
                {'column': 'networkid', 'value': networkid}
            ]
            Database().insert('ipaddress', controller_ip)
    for num in range(1, 10):
        if 'CONTROLLER'+str(num) in BOOTSTRAP['HOSTS'].keys():
            LOGGER.info(f"FOR DB: controller{num}: {BOOTSTRAP['HOSTS']['CONTROLLER'+str(num)]}")
            hostname=BOOTSTRAP['HOSTS']['CONTROLLER'+str(num)]['HOSTNAME']
            ip=BOOTSTRAP['HOSTS']['CONTROLLER'+str(num)]['IP']
            taken_ips.append(ip)
            other_controller = [
                {'column': 'hostname', 'value': hostname},
                {'column': 'serverport', 'value': BOOTSTRAP['HOSTS']['SERVERPORT']},
                {'column': 'clusterid', 'value': clusterid}
            ]
            controller_id=Database().insert('controller', other_controller)
            if controller_id:
                controller_ip = [
                    {'column': 'tableref', 'value': 'controller'},
                    {'column': 'tablerefid', 'value': controller_id},
                    {'column': 'ipaddress', 'value': ip},
                    {'column': 'networkid', 'value': networkid}
                ]
                Database().insert('ipaddress', controller_ip)

    osimage_path,osimage_kernelversion=None,None
    if 'PATH' in BOOTSTRAP['OSIMAGE']:
        osimage_path=BOOTSTRAP['OSIMAGE']['PATH']
        osimage_kernelversion, exit_code = Helper().runcommand(f"ls -tr {osimage_path}/lib/modules/|tail -n1")
        osimage_kernelversion=osimage_kernelversion.strip()
        osimage_kernelversion=osimage_kernelversion.decode('utf-8')
    default_osimage = [
        {'column': 'name', 'value': str(BOOTSTRAP['OSIMAGE']['NAME'])},
        {'column': 'grab_filesystems', 'value': '/, /boot'},
        {'column': 'grab_exclude', 'value': '/proc/*, /sys/*, /dev/*, /tmp/*, /var/log/*'},
        {'column': 'kernelversion', 'value': f'{osimage_kernelversion}'},
        {'column': 'path', 'value': f'{osimage_path}'},
        {'column': 'kernelmodules', 'value': 'ipmi_devintf, ipmi_si, ipmi_msghandler'},
        {'column': 'distribution', 'value': 'redhat'}
     ]
    osimage = Database().insert('osimage', default_osimage)
#    ubuntu_path = None
#    if 'FILES' in CONSTANT and 'IMAGE_DIRECTORY' in CONSTANT['FILES']:
#        ubuntu_path = CONSTANT['FILES']['IMAGE_DIRECTORY'] + '/ubuntu'
#    ubuntu_osimage = [
#        {'column': 'name', 'value': 'ubuntu'},
#        {'column': 'grab_filesystems', 'value': '/, /boot'},
#        {'column': 'grab_exclude', 'value': '/proc/*, /sys/*, /dev/*, /tmp/*, /var/log/*'},
#        {'column': 'kernelversion', 'value': ''},
#        {'column': 'path', 'value': f'{ubuntu_path}'},
#        {'column': 'kernelmodules', 'value': 'ipmi_devintf, ipmi_si, ipmi_msghandler'},
#        {'column': 'distribution', 'value': 'ubuntu'}
#     ]
#    ubuntu = Database().insert('osimage', ubuntu_osimage)

    default_group = [
            {'column': 'name', 'value': str(BOOTSTRAP['GROUPS']['NAME'])},
            {'column': 'setupbmc', 'value': '1'},
            {'column': 'bmcsetupid', 'value': '1'},
            {'column': 'domain', 'value': 'cluster'},
            {'column': 'netboot', 'value': '1'},
            {'column': 'localinstall', 'value': '0'},
            {'column': 'bootmenu', 'value': '0'},
            {'column': 'osimageid', 'value': osimage},
            {'column': 'partscript', 'value': "bW91bnQgLXQgdG1wZnMgdG1wZnMgL3N5c3Jvb3QK"},
            {'column': 'postscript', 'value': "ZWNobyAndG1wZnMgLyB0bXBmcyBkZWZhdWx0cyAwIDAnID4+IC9zeXNyb290L2V0Yy9mc3RhYgo="}
        ]
    Database().insert('group', default_group)

    # we call create plugin after group creation
    try:
        group_plugin().postcreate(name=str(BOOTSTRAP['GROUPS']['NAME']), nodes=[])
    except Exception as exp:
        LOGGER.error(f"{exp}")
    # ------------------------------------------

#    ubuntu_group = [
#            {'column': 'name', 'value': 'ubuntu'},
#            {'column': 'setupbmc', 'value': '1'},
#            {'column': 'bmcsetupid', 'value': '1'},
#            {'column': 'domain', 'value': 'cluster'},
#            {'column': 'netboot', 'value': '1'},
#            {'column': 'localinstall', 'value': '0'},
#            {'column': 'bootmenu', 'value': '0'},
#            {'column': 'osimageid', 'value': ubuntu},
#            {'column': 'partscript', 'value': "bW91bnQgLXQgdG1wZnMgdG1wZnMgIiRyb290bW50Igo="},
#            {'column': 'postscript', 'value': "ZWNobyB0bXBmcyAvIHRtcGZzIGRlZmF1bHRzIDAgMCA+PiAiJHJvb3RtbnQiL2V0Yy9mc3RhYgo="}
#        ]
#    Database().insert('group', ubuntu_group)
#
#    # we call create plugin after group creation
#    try:
#        group_plugin().postcreate(name='ubuntu', nodes=[])
#    except Exception as exp:
#        LOGGER.error(f"{exp}")
#    # ------------------------------------------

    group = Database().get_record(None, 'group', None)
    groupid = group[0]['id']
    groupname = group[0]['name']
    for nodex in BOOTSTRAP['HOSTS']['NODELIST']:
        default_node = [
            {'column': 'name', 'value': str(nodex)},
            {'column': 'groupid', 'value': str(groupid)},
            {'column': 'service', 'value': '0'},
        ]
        node_id = Database().insert('node', default_node)

        # we call create plugin after node creation
        try:
            node_plugin().postcreate(name=str(nodex), group=groupname)
        except Exception as exp:
            LOGGER.error(f"{exp}")
        # ------------------------------------------

        network_details=Helper().get_network_details(BOOTSTRAP['NETWORKS'][networkname]['NETWORK'])
        avail_ip = Helper().get_available_ip(network_details['network'],
                                             network_details['subnet'],
                                             taken_ips)
        taken_ips.append(avail_ip)
        default_int = [
            {'column': 'nodeid', 'value': str(node_id)},
            {'column': 'interface', 'value': 'BOOTIF'}
        ]
        if_id = Database().insert('nodeinterface', default_int)
        default_ip = [
            {'column': 'tableref', 'value': 'nodeinterface'},
            {'column': 'tablerefid', 'value': str(if_id)},
            {'column': 'ipaddress', 'value': str(avail_ip)},
            {'column': 'networkid', 'value': networkid}
        ]
        #ip_id = Database().insert('ipaddress', default_ip)
        Database().insert('ipaddress', default_ip)

        bmcnetwork_details = Helper().get_network_details(BOOTSTRAP['NETWORKS'][bmcnetworkname]['NETWORK'])
        avail_ip = Helper().get_available_ip(bmcnetwork_details['network'],network_details['subnet'],bmctaken_ips)
        bmctaken_ips.append(avail_ip)
        bmc_int = [
            {'column': 'nodeid', 'value': str(node_id)},
            {'column': 'interface', 'value': 'BMC'}
        ]
        bmcif_id = Database().insert('nodeinterface', bmc_int)
        bmc_ip = [
            {'column': 'tableref', 'value': 'nodeinterface'},
            {'column': 'tablerefid', 'value': str(bmcif_id)},
            {'column': 'ipaddress', 'value': str(avail_ip)},
            {'column': 'networkid', 'value': bmcnetworkid}
        ]
        Database().insert('ipaddress', bmc_ip)

    default_group_interface = [
        {'column': 'groupid', 'value': '1'},
        {'column': 'interface', 'value': 'BOOTIF'},
        {'column': 'networkid', 'value': networkid}
    ]
    bmc_group_interface = [
        {'column': 'groupid', 'value': '1'},
        {'column': 'interface', 'value': 'BMC'},
        {'column': 'networkid', 'value': bmcnetworkid}
    ]

    bmcsetup_name='compute'
    if 'NAME' in BOOTSTRAP['BMCSETUP'] and BOOTSTRAP['BMCSETUP']['NAME']:
        bmcsetup_name=str(BOOTSTRAP['BMCSETUP']['NAME'])
    default_bmcsetup = [
        {'column': 'name', 'value': bmcsetup_name},
        {'column': 'userid', 'value': '2'},
        {'column': 'netchannel', 'value': '1'},
        {'column': 'mgmtchannel', 'value': '1'},
        {'column': 'username', 'value': str(BOOTSTRAP['BMCSETUP']['USERNAME'])},
        {'column': 'password', 'value': str(BOOTSTRAP['BMCSETUP']['PASSWORD'])}
    ]

    default_switch = [
        {'column': 'name', 'value': 'switch01'},
        {'column': 'oid', 'value': '.1.3.6.1.2.1.17.7.1.2.2.1.2'},
        {'column': 'read', 'value': 'public'},
        {'column': 'rw', 'value': 'trusted'}
    ]

    Database().insert('groupinterface', default_group_interface)
    Database().insert('groupinterface', bmc_group_interface)
    Database().insert('bmcsetup', default_bmcsetup)
    Database().insert('switch', default_switch)
    current_time = str(time.time()).replace('.', '')
    new_bootstrapfile = f'/trinity/local/luna/daemon/config/bootstrap-{current_time}.ini'
    os.rename(bootstrapfile, new_bootstrapfile)
    LOGGER.info('###################### Bootstrap Finish ######################')
    return True


def validate_bootstrap():
    """
    The main method should be called from outside.
    To perform and check the bootstrap.
    """
    bootstrapfile = '/trinity/local/luna/daemon/config/bootstrap.ini'
    global BOOTSTRAP
    BOOTSTRAP = {
        'HOSTS': {'HOSTNAME': None, 'CONTROLLER': None, 'NODELIST': None, 'PRIMARY_DOMAIN': None},
        'NETWORKS': {'cluster': None, 'ipmi': None, 'ib': None},
        'GROUPS': {'NAME': None},
        'OSIMAGE': {'NAME': None},
        'BMCSETUP': {'USERNAME': None, 'PASSWORD': None}
    }
    bootstrapfile_check = Helper().check_path_state(bootstrapfile)
    db_check=check_db()
    if db_check is True:
        db_tables_check=check_db_tables()

    LOGGER.info(f'db_check = [{db_check}], db_tables_check = [{db_tables_check}]')
    if bootstrapfile_check is True and db_check is True:
        if db_tables_check is False:
            bootstrap(bootstrapfile)
        else:
            LOGGER.warning(f'{bootstrapfile} is still present, Kindly remove the file.')
    elif db_check is False:
        LOGGER.error('Database is unavailable.')
        return False
    elif db_tables_check is False:
        LOGGER.error('Database requires initialization but bootstrap.ini file is missing.')
        return False

    cleanup_queue_and_status()
    return True
