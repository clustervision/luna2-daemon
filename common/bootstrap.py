#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

from configparser import RawConfigParser
import os
import time
import hostlist
import subprocess
import threading
import sys
from common.constant import CONSTANT

configParser = RawConfigParser()

# -----------------------------------------------------------------------------------

def checkdbstatus():
    """
    A validation method to check which db is configured.
    """
    sqlite, read, write = False, False, False
    code = 503
    if CONSTANT['DATABASE']['DRIVER'] == "SQLite":
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
                    sys.stderr.write(f"checkdbstatus: I can read the database file.\n")
            except Exception as exp:
                sys.stderr.write(f"{CONSTANT['DATABASE']['DATABASE']} has exception {exp}.\n")

            with open(CONSTANT['DATABASE']['DATABASE'],'r', encoding = "ISO-8859-1") as dbfile:
                header = dbfile.read(100)
                if header.startswith('SQLite format 3'):
                    read, write = True, True
                    code = 200
                    sys.stderr.write(f"checkdbstatus: I see SQLite3 header.\n")
                else:
                    read, write = False, False
                    code = 503
                    sys.stderr.write(f"checkdbstatus: {CONSTANT['DATABASE']['DATABASE']} is not SQLite3.\n")
        else:
            sys.stderr.write(f"checkdbstatus: DATABASE {CONSTANT['DATABASE']['DATABASE']} is not readable.\n")
    else:
        code = 501
        sys.stderr.write(f"checkdbstatus: {CONSTANT['DATABASE']['DATABASE']} does not exist.\n")
    if not sqlite:
        try:
            from utils.database import Database
            Database().get_cursor()
            read, write = True, True
            code = 200
            sys.stderr.write(f"checkdbstatus: Successfully tried to test a non-sqlite database\n")
        except pyodbc.Error as error:
            sys.stderr.write(f"{CONSTANT['DATABASE']['DATABASE']} connection error: {error}.\n")
    response = {"driver": CONSTANT['DATABASE']['DRIVER'], "database": CONSTANT['DATABASE']['DATABASE'], "read": read, "write": write}
    sys.stderr.write(f"checkdbstatus: returning code = [{code}]\n")
    return response, code

def check_db():
    """
    some incredibly ugly stuff happens here
    for now only sqlite is supported as mysql requires a bit more work.... quite a bit.
    """
    dbstatus, dbcode = checkdbstatus()
    sys.stderr.write(f"Got this back from checkdbstatus: {dbcode} {dbstatus}\n")
    if dbcode == 200:
        return True
    if dbcode == 501: # means DB does not exist and we will create it
        sys.stderr.write(f"Will try to create {dbstatus['database']} with {dbstatus['driver']}\n")
        kill = lambda process: process.kill()
        output = None
        if dbstatus["driver"] == "SQLite":
            my_process = subprocess.Popen(f"sqlite3 {dbstatus['database']} \"create table init (id int); drop table init;\"", stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
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
# --------------------------------------------------------------------------------

def check_db_tables():
    """
    This method will check whether the database is empty or not.
    """
    table = ['cluster', 'bmcsetup', 'group', 'groupinterface', 'groupsecrets', 'status',
             'network', 'osimage', 'switch', 'tracker', 'node', 'nodeinterface', 'nodesecrets']
    num = 0
    for tablex in table:
        result = Database().get_record(None, tablex, None)
        if result:
            num = num+1
        else:
            LOGGER.error(f'ERROR :: Database table {tablex} does not seem to exist.')
    if num == 0:
        return False
    return True


def getconfig(filename=None):
    """
    From ini file Section Name is a section here, Option Name is an
    option here and Option Value is an item here.
    Example: sections[HOSTS, NETWORKS], options[HOSTNAME, NODELIST],
    and vlaues of options are item(10.141.255.254, node[001-004])
    """
    configParser.read(filename)
    Helper().checksection(filename, BOOTSTRAP)
    for section in configParser.sections():
        for (option, item) in configParser.items(section):
            globals()[option.upper()] = item
            if section in list(BOOTSTRAP.keys()):
                Helper().checkoption(filename, section, option.upper(), BOOTSTRAP)
                if 'CONTROLLER1' in option.upper():
                    Helper().check_ip(item)
                    BOOTSTRAP[section][option.upper()] = item
                elif 'CONTROLLER' in option.upper() and 'CONTROLLER1' not in option.upper():
                    if '.' in item:
                        Helper().check_ip(item)
                        BOOTSTRAP[section][option.upper()] = item
                    else:
                        del BOOTSTRAP[section][option.upper()]
                elif 'NODELIST' in option.upper():
                    ### TODO Nodelist also check for the length
                    try:
                        item = hostlist.expand_hostlist(item)
                        BOOTSTRAP[section][option.upper()] = item
                    except Exception:
                        LOGGER.error(f'Invalid node list range: {item}, kindly use the numbers in incremental order.')
                elif 'NETWORKS' in section:
                    Helper().get_subnet(item)
                    BOOTSTRAP[section][option.upper()] = item
                else:
                    BOOTSTRAP[section][option.upper()] = item
            else:
                BOOTSTRAP[section] = {}
                BOOTSTRAP[section][option.upper()] = item


def create_database_tables():
    Database().create("status",DATABASE_LAYOUT_status)
    Database().create("osimage",DATABASE_LAYOUT_osimage)
    Database().create("nodesecrets",DATABASE_LAYOUT_nodesecrets)
    Database().create("nodeinterface",DATABASE_LAYOUT_nodeinterface)
    Database().create("bmcsetup",DATABASE_LAYOUT_bmcsetup)
    Database().create("monitor",DATABASE_LAYOUT_monitor)
    Database().create("ipaddress",DATABASE_LAYOUT_ipaddress)
    Database().create("groupinterface",DATABASE_LAYOUT_groupinterface)
    Database().create("roles",DATABASE_LAYOUT_roles)
    Database().create("group",DATABASE_LAYOUT_group)
    Database().create("network",DATABASE_LAYOUT_network)
    Database().create("user",DATABASE_LAYOUT_user)
    Database().create("switch",DATABASE_LAYOUT_switch)
    Database().create("otherdevices",DATABASE_LAYOUT_otherdevices)
    Database().create("controller",DATABASE_LAYOUT_controller)
    Database().create("groupsecrets",DATABASE_LAYOUT_groupsecrets)
    Database().create("node",DATABASE_LAYOUT_node)
    Database().create("cluster",DATABASE_LAYOUT_cluster)
    Database().create("tracker",DATABASE_LAYOUT_tracker)


def bootstrap(bootstrapfile=None):
    """
    Insert default data into the database.
    """
    getconfig(bootstrapfile)
    LOGGER.info('###################### Bootstrap Start ######################')
    create_database_tables()
    default_cluster = [
            {'column': 'technical_contacts', 'value': 'root@localhost'},
            {'column': 'provision_method', 'value': 'torrent'},
            {'column': 'provision_fallback', 'value': 'http'},
            {'column': 'security', 'value': '1'},
            {'column': 'debug', 'value': '0'}
        ]
    Database().insert('cluster', default_cluster)
    cluster = Database().get_record(None, 'cluster', None)
    clusterid = cluster[0]['id']
    for nwkx in BOOTSTRAP['NETWORKS'].keys():
        default_network = [
                {'column': 'name', 'value': str(nwkx)},
                {'column': 'network', 'value': str(BOOTSTRAP['NETWORKS'][nwkx])},
                {'column': 'dhcp', 'value': '0'},
                {'column': 'ns_hostname', 'value': BOOTSTRAP['HOSTS']['HOSTNAME']},
                {'column': 'ns_ip', 'value': BOOTSTRAP['HOSTS']['CONTROLLER1']},
                {'column': 'gateway', 'value': BOOTSTRAP['HOSTS']['CONTROLLER1']},
                {'column': 'ntp_server', 'value': BOOTSTRAP['HOSTS']['CONTROLLER1']}
            ]
        Database().insert('network', default_network)
    network = Database().get_record(None, 'network', None)
    networkid = network[0]['id']
    num  = 1
    for hosts in BOOTSTRAP['HOSTS']:
        if f'CONTROLLER{num}' in BOOTSTRAP['HOSTS'].keys():
            default_controller = [
                {'column': 'hostname', 'value': BOOTSTRAP['HOSTS']['HOSTNAME']},
                {'column': 'serverport', 'value': BOOTSTRAP['HOSTS']['SERVERPORT']},
                {'column': 'clusterid', 'value': clusterid}
                ]
            controller_id=Database().insert('controller', default_controller)
            if controller_id:
                controller_ip = [
                    {'column': 'tableref', 'value': 'controller'},
                    {'column': 'tablerefid', 'value': controller_id},
                    {'column': 'ipaddress', 'value': BOOTSTRAP['HOSTS'][f'CONTROLLER{num}']}
                ]
                # we did not specify a network! this means that we will not use it. not a biggy but we cannot verify nor use this kind of info --> api/boot.py
                Database().insert('ipaddress', controller_ip)
        num = num + 1
    default_group = [
            {'column': 'name', 'value': str(BOOTSTRAP['GROUPS']['NAME'])},
            {'column': 'bmcsetup', 'value': '1'},
            {'column': 'domain', 'value': 'cluster'},
            {'column': 'netboot', 'value': '1'},
            {'column': 'localinstall', 'value': '0'},
            {'column': 'bootmenu', 'value': '0'},
            {'column': 'provisionmethod', 'value': 'torrent'},
            {'column': 'provisionfallback', 'value': 'http'}
        ]
    Database().insert('group', default_group)
    group = Database().get_record(None, 'group', None)
    groupid = group[0]['id']
    for nodex in BOOTSTRAP['HOSTS']['NODELIST']:
        default_node = [
                {'column': 'name', 'value': str(nodex)},
                {'column': 'groupid', 'value': str(groupid)},
                {'column': 'localboot', 'value': '0'},
                {'column': 'service', 'value': '0'},
                {'column': 'setupbmc', 'value': '1'},
                {'column': 'localinstall', 'value': '0'},
                {'column': 'bootmenu', 'value': '0'},
                {'column': 'netboot', 'value': '1'},
                {'column': 'provisionmethod', 'value': 'torrent'},
                {'column': 'provisionfallback', 'value': 'http'}
            ]
        Database().insert('node', default_node)
    default_group_interface = [
            {'column': 'groupid', 'value': '1'},
            {'column': 'interfacename', 'value': 'BOOTIF'},
            {'column': 'networkid', 'value': networkid}
        ]

    default_osimage = [
            {'column': 'name', 'value': str(BOOTSTRAP['OSIMAGE']['NAME'])},
            {'column': 'dracutmodules', 'value': 'luna, -18n, -plymouth'},
            {'column': 'grab_filesystems', 'value': '/, /boot'},
            {'column': 'initrdfile', 'value': 'osimagename-initramfs-`uname -r`'},
            {'column': 'kernelfile', 'value': 'osimagename-vmlinuz-`uname -r`'},
            {'column': 'kernelmodules', 'value': 'ipmi_devintf, ipmi_si, ipmi_msghandler'},
            {'column': 'distribution', 'value': 'redhat'}
        ]

    default_bmcsetup = [
            {'column': 'username', 'value': str(BOOTSTRAP['BMCSETUP']['USERNAME'])},
            {'column': 'password', 'value': str(BOOTSTRAP['BMCSETUP']['PASSWORD'])}
        ]
    default_switch = [
            {'column': 'name', 'value': 'switch01'},
            {'column': 'oid', 'value': '.1.3.6.1.2.1.17.7.1.2.2.1.2'},
            {'column': 'read', 'value': 'public'},
            {'column': 'rw', 'value': 'private'}
            ]
    
    Database().insert('groupinterface', default_group_interface)
    Database().insert('osimage', default_osimage)
    Database().insert('bmcsetup', default_bmcsetup)
    Database().insert('switch', default_switch)
    current_time = str(time.time()).replace('.', '')
    new_bootstrapfile = f'/trinity/local/luna/config/bootstrap-{current_time}.ini'
    os.rename(bootstrapfile, new_bootstrapfile)
    LOGGER.info('###################### Bootstrap Finish ######################')
    return True


def validatebootstrap():
    """
    The main method should be called from outside.
    To perform and check the bootstrap.
    """
    bootstrapfile = '/trinity/local/luna/config/bootstrap.ini'
    global BOOTSTRAP
    BOOTSTRAP = {
        'HOSTS': {'HOSTNAME': None, 'CONTROLLER1': None, 'CONTROLLER2': None, 'NODELIST': None},
        'NETWORKS': {'INTERNAL': None, 'BMC': None, 'IB': None},
        'GROUPS': {'NAME': None},
        'OSIMAGE': {'NAME': None},
        'BMCSETUP': {'USERNAME': None, 'PASSWORD': None}
    }
    bootstrapfile_check = Helper().checkpathstate(bootstrapfile)
    db_check=check_db()
    if db_check is True:
        db_tables_check=check_db_tables()

    LOGGER.warning(f'db_check = [{db_check}], db_tables_check = [{db_tables_check}]')
    if bootstrapfile_check is True and db_check is True:
        if db_tables_check is False:
            bootstrap(bootstrapfile)
        else:
            LOGGER.warning(f'Bootstrap file {bootstrapfile} is still present, Kindly remove the file.')
    elif bootstrapfile_check is True and db_check is False:
        LOGGER.error(f'Database is unavailable.')
    elif bootstrapfile_check is False and db_tables_check is True:
        pass
    elif bootstrapfile_check is False and db_tables_check is False:
        LOGGER.error(f'{bootstrapfile} and database is unavailable.')
    return True
