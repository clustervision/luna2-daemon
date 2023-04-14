#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
The database table layouts are listed below
supposedly both SQLite and MySQL compliant
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


DATABASE_LAYOUT_status = [
{"column": "id",                   "datatype": "integer", "length": "10", "key": "PRIMARY", "keyadd": "autoincrement"},
{"column": "request_id",           "datatype": "text"},
{"column": "username_initiator",   "datatype": "text"},
{"column": "created",              "datatype": "numeric"},
{"column": "read",                 "datatype": "integer"},
{"column": "message",              "datatype": "text"}]

DATABASE_LAYOUT_queue = [
{"column": "id",                   "datatype": "integer", "length": "10", "key": "PRIMARY", "keyadd": "autoincrement"},
{"column": "request_id",           "datatype": "text"},
{"column": "username_initiator",   "datatype": "text"},
{"column": "created",              "datatype": "numeric"},
{"column": "subsystem",            "datatype": "varchar", "length": "128"},
{"column": "task",                 "datatype": "text"},
{"column": "status",               "datatype": "varchar", "length": "64"}]

DATABASE_LAYOUT_osimage = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "name",                 "datatype": "VARCHAR", "length": "20", "key": "UNIQUE"},
{"column": "dracutmodules",        "datatype": "VARCHAR", "length": "100"},
{"column": "grab_filesystems",     "datatype": "VARCHAR", "length": "250"},
{"column": "grab_exclude",         "datatype": "TEXT"},
{"column": "initrdfile",           "datatype": "VARCHAR", "length": "100"},
{"column": "kernelfile",           "datatype": "VARCHAR", "length": "100"},
{"column": "kernelmodules",        "datatype": "VARCHAR", "length": "100"},
{"column": "kerneloptions",        "datatype": "VARCHAR", "length": "60"},
{"column": "kernelversion",        "datatype": "VARCHAR", "length": "60"},
{"column": "path",                 "datatype": "VARCHAR", "length": "60"},
{"column": "tarball",              "datatype": "VARCHAR", "length": "100"},
{"column": "torrent",              "datatype": "VARCHAR", "length": "100"},
{"column": "distribution",         "datatype": "VARCHAR", "length": "20"},
{"column": "changed",              "datatype": "INTEGER", "length": "10"},
{"column": "comment",              "datatype": "VARCHAR", "length": "20"}]

DATABASE_LAYOUT_nodesecrets = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "nodeid",               "datatype": "INTEGER", "length": "10"},
{"column": "name",                 "datatype": "VARCHAR", "length": "50"},
{"column": "content",              "datatype": "TEXT"},
{"column": "path",                 "datatype": "VARCHAR", "length": "200"}]

DATABASE_LAYOUT_nodeinterface = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "nodeid",               "datatype": "INTEGER", "length": "10", "key": "UNIQUE", "with": "interface"},
{"column": "interface",            "datatype": "VARCHAR", "length": "50"},
{"column": "macaddress",           "datatype": "VARCHAR", "length": "200"},
{"column": "options",              "datatype": "TEXT"}]

DATABASE_LAYOUT_bmcsetup = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "name",                 "datatype": "VARCHAR", "length": "20"},
{"column": "userid",               "datatype": "INTEGER", "length": "10"},
{"column": "username",             "datatype": "VARCHAR", "length": "20"},
{"column": "password",             "datatype": "VARCHAR", "length": "60"},
{"column": "netchannel",           "datatype": "INTEGER", "length": "10"},
{"column": "mgmtchannel",          "datatype": "INTEGER", "length": "10"},
{"column": "comment",              "datatype": "TEXT"},
{"column": "unmanaged_bmc_users",  "datatype": "VARCHAR", "length": "30"}]

DATABASE_LAYOUT_monitor = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "nodeid",               "datatype": "INTEGER", "length": "10"},
{"column": "status",               "datatype": "VARCHAR", "length": "100"},
{"column": "state",                "datatype": "VARCHAR", "length": "50"}]

DATABASE_LAYOUT_ipaddress = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "ipaddress",            "datatype": "VARCHAR", "length": "60", "key": "UNIQUE"},
{"column": "tableref",             "datatype": "VARCHAR", "length": "100", "key": "UNIQUE", "with": "tablerefid"},
{"column": "tablerefid",           "datatype": "integer", "length": "10"},
{"column": "networkid",            "datatype": "interger", "length": "10"}]

DATABASE_LAYOUT_groupinterface = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "groupid",              "datatype": "INTEGER", "length": "10"},
{"column": "interface",            "datatype": "VARCHAR", "length": "60"},
{"column": "networkid",            "datatype": "INTEGER", "length": "10"},
{"column": "options",              "datatype": "TEXT"}]

DATABASE_LAYOUT_roles = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "name",                 "datatype": "VARCHAR", "length": "50"},
{"column": "modules",              "datatype": "VARCHAR", "length": "200"}]

DATABASE_LAYOUT_group = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "name",                 "datatype": "VARCHAR", "length": "20", "key": "UNIQUE"},
{"column": "bmcsetupid",           "datatype": "INTEGER", "length": "10"},
{"column": "setupbmc",             "datatype": "INTEGER", "length": "10"},
{"column": "domain",               "datatype": "VARCHAR", "length": "20"},
{"column": "osimageid",            "datatype": "INTEGER", "length": "10"},
{"column": "prescript",            "datatype": "TEXT"},
{"column": "partscript",           "datatype": "TEXT"},
{"column": "postscript",           "datatype": "TEXT"},
{"column": "netboot",              "datatype": "VARCHAR", "length": "20"},
{"column": "localinstall",         "datatype": "INTEGER", "length": "10"},
{"column": "bootmenu",             "datatype": "INTEGER", "length": "10"},
{"column": "comment",              "datatype": "VARCHAR", "length": "20"},
{"column": "provision_interface",  "datatype": "VARCHAR", "length": "20"},
{"column": "provision_method",     "datatype": "VARCHAR", "length": "20"},
{"column": "provision_fallback",   "datatype": "VARCHAR", "length": "20"},
{"column": "unmanaged_bmc_users",  "datatype": "VARCHAR", "length": "30"}]

DATABASE_LAYOUT_network = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "name",                 "datatype": "VARCHAR", "length": "20", "key": "UNIQUE"},
{"column": "network",              "datatype": "VARCHAR", "length": "20"},
{"column": "subnet",               "datatype": "VARCHAR", "length": "20"},
{"column": "gateway",              "datatype": "VARCHAR", "length": "60"},
{"column": "nameserver_ip",        "datatype": "VARCHAR", "length": "20"},
{"column": "ntp_server",           "datatype": "VARCHAR", "length": "60"},
{"column": "dhcp",                 "datatype": "INTEGER", "length": "10"},
{"column": "dhcp_range_begin",     "datatype": "VARCHAR", "length": "20"},
{"column": "dhcp_range_end",       "datatype": "VARCHAR", "length": "60"},
{"column": "comment",              "datatype": "VARCHAR", "length": "60"}]

DATABASE_LAYOUT_user = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "username",             "datatype": "VARCHAR", "length": "50"},
{"column": "password",             "datatype": "VARCHAR", "length": "100"},
{"column": "roleid",               "datatype": "INTEGER", "length": "10"},
{"column": "createdby",            "datatype": "INTEGER", "length": "10"},
{"column": "lastlogin",            "datatype": "VARCHAR", "length": "50"},
{"column": "created",              "datatype": "VARCHAR", "length": "50"}]

DATABASE_LAYOUT_switch = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "name",                 "datatype": "VARCHAR", "length": "60", "key": "UNIQUE"},
{"column": "macaddress",           "datatype": "VARCHAR", "length": "60"},
{"column": "oid",                  "datatype": "VARCHAR", "length": "60"},
{"column": "read",                 "datatype": "VARCHAR", "length": "60"},
{"column": "rw",                   "datatype": "VARCHAR", "length": "60"},
{"column": "comment",              "datatype": "VARCHAR", "length": "60"}]

DATABASE_LAYOUT_otherdevices = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "name",                 "datatype": "VARCHAR", "length": "60", "key": "UNIQUE"},
{"column": "macaddress",           "datatype": "VARCHAR", "length": "60"},
{"column": "comment",              "datatype": "VARCHAR", "length": "60"}]

DATABASE_LAYOUT_controller = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "hostname",             "datatype": "VARCHAR", "length": "100", "key": "UNIQUE"},
{"column": "clusterid",            "datatype": "INTEGER", "length": "10"},
{"column": "status",               "datatype": "VARCHAR", "length": "20"},
{"column": "serverport",           "datatype": "INTEGER", "length": "10"}]

DATABASE_LAYOUT_groupsecrets = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "groupid",              "datatype": "INTEGER", "length": "10"},
{"column": "name",                 "datatype": "VARCHAR", "length": "50"},
{"column": "content",              "datatype": "TEXT"},
{"column": "path",                 "datatype": "VARCHAR", "length": "200"}]

DATABASE_LAYOUT_node = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "name",                 "datatype": "VARCHAR", "length": "10", "key": "UNIQUE"},
{"column": "hostname",             "datatype": "VARCHAR", "length": "120", "key": "UNIQUE"},
{"column": "groupid",              "datatype": "INTEGER", "length": "10"},
{"column": "localboot",            "datatype": "INTEGER", "length": "10"},
{"column": "osimageid",            "datatype": "INTEGER", "length": "10"},
{"column": "switchport",           "datatype": "INTEGER", "length": "10"},
{"column": "service",              "datatype": "INTEGER", "length": "10"},
{"column": "bmcsetupid",           "datatype": "INTEGER", "length": "10"},
{"column": "setupbmc",             "datatype": "INTEGER", "length": "10"},
{"column": "status",               "datatype": "VARCHAR", "length": "20"},
{"column": "switchid",             "datatype": "INTEGER", "length": "10"},
{"column": "comment",              "datatype": "TEXT"},
{"column": "prescript",            "datatype": "TEXT"},
{"column": "partscript",           "datatype": "TEXT"},
{"column": "postscript",           "datatype": "TEXT"},
{"column": "netboot",              "datatype": "INTEGER", "length": "10"},
{"column": "localinstall",         "datatype": "INTEGER", "length": "10"},
{"column": "bootmenu",             "datatype": "INTEGER", "length": "10"},
{"column": "provision_interface",  "datatype": "VARCHAR", "length": "60"},
{"column": "provision_method",     "datatype": "VARCHAR", "length": "60"},
{"column": "provision_fallback",   "datatype": "VARCHAR", "length": "60"},
{"column": "tpm_uuid",             "datatype": "VARCHAR", "length": "60"},
{"column": "tpm_pubkey",           "datatype": "VARCHAR", "length": "1024"},
{"column": "tpm_sha256",           "datatype": "VARCHAR", "length": "256"},
{"column": "unmanaged_bmc_users",  "datatype": "VARCHAR", "length": "30"}]

DATABASE_LAYOUT_cluster = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "name",                 "datatype": "VARCHAR", "length": "20", "key": "UNIQUE"},
{"column": "user",                 "datatype": "VARCHAR", "length": "20"},
{"column": "nameserver_ip",        "datatype": "VARCHAR", "length": "200"},
{"column": "forwardserver_ip",     "datatype": "VARCHAR", "length": "200"},
{"column": "ntp_server",           "datatype": "VARCHAR", "length": "200"},
{"column": "technical_contacts",   "datatype": "VARCHAR", "length": "50"},
{"column": "provision_method",     "datatype": "VARCHAR", "length": "20"},
{"column": "provision_fallback",   "datatype": "VARCHAR", "length": "20"},
{"column": "debug",                "datatype": "INTEGER", "length": "10"},
{"column": "security",             "datatype": "INTEGER", "length": "10"},
{"column": "createnode_ondemand",  "datatype": "INTEGER", "length": "10"}]

DATABASE_LAYOUT_tracker = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "infohash",             "datatype": "VARCHAR", "length": "80"},
{"column": "peer",                 "datatype": "VARCHAR", "length": "80"},
{"column": "ipaddress",            "datatype": "VARCHAR", "length": "60"},
{"column": "port",                 "datatype": "INTEGER", "length": "10"},
{"column": "download",             "datatype": "INTEGER", "length": "10"},
{"column": "upload",               "datatype": "INTEGER", "length": "10"},
{"column": "left",                 "datatype": "INTEGER", "length": "10"},
{"column": "updated",              "datatype": "VARCHAR", "length": "60"},
{"column": "status",               "datatype": "VARCHAR", "length": "20"}]

