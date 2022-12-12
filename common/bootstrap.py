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
from pathlib import Path
import os
import ipaddress
import time
import hostlist
# from common.dbcheck import checkdbstatus
from utils.helper import Helper
from utils.database import Database
from utils.log import Log

configParser = RawConfigParser()
logger = Log.get_logger()

def check_db():
    """
    This method will check whether the database is empty or not.
    """
    dbcheck = False
    table = ['cluster', 'bmcsetup', 'group', 'groupinterface', 'groupsecrets',
             'network', 'osimage', 'switch', 'tracker', 'node', 'nodeinterface', 'nodesecrets']
    num = 0
    for tablex in table:
        result = Database().get_record(None, tablex, None)
        if result is None:
            logger.error(f'ERROR :: Database table {tablex} already have data.')
        if result:
            num = num+1
    if num == 0:
        dbcheck = True
    return dbcheck


def getconfig(filename=None):
    """
    From ini file Section Name is a section here, Option Name is an option here and Option Value is an item here.
    Example: sections[HOSTS, NETWORKS], options[HOSTNAME, NODELIST], and vlaues of options are item(10.141.255.254, node[001-004])
    """
    configParser.read(filename)
    # checksection(filename)
    Helper().checksection(filename, BOOTSTRAP)
    for section in configParser.sections():
        for (option, item) in configParser.items(section):
            globals()[option.upper()] = item
            if section in list(BOOTSTRAP.keys()):
                # checkoption(filename, section, option.upper())
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
                        logger.error(f'Invalid node list range: {item}, kindly use the numbers in incremental order.')
                elif 'NETWORKS' in section:
                    Helper().get_subnet(item)
                    BOOTSTRAP[section][option.upper()] = item
                else:
                    BOOTSTRAP[section][option.upper()] = item
            else:
                BOOTSTRAP[section] = {}
                BOOTSTRAP[section][option.upper()] = item


def bootstrap(bootstrapfile=None):
    """
    Insert default data into the database.
    """
    getconfig(bootstrapfile)
    logger.info('###################### Bootstrap Start ######################')
    num  = 1
    for hosts in BOOTSTRAP['HOSTS']:
        if f'CONTROLLER{num}' in BOOTSTRAP['HOSTS'].keys():
            default_controller = [{'column': 'ipaddr', 'value': BOOTSTRAP['HOSTS'][f'CONTROLLER{num}']}]
            Database().insert('controller', default_controller)
        num = num + 1
    for nodex in BOOTSTRAP['HOSTS']['NODELIST']:
        default_node = [
                {'column': 'name', 'value': str(nodex)},
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
    for nwkx in BOOTSTRAP['NETWORKS'].keys():
        default_network = [
                {'column': 'name', 'value': str(nwkx)},
                {'column': 'network', 'value': str(BOOTSTRAP['NETWORKS'][nwkx])},
                {'column': 'dhcp', 'value': '0'},
                {'column': 'ns_hostname', 'value': 'controller_hostname'},
                {'column': 'ns_ip', 'value': 'controller_ip'},
                {'column': 'gateway', 'value': 'controller_ip'},
                {'column': 'ntp_server', 'value': 'controller_ip'}
            ]
        Database().insert('network', default_network)
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

    default_group_interface = [
            {'column': 'groupid', 'value': '1'},
            {'column': 'interfacename', 'value': 'BOOTIF'}
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

    default_cluster = [
            {'column': 'technical_contacts', 'value': 'root@localhost'},
            {'column': 'provision_method', 'value': 'torrent'},
            {'column': 'provision_fallback', 'value': 'http'},
            {'column': 'security', 'value': '1'},
            {'column': 'debug', 'value': '0'}
        ]

    default_switch = [
            {'column': 'oid', 'value': '.1.3.6.1.2.1.17.7.1.2.2.1.2'},
            {'column': 'read', 'value': 'public'},
            {'column': 'rw', 'value': 'private'}
            ]
    Database().insert('group', default_group)
    Database().insert('groupinterface', default_group_interface)
    Database().insert('osimage', default_osimage)
    Database().insert('bmcsetup', default_bmcsetup)
    Database().insert('cluster', default_cluster)
    Database().insert('switch', default_switch)

    current_time = str(time.time()).replace('.', '')
    new_bootstrapfile = f'/trinity/local/luna/config/bootstrap-{current_time}.ini'
    os.rename(bootstrapfile, new_bootstrapfile)
    logger.info('###################### Bootstrap Finish ######################')
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
    dbstatus, dbcode = Helper().checkdbstatus()
    if dbcode == 200:
        db_check = check_db()

    if bootstrapfile_check is True and dbcode == 200:
        if db_check is True:
            bootstrap(bootstrapfile)
        else:
            logger.warning(f'Bootstrap file {bootstrapfile} is still present, Kindly remove the file.')
    elif bootstrapfile_check is True and db_check is False:
        logger.error(f'Database {dbstatus["database"]} is unavailable.')
    elif bootstrapfile_check is False and dbcode == 200:
        pass
    elif bootstrapfile_check is False and dbcode != 200:
        logger.error(f'Bootstrap file {bootstrapfile} and Database {dbstatus["database"]} is unavailable.')
    return True
