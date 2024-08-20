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
{"column": "remote_request_id",    "datatype": "text"},
{"column": "remote_host",          "datatype": "VARCHAR", "length": "250"},
{"column": "username_initiator",   "datatype": "VARCHAR", "length": "250"},
{"column": "created",              "datatype": "numeric"},
{"column": "read",                 "datatype": "integer"},
{"column": "message",              "datatype": "text"}]

DATABASE_LAYOUT_queue = [
{"column": "id",                   "datatype": "integer", "length": "10", "key": "PRIMARY", "keyadd": "autoincrement"},
{"column": "request_id",           "datatype": "text"},
{"column": "username_initiator",   "datatype": "text"},
{"column": "created",              "datatype": "numeric"},
{"column": "subsystem",            "datatype": "varchar", "length": "128"},
{"column": "task",                 "datatype": "varchar", "length": "128"},
{"column": "param",                "datatype": "varchar", "length": "128"},
{"column": "noeof",                "datatype": "integer", "length": "10"},
{"column": "status",               "datatype": "varchar", "length": "64"}]

DATABASE_LAYOUT_osimage = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "name",                 "datatype": "VARCHAR", "length": "20", "key": "UNIQUE"},
{"column": "grab_filesystems",     "datatype": "VARCHAR", "length": "250"},
{"column": "grab_exclude",         "datatype": "TEXT"},
{"column": "initrdfile",           "datatype": "VARCHAR", "length": "100"},
{"column": "kernelfile",           "datatype": "VARCHAR", "length": "100"},
{"column": "kernelmodules",        "datatype": "VARCHAR", "length": "100"},
{"column": "kerneloptions",        "datatype": "VARCHAR", "length": "100"},
{"column": "kernelversion",        "datatype": "VARCHAR", "length": "60"},
{"column": "path",                 "datatype": "VARCHAR", "length": "60"},
{"column": "imagefile",            "datatype": "VARCHAR", "length": "100"},
{"column": "distribution",         "datatype": "VARCHAR", "length": "20"},
{"column": "osrelease",            "datatype": "VARCHAR", "length": "20"},
{"column": "tagid",                "datatype": "INTEGER", "length": "10"},
{"column": "changed",              "datatype": "INTEGER", "length": "10"},
{"column": "comment",              "datatype": "VARCHAR", "length": "20"}]

DATABASE_LAYOUT_osimagetag = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "name",                 "datatype": "VARCHAR", "length": "60"},
{"column": "osimageid",            "datatype": "INTEGER", "length": "10"},
{"column": "initrdfile",           "datatype": "VARCHAR", "length": "100"},
{"column": "kernelfile",           "datatype": "VARCHAR", "length": "100"},
{"column": "kerneloptions",        "datatype": "VARCHAR", "length": "200"},
{"column": "imagefile",            "datatype": "VARCHAR", "length": "100"}]

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
{"column": "vlanid",               "datatype": "VARCHAR", "length": "10"},
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
{"column": "tableref",             "datatype": "VARCHAR", "length": "100", "key": "UNIQUE", "with": "tablerefid"},
{"column": "tablerefid",           "datatype": "INTEGER", "length": "10"},
{"column": "status",               "datatype": "VARCHAR", "length": "2048"},
{"column": "state",                "datatype": "VARCHAR", "length": "50"},
{"column": "updated",              "datatype": "numeric"}]

DATABASE_LAYOUT_ipaddress = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "ipaddress",            "datatype": "VARCHAR", "length": "60", "key": "UNIQUE"},
{"column": "ipaddress_ipv6",       "datatype": "VARCHAR", "length": "60", "key": "UNIQUE"},
{"column": "tableref",             "datatype": "VARCHAR", "length": "100", "key": "UNIQUE", "with": "tablerefid"},
{"column": "tablerefid",           "datatype": "INTEGER", "length": "10"},
{"column": "networkid",            "datatype": "INTEGER", "length": "10"}]

DATABASE_LAYOUT_reservedipaddress = [
{"column": "version",              "datatype": "VARCHAR", "length": "10"},
{"column": "ipaddress",            "datatype": "VARCHAR", "length": "60", "key": "UNIQUE", "with": "version"},
{"column": "created",              "datatype": "numeric"}]

DATABASE_LAYOUT_groupinterface = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "groupid",              "datatype": "INTEGER", "length": "10"},
{"column": "interface",            "datatype": "VARCHAR", "length": "60"},
{"column": "vlanid",               "datatype": "VARCHAR", "length": "10"},
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
{"column": "osimagetagid",         "datatype": "INTEGER", "length": "10"},
{"column": "kerneloptions",        "datatype": "VARCHAR", "length": "200"},
{"column": "prescript",            "datatype": "TEXT"},
{"column": "partscript",           "datatype": "TEXT"},
{"column": "postscript",           "datatype": "TEXT"},
{"column": "netboot",              "datatype": "INTEGER", "length": "10"},
{"column": "localinstall",         "datatype": "INTEGER", "length": "10"},
{"column": "bootmenu",             "datatype": "INTEGER", "length": "10"},
{"column": "comment",              "datatype": "VARCHAR", "length": "20"},
{"column": "roles",                "datatype": "VARCHAR", "length": "512"},
{"column": "provision_interface",  "datatype": "VARCHAR", "length": "20"},
{"column": "provision_method",     "datatype": "VARCHAR", "length": "20"},
{"column": "provision_fallback",   "datatype": "VARCHAR", "length": "20"},
{"column": "unmanaged_bmc_users",  "datatype": "VARCHAR", "length": "30"}]

DATABASE_LAYOUT_network = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "name",                 "datatype": "VARCHAR", "length": "60", "key": "UNIQUE"},
{"column": "network",              "datatype": "VARCHAR", "length": "20"},
{"column": "network_ipv6",         "datatype": "VARCHAR", "length": "60"},
{"column": "subnet",               "datatype": "VARCHAR", "length": "20"},
{"column": "subnet_ipv6",          "datatype": "VARCHAR", "length": "20"},
{"column": "gateway",              "datatype": "VARCHAR", "length": "20"},
{"column": "gateway_ipv6",         "datatype": "VARCHAR", "length": "60"},
{"column": "gateway_metric",       "datatype": "INTEGER", "length": "10"},
{"column": "nameserver_ip",        "datatype": "VARCHAR", "length": "20"},
{"column": "nameserver_ip_ipv6",   "datatype": "VARCHAR", "length": "60"},
{"column": "ntp_server",           "datatype": "VARCHAR", "length": "60"},
{"column": "dhcp",                 "datatype": "INTEGER", "length": "10"},
{"column": "dhcp_range_begin",     "datatype": "VARCHAR", "length": "20"},
{"column": "dhcp_range_begin_ipv6","datatype": "VARCHAR", "length": "60"},
{"column": "dhcp_range_end",       "datatype": "VARCHAR", "length": "20"},
{"column": "dhcp_range_end_ipv6",  "datatype": "VARCHAR", "length": "60"},
{"column": "zone",                 "datatype": "VARCHAR", "length": "60"},
{"column": "shared",               "datatype": "VARCHAR", "length": "60"},
{"column": "type",                 "datatype": "VARCHAR", "length": "100"},
{"column": "comment",              "datatype": "VARCHAR", "length": "200"}]

DATABASE_LAYOUT_dns = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "host",                 "datatype": "VARCHAR", "length": "100"},
{"column": "ipaddress",            "datatype": "VARCHAR", "length": "20"},
{"column": "ipaddress_ipv6",       "datatype": "VARCHAR", "length": "60"},
{"column": "networkid",            "datatype": "INTEGER", "length": "10"}]

DATABASE_LAYOUT_user = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "username",             "datatype": "VARCHAR", "length": "50"},
{"column": "password",             "datatype": "VARCHAR", "length": "100"},
{"column": "roleid",               "datatype": "INTEGER", "length": "10"},
{"column": "createdby",            "datatype": "INTEGER", "length": "10"},
{"column": "lastlogin",            "datatype": "VARCHAR", "length": "50"},
{"column": "created",              "datatype": "numeric"}]

DATABASE_LAYOUT_switch = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "name",                 "datatype": "VARCHAR", "length": "60", "key": "UNIQUE"},
{"column": "macaddress",           "datatype": "VARCHAR", "length": "60"},
{"column": "oid",                  "datatype": "VARCHAR", "length": "60"},
{"column": "read",                 "datatype": "VARCHAR", "length": "60"},
{"column": "rw",                   "datatype": "VARCHAR", "length": "60"},
{"column": "uplinkports",          "datatype": "VARCHAR", "length": "60"},
{"column": "vendor",               "datatype": "VARCHAR", "length": "60"},
{"column": "comment",              "datatype": "VARCHAR", "length": "60"}]

DATABASE_LAYOUT_otherdevices = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "name",                 "datatype": "VARCHAR", "length": "60", "key": "UNIQUE"},
{"column": "macaddress",           "datatype": "VARCHAR", "length": "60"},
{"column": "vendor",               "datatype": "VARCHAR", "length": "60"},
{"column": "comment",              "datatype": "VARCHAR", "length": "60"}]

DATABASE_LAYOUT_cloud = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "name",                 "datatype": "VARCHAR", "length": "60", "key": "UNIQUE"},
{"column": "type",                 "datatype": "VARCHAR", "length": "60"},
{"column": "comment",              "datatype": "VARCHAR", "length": "60"}]

DATABASE_LAYOUT_controller = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "hostname",             "datatype": "VARCHAR", "length": "100", "key": "UNIQUE"},
{"column": "beacon",               "datatype": "INTEGER", "length": "10"},
{"column": "clusterid",            "datatype": "INTEGER", "length": "10"},
{"column": "status",               "datatype": "VARCHAR", "length": "20"},
{"column": "vendor",               "datatype": "VARCHAR", "length": "60"},
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
{"column": "groupid",              "datatype": "INTEGER", "length": "10"},
{"column": "osimageid",            "datatype": "INTEGER", "length": "10"},
{"column": "osimagetagid",         "datatype": "INTEGER", "length": "10"},
{"column": "kerneloptions",        "datatype": "VARCHAR", "length": "200"},
{"column": "switchid",             "datatype": "INTEGER", "length": "10"},
{"column": "switchport",           "datatype": "INTEGER", "length": "10"},
{"column": "cloudid",              "datatype": "INTEGER", "length": "10"},
{"column": "service",              "datatype": "INTEGER", "length": "10"},
{"column": "bmcsetupid",           "datatype": "INTEGER", "length": "10"},
{"column": "setupbmc",             "datatype": "INTEGER", "length": "10"},
{"column": "status",               "datatype": "VARCHAR", "length": "20"},
{"column": "comment",              "datatype": "TEXT"},
{"column": "roles",                "datatype": "VARCHAR", "length": "512"},
{"column": "vendor",               "datatype": "VARCHAR", "length": "60"},
{"column": "assettag",             "datatype": "VARCHAR", "length": "32"},
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
{"column": "domain_search",        "datatype": "VARCHAR", "length": "200"},
{"column": "nameserver_ip",        "datatype": "VARCHAR", "length": "200"},
{"column": "forwardserver_ip",     "datatype": "VARCHAR", "length": "200"},
{"column": "ntp_server",           "datatype": "VARCHAR", "length": "200"},
{"column": "technical_contacts",   "datatype": "VARCHAR", "length": "50"},
{"column": "provision_method",     "datatype": "VARCHAR", "length": "20"},
{"column": "provision_fallback",   "datatype": "VARCHAR", "length": "20"},
{"column": "debug",                "datatype": "INTEGER", "length": "10"},
{"column": "security",             "datatype": "INTEGER", "length": "10"},
{"column": "packing_bootpause",    "datatype": "INTEGER", "length": "10"},
{"column": "createnode_ondemand",  "datatype": "INTEGER", "length": "10"},
{"column": "nextnode_discover",    "datatype": "INTEGER", "length": "10"}]

DATABASE_LAYOUT_tracker = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "infohash",             "datatype": "VARCHAR", "length": "80"},
{"column": "peer",                 "datatype": "VARCHAR", "length": "80"},
{"column": "ipaddress",            "datatype": "VARCHAR", "length": "60"},
{"column": "port",                 "datatype": "INTEGER", "length": "10"},
{"column": "download",             "datatype": "INTEGER", "length": "10"},
{"column": "upload",               "datatype": "INTEGER", "length": "10"},
{"column": "left",                 "datatype": "INTEGER", "length": "10"},
{"column": "updated",              "datatype": "numeric"},
{"column": "status",               "datatype": "VARCHAR", "length": "20"}]

DATABASE_LAYOUT_journal = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "function",             "datatype": "VARCHAR", "length": "4096"},
{"column": "object",               "datatype": "VARCHAR", "length": "1024"},
{"column": "param",                "datatype": "VARCHAR", "length": "1024"},
{"column": "payload",              "datatype": "VARCHAR", "length": "65536"},
{"column": "masteronly",           "datatype": "INTEGER", "length": "10"},
{"column": "misc",                 "datatype": "VARCHAR", "length": "1024"},
{"column": "sendfor",              "datatype": "VARCHAR", "length": "80"},
{"column": "sendby",               "datatype": "VARCHAR", "length": "80"},
{"column": "tries",                "datatype": "INTEGER", "length": "10"},
{"column": "created",              "datatype": "numeric"}]

DATABASE_LAYOUT_ha = [
{"column": "enabled",              "datatype": "INTEGER", "length": "10"},
{"column": "syncimages",           "datatype": "INTEGER", "length": "10"},
{"column": "insync",               "datatype": "INTEGER", "length": "10"},
{"column": "sharedip",             "datatype": "INTEGER", "length": "10"},
{"column": "overrule",             "datatype": "INTEGER", "length": "10"},
{"column": "master",               "datatype": "INTEGER", "length": "10"},
{"column": "updated",              "datatype": "numeric"}]

DATABASE_LAYOUT_ping = [
{"column": "updated",              "datatype": "numeric"}]

DATABASE_LAYOUT_rack = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "name",                 "datatype": "VARCHAR", "length": "20", "key": "UNIQUE"},
{"column": "room",                 "datatype": "VARCHAR", "length": "100"},
{"column": "site",                 "datatype": "VARCHAR", "length": "100"},
{"column": "order",                "datatype": "VARCHAR", "length": "20"},
{"column": "size",                 "datatype": "INTEGER", "length": "10"}]

DATABASE_LAYOUT_rackinventory = [
{"column": "id",                   "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
{"column": "tableref",             "datatype": "VARCHAR", "length": "100", "key": "UNIQUE", "with": "tablerefid"},
{"column": "tablerefid",           "datatype": "INTEGER", "length": "10"},
{"column": "rackid",               "datatype": "INTEGER", "length": "10"},
{"column": "height",               "datatype": "INTEGER", "length": "10"},
{"column": "position",             "datatype": "INTEGER", "length": "10"},
{"column": "orientation",          "datatype": "VARCHAR", "length": "20"}]

