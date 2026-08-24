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
This is a Config Class, which provide the configuration
to DHN and DHCP methods.

"""

__author__      = 'Sumit Sharma/Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Sumit Sharma/Antoine Schonewille'
__email__       = 'support@clustervision.com'
__status__      = 'Development'

import os
import sys
import subprocess
import shutil
from time import time, sleep
import re
from jinja2 import Environment, FileSystemLoader
from ipaddress import ip_address, ip_network
from textwrap import dedent
from utils.log import Log
from utils.database import Database
from utils.helper import Helper
from utils.queue import Queue
from utils.ha import HA
from utils.controller import Controller
from common.constant import CONSTANT


class Config(object):
    """
    All kind of configuration methods.
    """

    def __init__(self):
        """
        Constructor - As of now, nothing has to initialize.
        """
        self.logger = Log.get_logger()
        self.plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
        self.hooks_plugins = None


    def normalize_ipxe_kernel(self, value=None):
        """Normalize the iPXE kernel selector stored on groups and nodes."""
        if value is None or value == '':
            return None
        normalized = str(value).strip().lower()
        if normalized in ['default', 'alternative']:
            return normalized
        self.logger.warning(f"unknown ipxe_kernel value {value}; falling back to default")
        return 'default'


    def ipxe_bootfiles(self, ipxe_kernel=None):
        """Return architecture-specific iPXE boot filenames for the selected kernel."""
        normalized = self.normalize_ipxe_kernel(ipxe_kernel) or 'default'
        if normalized == 'alternative':
            return {
                'class': 'ipxe-kernel-alternative',
                'x86_64': 'luna_snponly.efi',
                'arm64': 'luna_snponly_arm64.efi'
            }
        return {
            'class': 'ipxe-kernel-default',
            'x86_64': 'luna_ipxe.efi',
            'arm64': 'luna_ipxe_arm64.efi'
        }


    def dhcp_reservation_nextserver(self, network_name=None, subnets=None, shared=None, linksel=None):
        """Return next-server/port for a network from normal, shared, or link-selection subnet config."""
        subnets = subnets or {}
        shared = shared or {}
        linksel = linksel or {}
        if network_name in subnets:
            return {
                'server': subnets[network_name].get('nextserver'),
                'port': subnets[network_name].get('nextport')
            }
        for share in shared.values():
            if network_name in share:
                return {
                    'server': share[network_name].get('nextserver'),
                    'port': share[network_name].get('nextport')
                }
        # option-82.5 link-selection networks live in their own shared-networks block, so their
        # next-server sits in the link-sel 'boot' subnet rather than in subnets/shared.
        if network_name in linksel:
            boot = linksel[network_name].get('boot', {})
            return {'server': boot.get('nextserver'), 'port': boot.get('nextport')}
        return {'server': None, 'port': None}


    def switch_boot_reservation(self, device, next_server):
        """ZTP boot-option fields for a netboot switch reservation, shared by the v4 and v6
        renderers. Returns an empty dict when the switch is not doing netboot, so callers can
        blindly update() their host dict. next_server is the family-appropriate next-server."""
        boot = {}
        if Helper().make_bool(device.get('netboot')) is not True:
            return boot
        if not device.get('default_url') and not device.get('bootfile'):
            self.logger.warning(
                f"Switch {device['name']}: netboot is enabled but neither "
                "default_url nor bootfile is defined; skipping netboot"
            )
            return boot
        boot['switch'] = True
        # url_server is an optional manual override of the boot host; else the known next-server.
        boot['nextserver'] = device.get('url_server') or next_server['server']
        boot['nextport'] = next_server['port']
        # the daemon serves the switch recipe at boot/switch/<name>; advertise it when no explicit bootfile.
        boot['bootfile'] = device.get('bootfile') or f"boot/switch/{device['name']}"
        # ostype gates the Cumulus-only option 239; NVOS/generic never get it.
        if str(device.get('ostype') or '').lower() == 'cumulus':
            boot['cumulus'] = True
        # tftp_enable off (default) suppresses option 66 for the switch (HTTP ZTP goes straight through).
        # When tftp is enabled and url_server overrides the boot host, point option 66 at that same host
        # so it follows the override like next-server and the boot URL do; without an override the switch
        # keeps inheriting the subnet-level tftp-server-name.
        if Helper().make_bool(device.get('tftp_enable')) is not True:
            boot['tftp_suppress'] = True
        elif device.get('url_server'):
            boot['tftp_server'] = device['url_server']
        return boot


    def effective_mgmt_iface_ids(self):
        """switchinterface ids that are the *effective* management interface of their switch: the
        first (lowest id) mgmt=1 row per switch. The management interface renders as the bare
        <switch> name in DHCP and DNS; every other interface renders <switch>-<interface>. This is
        defensive on purpose: if a switch has several mgmt=1 rows (a bug, a hand DB edit, an
        out-of-order replicated write) only its first is treated as the prime, so rendering can
        never emit two bare <switch> names that would collide."""
        rows = Database().get_record(table="switchinterface", where="mgmt=1") or []
        ids, seen = set(), set()
        for row in sorted(rows, key=lambda r: r['id']):
            if row['switchid'] not in seen:
                ids.add(row['id'])
                seen.add(row['switchid'])
        return ids


    def dhcp_syntax_check(self, command=None, path=None, family=None):
        """
        Run the configured syntax checker over a rendered DHCP file. True when the server accepts
        it. On failure the server's own reason is logged: "containing errors" alone leaves an
        administrator with nowhere to start, and the reason is the whole diagnosis - a missing
        binary, an interface the host does not have, an address the option cannot hold.
        """
        try:
            checked = subprocess.run(command.split() + [path], check=True,
                                     capture_output=True, text=True)
        except Exception as exp:
            reason = (getattr(exp, 'stderr', None) or getattr(exp, 'stdout', None) or str(exp))
            self.logger.error(f'{family} file : {path} containing errors. {reason.strip()}')
            return False
        if checked.returncode:
            self.logger.error(f'{family} file : {path} containing errors. {(checked.stderr or "").strip()}')
            return False
        return True


    def dhcp_overwrite(self):
        """
        This method collect dhcp enabled networks, node interfaces belongs to the networks and
        other devices which have the mac address. write and validates the /var/tmp/luna/dhcpd.conf

        Both families are validated before either is installed, and a fault in one still holds
        the other back. That is deliberate: the two are reloaded together, and a v6 config the
        server refuses is a reason to look at the cluster rather than to press on with v4. What
        the fault must not do is masquerade as a fault in the family that is fine, so each half
        is judged separately and the log says which one failed and why.
        """
        validate4, validate6 = True, True
        rendered4, rendered6 = False, False
        dhcp_test = 'dhcpd -t -cf'
        dhcp6_test = 'dhcpd -6 -t -cf'
        dhcp_config_path = '/etc/dhcp/dhcpd.conf'
        dhcp6_config_path = '/etc/dhcp/dhcpd6.conf'
        template = 'templ_dhcpd.cfg'
        template6 = 'templ_dhcpd6.cfg'
        dhcp6_interface = ''
        ignore_link_selection = False
        if 'DHCP' in CONSTANT:
            if 'TEMPLATE' in CONSTANT["DHCP"]:
                template = CONSTANT["DHCP"]["TEMPLATE"]
            if 'TEST' in CONSTANT["DHCP"]:
                dhcp_test = CONSTANT["DHCP"]["TEST"]
            if 'CONFIG_PATH' in CONSTANT["DHCP"]:
                dhcp_config_path = CONSTANT["DHCP"]["CONFIG_PATH"]
            if 'TEMPLATE6' in CONSTANT["DHCP"]:
                template6 = CONSTANT["DHCP"]["TEMPLATE6"]
            if 'TEST6' in CONSTANT["DHCP"]:
                dhcp6_test = CONSTANT["DHCP"]["TEST6"]
            if 'CONFIG6_PATH' in CONSTANT["DHCP"]:
                dhcp6_config_path = CONSTANT["DHCP"]["CONFIG6_PATH"]
            # Last-resort interface for a DHCPv6 subnet with no controller address in range. Unset
            # by default and deliberately so: kea refuses the entire configuration when given an
            # interface the host does not have, so the name has to come from whoever knows the
            # controller rather than from a guess shipped in a template.
            if 'INTERFACE6' in CONSTANT["DHCP"]:
                dhcp6_interface = CONSTANT["DHCP"]["INTERFACE6"] or ''
            # Whether kea honours option 82 sub-option 5 (RFC 3527 link-selection). Off by default:
            # where a relay uses the sub-option to tell apart several links behind one giaddr, it is
            # the only thing that identifies the link, and ignoring it puts clients in a sibling
            # subnet with no error anywhere. Turn it on where the sub-option names a prefix luna
            # does not manage and giaddr alone identifies the link; dhcp_link_subnet is the other
            # answer to that case, and keeps foreign devices out of our pools as well.
            if 'IGNORE_LINK_SELECTION' in CONSTANT["DHCP"]:
                ignore_link_selection = Helper().make_bool(CONSTANT["DHCP"]["IGNORE_LINK_SELECTION"])

        # option 82.5 link-selection is a Kea-only construct (shared-networks + link anchor). On the
        # ISC dhcpd backend a link network must keep rendering exactly as before, so the routing
        # change below is gated on the selected template being Kea, per family.
        is_kea = 'kea' in template.lower()
        is_kea6 = 'kea' in template6.lower()
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            self.logger.error(f"Error building dhcp config. {template_path} does not exist")
            return False
        template6_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template6}'
        check_template6 = Helper().check_jinja(template6_path)
        if not check_template6:
            self.logger.error(f"Error building dhcp6 config. {template6_path} does not exist")
            return False

        if len(dhcp_config_path) < 5 or not dhcp_config_path.startswith('/'):
            self.logger.error(f"Error building dhcp config. dhcp_config_path {dhcp_config_path} not matching minimum criterea")
            return False
        if len(dhcp6_config_path) < 5 or not dhcp6_config_path.startswith('/'):
            self.logger.error(f"Error building dhcp6 config. dhcp6_config_path {dhcp6_config_path} not matching minimum criterea")
            return False

        ntp_server, nameserver_ip, nameserver_ip_ipv6 = None, None, None
        cluster = Database().get_record(table='cluster')
        if cluster:
            if 'ntp_server' in cluster[0] and cluster[0]['ntp_server']:
                ntp_server = cluster[0]['ntp_server']
            if 'nameserver_ip' in cluster[0] and cluster[0]['nameserver_ip']:
                nameserver_ip = cluster[0]['nameserver_ip']
            if 'nameserver_ip_ipv6' in cluster[0] and cluster[0]['nameserver_ip_ipv6']:
                nameserver_ip_ipv6 = cluster[0]['nameserver_ip_ipv6']
        dhcp_file = f"{CONSTANT['TEMPLATES']['TMP_DIRECTORY']}/dhcpd.conf"
        dhcp6_file = f"{CONSTANT['TEMPLATES']['TMP_DIRECTORY']}/dhcpd6.conf"
        domain = None
        controller = Database().get_record_join(
            ['ipaddress.ipaddress','ipaddress.ipaddress_ipv6','network.name as domain'],
            ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
            ['tableref="controller"', 'controller.beacon=1']
        )
        if controller:
            domain=controller[0]['domain']
            ntp_server = ntp_server or controller[0]['ipaddress']
            nameserver_ip = nameserver_ip or controller[0]['ipaddress']
            nameserver_ip_ipv6 = nameserver_ip_ipv6 or controller[0]['ipaddress_ipv6']
        #
        omapikey=None
        tsigkey=None
        tsigalgo=None
        if 'OMAPIKEY' in CONSTANT['DHCP'] and CONSTANT['DHCP']['OMAPIKEY']:
            omapikey=CONSTANT['DHCP']['OMAPIKEY']
        if 'TSIGKEY' in CONSTANT['DHCP'] and 'TSIGALGO' in CONSTANT['DHCP']:
            if CONSTANT['DHCP']['TSIGKEY'] and CONSTANT['DHCP']['TSIGALGO']:
                tsigkey=CONSTANT['DHCP']['TSIGKEY']
                tsigalgo=CONSTANT['DHCP']['TSIGALGO']
        #
        config_classes = {}
        config_classes6 = {}
        config_shared = {}
        config_shared6 = {}
        config_subnets = {}
        config_subnets6 = {}
        config_zones = {}
        config_zones6 = {}
        config_empty = {}
        config_empty6 = {}
        config_pools = {}
        config_pools6 = {}
        config_reservations = {}
        config_reservations6 = {}
        mgmt_iface_ids = self.effective_mgmt_iface_ids()
        #
        networksbyname = {}
        emptybyname = {}
        handled = []

        empty = Database().get_record(table='network', where=f'name="{domain}" AND (dhcp IS NULL OR dhcp != 1)')
        if empty:
            emptybyname = Helper().convert_list_to_dict(empty, 'name')

        networks = Database().get_record(table='network', where='dhcp = 1')
        if networks:
            networksbyname = Helper().convert_list_to_dict(networks, 'name')

        networksbyname = networksbyname | emptybyname

        shared = {}
        shared6 = {}
        # prepare - we check if we are shared, are ipv4/v6, etc
        for network in networksbyname.keys():
            networksbyname[network]['ipv6'], networksbyname[network]['ipv4'] = False, False
            dhcp_nodes_only = bool(networksbyname[network].get('dhcp_nodes_only'))
            if networksbyname[network]['network'] and (
                dhcp_nodes_only or
                (networksbyname[network]['dhcp_range_begin'] and networksbyname[network]['dhcp_range_end'])
            ):
                networksbyname[network]['ipv4'] = True
            if networksbyname[network]['network_ipv6'] and (
                dhcp_nodes_only or
                (networksbyname[network]['dhcp_range_begin_ipv6'] and networksbyname[network]['dhcp_range_end_ipv6'])
            ):
                networksbyname[network]['ipv6'] = True
            if networksbyname[network]['shared'] and networksbyname[network]['shared'] in networksbyname.keys():
                # A network carrying a dhcp_link_subnet anchor stays in its shared group so the
                # anchor joins the group's block: a sibling left outside is unreachable from the
                # anchor, and a node reserved there is served from the wrong network's pool. That
                # only holds where the group really is one link - see dhcp_group_shares_link. Where
                # it is not, the anchor keeps a block of its own, because selection through it
                # cannot tell two relayed links apart.
                link_field = networksbyname[network].get('dhcp_link_subnet')
                one_link = (not link_field) or self.dhcp_group_shares_link(
                    network, networksbyname[network]['shared'], networksbyname)
                if networksbyname[network]['ipv4'] and not (
                        is_kea and link_field and not one_link
                        and self.dhcp_link_anchors(link_field, 'ipv4')):
                    if not networksbyname[network]['shared'] in shared.keys():
                        shared[networksbyname[network]['shared']] = []
                    shared[networksbyname[network]['shared']].append(network)
                if networksbyname[network]['ipv6'] and not (
                        is_kea6 and link_field and not one_link
                        and self.dhcp_link_anchors(link_field, 'ipv6')):
                    if not networksbyname[network]['shared'] in shared6.keys():
                        shared6[networksbyname[network]['shared']] = []
                    shared6[networksbyname[network]['shared']].append(network)

        # IPv4 - shared networks
        shared_groups, shared_groups6, shared_group_of = [], [], {}
        for network in shared.keys():
            shared_name = f"{network}-" + "-".join(shared[network])
            shared_groups.append((shared_name, network, list(shared[network])))
            for member in [network] + shared[network]:
                shared_group_of[member] = shared_name
            #
            # the main network/carrier
            config_pools[shared_name]={}
            config_pools[shared_name]['policy']='deny'
            config_pools[shared_name]['members']=shared[network]
            if networksbyname[network]['dhcp'] and not networksbyname[network].get('dhcp_nodes_only'):
                config_pools[shared_name]['range_begin']=networksbyname[network]['dhcp_range_begin']
                config_pools[shared_name]['range_end']=networksbyname[network]['dhcp_range_end']
            #
            config_shared[shared_name] = {}
            config_shared[shared_name][network]=self.dhcp_subnet_config(networksbyname[network],'shared','ipv4')
            config_reservations[network] = []
            handled.append(network)

            # the network that has shared config, or piggy backs on the carrier
            for piggyback in shared[network]:
                config_shared[shared_name][piggyback]=self.dhcp_subnet_config(networksbyname[piggyback],'shared','ipv4')
                config_reservations[piggyback] = []
                config_pools[piggyback]={}
                config_pools[piggyback]['policy']='allow'
                config_pools[piggyback]['members']=[piggyback]
                if not networksbyname[piggyback].get('dhcp_nodes_only'):
                    config_pools[piggyback]['range_begin']=networksbyname[piggyback]['dhcp_range_begin']
                    config_pools[piggyback]['range_end']=networksbyname[piggyback]['dhcp_range_end']
                config_classes[piggyback]={}
                config_classes[piggyback]['network']=piggyback
                handled.append(piggyback)

        # IPv6 - shared networks
        for network in shared6.keys():
            shared_name = f"{network}-" + "-".join(shared6[network])
            shared_groups6.append((shared_name, network, list(shared6[network])))
            for member in [network] + shared6[network]:
                shared_group_of[member + '_ipv6'] = shared_name
            #
            # the main network/carrier
            config_pools6[shared_name]={}
            config_pools6[shared_name]['policy']='deny'
            #config_pools6[shared_name]['primary']=true # might be completely unused
            config_pools6[shared_name]['members']=shared6[network]
            if networksbyname[network]['dhcp'] and not networksbyname[network].get('dhcp_nodes_only'):
                config_pools6[shared_name]['range_begin']=networksbyname[network]['dhcp_range_begin_ipv6']
                config_pools6[shared_name]['range_end']=networksbyname[network]['dhcp_range_end_ipv6']
            #
            config_shared6[shared_name] = {}
            config_shared6[shared_name][network]=self.dhcp_subnet_config(networksbyname[network],'shared','ipv6')
            config_reservations6[network] = []
            handled.append(network+'_ipv6')

            # the network that has shared config, or piggy backs on the carrier
            for piggyback in shared6[network]:
                config_shared6[shared_name][piggyback]=self.dhcp_subnet_config(networksbyname[piggyback],'shared','ipv6')
                config_reservations6[piggyback] = []
                config_pools6[piggyback]={}
                config_pools6[piggyback]['policy']='allow'
                config_pools6[piggyback]['members']=[piggyback]
                if not networksbyname[piggyback].get('dhcp_nodes_only'):
                    config_pools6[piggyback]['range_begin']=networksbyname[piggyback]['dhcp_range_begin_ipv6']
                    config_pools6[piggyback]['range_end']=networksbyname[piggyback]['dhcp_range_end_ipv6']
                config_classes6[piggyback]={}
                config_classes6[piggyback]['network']=piggyback
                handled.append(piggyback+'_ipv6')

        # option-82.5 (RFC 3527) link-selection: a relay may rewrite subnet selection with the
        # link-selection sub-option, and kea then matches that address instead of giaddr. A network
        # with a dhcp_link_subnet anchor gets a pool-less subnet on the relay's link prefix so the
        # rewritten selection still lands somewhere we control. The anchor belongs to the whole
        # link, so where the network is in a shared group the anchor joins that group's block -
        # a group sibling outside it is unreachable from the anchor, and kea refuses the entire
        # configuration if the same prefix is rendered in two blocks.
        config_linksel = {}
        config_linksel6 = {}
        config_anchor = {}
        config_anchor6 = {}
        for network in networksbyname.keys():
            nwk = networksbyname[network]
            if not nwk['dhcp'] or not nwk.get('dhcp_link_subnet'):
                continue
            for family, kea, in_pool, linksel, anchor, reservations in (
                ('ipv4', is_kea, nwk['ipv4'], config_linksel, config_anchor, config_reservations),
                ('ipv6', is_kea6, nwk['ipv6'], config_linksel6, config_anchor6, config_reservations6),
            ):
                key = network if family == 'ipv4' else network + '_ipv6'
                if not (kea and in_pool):
                    continue
                anchors = self.dhcp_link_anchors(nwk['dhcp_link_subnet'], family)
                if not anchors:
                    continue
                group = shared_group_of.get(key)
                if group:
                    for prefix in anchors:
                        if prefix not in anchor.setdefault(group, []):
                            anchor[group].append(prefix)
                elif key not in handled:
                    linksel[network] = {'anchor': anchors, 'boot': self.dhcp_subnet_config(nwk, False, family)}
                    reservations[network] = []
                    handled.append(key)

        # kea takes a shared group's pools from the subnet bodies rather than from a pool list, and
        # fences them where the group carries a link anchor. This only adds keys; the ISC template
        # reads neither and keeps taking its pools and its allow/deny from POOLS.
        config_derived = []
        config_derived6 = []
        for groups, subnets, pools, anchors, derived, policy in (
            (shared_groups, config_shared, config_pools, config_anchor, config_derived, True),
            (shared_groups6, config_shared6, config_pools6, config_anchor6, config_derived6, False),
        ):
            for shared_name, carrier, members in groups:
                derived += self.dhcp_shared_pools(
                    subnets=subnets.get(shared_name), pools=pools, group=shared_name,
                    carrier=carrier, members=members, policy=policy,
                    fence=f"{shared_name}-boot-class" if shared_name in anchors else None)

        # A link prefix may be rendered once only. Validation refuses a duplicate across networks,
        # so this is the backstop for a database that predates it: drop the repeat and say so,
        # rather than emit a configuration kea refuses in its entirety.
        for anchors in (config_anchor, config_anchor6):
            seen = {}
            for group in list(anchors.keys()):
                for prefix in list(anchors[group]):
                    if prefix in seen:
                        self.logger.error(f"dhcp_link_subnet {prefix} is claimed by both "
                                          f"{seen[prefix]} and {group}; kea allows a prefix in one "
                                          f"shared-network only, so it is dropped from {group}. "
                                          f"Set the anchor on one of the two groups.")
                        anchors[group].remove(prefix)
                        continue
                    seen[prefix] = group
                if not anchors[group]:
                    del anchors[group]

        # An anchor says the sub-option carries information we want, which is the opposite of
        # ignoring it. The anchor is the more specific statement, so it wins - loudly, because the
        # two settings contradict and whoever set them should know which one took effect.
        ignore_rai = is_kea and ignore_link_selection
        if ignore_rai and (config_linksel or config_anchor):
            self.logger.error("[DHCP] IGNORE_LINK_SELECTION is set, but "
                              f"{', '.join(sorted(set(config_linksel) | set(config_anchor)))} "
                              "declares a dhcp_link_subnet anchor, which only has meaning when the "
                              "option-82.5 sub-option is honoured. Honouring it; clear the anchor "
                              "or clear the setting.")
            ignore_rai = False

        # we handle all (remaining) networks below
        if networksbyname:
            for network in networksbyname.keys():
                nwk = networksbyname[network]
                if nwk['dhcp']:
                    if nwk['name'] not in handled and nwk['ipv4']:
                        config_subnets[nwk['name']] = self.dhcp_subnet_config(nwk,False,'ipv4')
                        config_reservations[nwk['name']] = []
                        handled.append(nwk['name'])
                    if nwk['name']+'_ipv6' not in handled and nwk['ipv6']:
                        config_subnets6[nwk['name']] = self.dhcp_subnet_config(nwk,False,'ipv6')
                        config_reservations6[nwk['name']] = []
                        handled.append(nwk['name']+'_ipv6')
                else:
                    if nwk['name'] not in handled and nwk['network']:
                        config_empty[nwk['name']] = self.dhcp_empty_config(nwk,'ipv4')
                        handled.append(nwk['name'])
                    if nwk['name']+'_ipv6' not in handled and nwk['network_ipv6']:
                        config_empty6[nwk['name']] = self.dhcp_empty_config(nwk,'ipv6')
                        handled.append(nwk['name']+'_ipv6')
                    continue
                network_id = nwk['id']
                network_name = nwk['name']
                network_ip = nwk['network']
                network_ipv6 = nwk['network_ipv6']
                if nwk['dhcp_nodes_in_pool']:
                    self.logger.info(f'using forward updates for network {network_name} IPv4: {network_ip} or IPv6: {network_ipv6}')
                    if nwk['ipv4']:
                        config_zones[nwk['name']] = self.dhcp_zone_config(nwk,'ipv4')
                    if nwk['ipv6']:
                        config_zones6[nwk['name']] = self.dhcp_zone_config(nwk,'ipv6')
                node_interface = Database().get_record_join(
                    ['node.name as nodename', 'node.ipxe_kernel as node_ipxe_kernel',
                     'group.ipxe_kernel as group_ipxe_kernel', 'ipaddress.ipaddress',
                     'ipaddress.ipaddress_ipv6', 'nodeinterface.macaddress','ipaddress.dhcp'],
                    ['ipaddress.tablerefid=nodeinterface.id', 'nodeinterface.nodeid=node.id',
                     'group.id=node.groupid'],
                    ['tableref="nodeinterface"', f'ipaddress.networkid="{network_id}"']
                )
                nwkdomain=nwk['name']
                if node_interface:
                    for interface in node_interface:
                        if nwk['dhcp_nodes_in_pool'] and interface['dhcp']:
                            continue
                        elif interface['macaddress']:
                            ipxe_bootfiles = self.ipxe_bootfiles(
                                interface['node_ipxe_kernel'] or interface['group_ipxe_kernel']
                            )
                            if interface['ipaddress_ipv6']:
                                config_host6={}
                                config_host6['name']=interface['nodename']
                                config_host6['domain']=nwkdomain
                                config_host6['ipaddress']=interface['ipaddress_ipv6']
                                config_host6['macaddress']=interface['macaddress']
                                config_host6['ipxe_kernel_class']=ipxe_bootfiles['class']
                                config_host6['ipxe_bootfile']=ipxe_bootfiles['x86_64']
                                config_host6['ipxe_bootfile_arm64']=ipxe_bootfiles['arm64']
                                next_server = self.dhcp_reservation_nextserver(
                                    nwk['name'], config_subnets6, config_shared6, config_linksel6
                                )
                                config_host6['nextserver']=next_server['server']
                                config_host6['nextport']=next_server['port']
                                if nwk['name'] in config_reservations6:
                                    config_reservations6[nwk['name']].append(config_host6)
                            elif interface['ipaddress']:
                                config_host={}
                                config_host['name']=interface['nodename']
                                config_host['domain']=nwkdomain
                                config_host['ipaddress']=interface['ipaddress']
                                config_host['macaddress']=interface['macaddress']
                                config_host['ipxe_kernel_class']=ipxe_bootfiles['class']
                                config_host['ipxe_bootfile']=ipxe_bootfiles['x86_64']
                                config_host['ipxe_bootfile_arm64']=ipxe_bootfiles['arm64']
                                next_server = self.dhcp_reservation_nextserver(
                                    nwk['name'], config_subnets, config_shared, config_linksel
                                )
                                config_host['nextserver']=next_server['server']
                                config_host['nextport']=next_server['port']
                                if nwk['name'] in config_reservations:
                                    config_reservations[nwk['name']].append(config_host)
                else:
                    self.logger.info(f'no nodes available for network {network_name} IPv4: {network_ip} or IPv6: {network_ipv6}')
                for item in ['otherdevices', 'switch', 'switchinterface']:
                    if item == 'switchinterface':
                        # additive: each extra switch interface (eth1+) gets its own reservation, keyed on
                        # its own mac/ip but carrying the parent switch's ZTP config (netboot/ostype/...).
                        select = ['switch.name', 'switchinterface.interface', 'switchinterface.id as ifid',
                                  'ipaddress.ipaddress', 'ipaddress.ipaddress_ipv6', 'switchinterface.macaddress',
                                  'switch.netboot', 'switch.default_url', 'switch.bootfile', 'switch.ostype',
                                  'switch.tftp_enable', 'switch.url_server']
                        join = ['ipaddress.tablerefid=switchinterface.id', 'switchinterface.switchid=switch.id']
                    else:
                        select = [f'{item}.name','ipaddress.ipaddress','ipaddress.ipaddress_ipv6',f'{item}.macaddress']
                        if item == 'switch':
                            select += ['switch.netboot', 'switch.default_url', 'switch.bootfile',
                                       'switch.ostype', 'switch.tftp_enable', 'switch.url_server']
                        join = [f'ipaddress.tablerefid={item}.id']
                    devices = Database().get_record_join(
                        select,
                        join,
                        [f'tableref="{item}"', f'ipaddress.networkid="{network_id}"']
                    )
                    if devices:
                        for device in devices:
                            if device['macaddress']:
                                # the management interface keeps the bare <switch> name; every other
                                # switch interface is <switch>-<interface> so interfaces of one switch
                                # on a network do not collide (matches dns_configure).
                                resv_name = device['name']
                                if item == 'switchinterface' and device.get('ifid') not in mgmt_iface_ids:
                                    resv_name = f"{device['name']}-{device['interface']}"
                                if device['ipaddress_ipv6']:
                                    config_host6={}
                                    config_host6['name']=resv_name
                                    config_host6['domain']=nwkdomain
                                    config_host6['ipaddress']=device['ipaddress_ipv6']
                                    config_host6['macaddress']=device['macaddress']
                                    if item in ('switch', 'switchinterface'):
                                        next_server = self.dhcp_reservation_nextserver(
                                            nwk['name'], config_subnets6, config_shared6, config_linksel6
                                        )
                                        config_host6.update(self.switch_boot_reservation(device, next_server))
                                    if nwk['name'] in config_reservations6:
                                        config_reservations6[nwk['name']].append(config_host6)
                                else:
                                    config_host={}
                                    config_host['name']=resv_name
                                    config_host['domain']=nwkdomain
                                    config_host['ipaddress']=device['ipaddress']
                                    config_host['macaddress']=device['macaddress']
                                    if item in ('switch', 'switchinterface'):
                                        next_server = self.dhcp_reservation_nextserver(
                                            nwk['name'], config_subnets, config_shared, config_linksel
                                        )
                                        config_host.update(self.switch_boot_reservation(device, next_server))
                                    if nwk['name'] in config_reservations:
                                        config_reservations[nwk['name']].append(config_host)
                    else:
                        self.logger.debug(f'{item} not available for {network_name}  IPv4: {network_ip} or IPv6: {network_ipv6}')
        
        # DHCPv6 gates each subnet on the boot classes built for it; give every subnet the one
        # derived class that says the same thing, so the render stops depending on a kea 3.0-only
        # spelling. Done after the pool wiring so a group's carrier and piggybacks are known.
        for shared_name, carrier, members in shared_groups6:
            for name, subnet in (config_shared6.get(shared_name) or {}).items():
                select, definition = self.dhcp6_select_class(subnet=subnet, name=name,
                                                             group=shared_name,
                                                             piggyback=(name != carrier))
                subnet['select_class'] = select
                if definition:
                    config_derived6.append(definition)
        for name, subnet in config_subnets6.items():
            select, definition = self.dhcp6_select_class(subnet=subnet, name=name)
            subnet['select_class'] = select
            if definition:
                config_derived6.append(definition)

        try:
            file_loader = FileSystemLoader(CONSTANT["TEMPLATES"]["TEMPLATE_FILES"])
            env = Environment(loader=file_loader)
            # IPv4 -----------------------------------
            if any([config_subnets, config_shared, config_empty, config_linksel]):
                dhcpd_template = env.get_template(template)
                dhcpd_config = dhcpd_template.render(CLASSES=config_classes,SHARED=config_shared,SUBNETS=config_subnets,
                                                     ZONES=config_zones,EMPTY=config_empty,POOLS=config_pools,
                                                     LINKSEL=config_linksel,ANCHOR=config_anchor,
                                                     DERIVED=config_derived,IGNORE_RAI=ignore_rai,
                                                     DOMAINNAME=domain,NAMESERVERS=nameserver_ip,NTPSERVERS=ntp_server,
                                                     RESERVATIONS=config_reservations,OMAPIKEY=omapikey,
                                                     TSIGKEY=tsigkey,TSIGALGO=tsigalgo)
                with open(dhcp_file, 'w', encoding='utf-8') as dhcp:
                    dhcp.write(dhcpd_config)
                rendered4 = True
                validate4 = self.dhcp_syntax_check(dhcp_test, dhcp_file, 'DHCP')
            # IPv6 -----------------------------------
            if any([config_subnets6, config_shared6, config_empty6, config_linksel6]):
                interfaces = Helper().get_controller_interfaces_for_networks()
                if not dhcp6_interface:
                    # With a fallback configured every subnet names an interface, so there is
                    # nothing to report: kea will say soon enough whether that name is real.
                    self.dhcp6_unservable(config_subnets6, config_shared6, config_linksel6, interfaces['ipv6'])
                dhcpd_template = env.get_template(template6)
                dhcpd_config = dhcpd_template.render(CLASSES=config_classes6,SHARED=config_shared6,SUBNETS=config_subnets6,
                                                     ZONES=config_zones6,EMPTY=config_empty6,POOLS=config_pools6,
                                                     LINKSEL=config_linksel6,ANCHOR=config_anchor6,
                                                     DERIVED=config_derived6,
                                                     DOMAINNAME=domain,NAMESERVERS=nameserver_ip,
                                                     NAMESERVERS_IPV6=nameserver_ip_ipv6,NTPSERVERS=ntp_server,
                                                     RESERVATIONS=config_reservations6,OMAPIKEY=omapikey,
                                                     TSIGKEY=tsigkey,TSIGALGO=tsigalgo,INTERFACES=interfaces['ipv6'],
                                                     FALLBACK_INTERFACE=dhcp6_interface)
                with open(dhcp6_file, 'w', encoding='utf-8') as dhcp:
                    dhcp.write(dhcpd_config)
                rendered6 = True
                validate6 = self.dhcp_syntax_check(dhcp6_test, dhcp6_file, 'DHCP6')

            # Install only once both families are accepted. They are reloaded together, so
            # copying one in while the other is refused leaves the file on disk and the running
            # service disagreeing, and some later unrelated restart applies a config nobody was
            # told had gone in.
            if validate4 and validate6:
                if rendered4:
                    shutil.copyfile(dhcp_file, dhcp_config_path)
                if rendered6:
                    shutil.copyfile(dhcp6_file, dhcp6_config_path)
            elif validate4 != validate6:
                good, bad = ('DHCPv4', 'DHCPv6') if validate4 else ('DHCPv6', 'DHCPv4')
                self.logger.error(f"the {good} configuration validated clean; it is NOT the "
                                  f"cause. It is being held back because the {bad} configuration "
                                  f"was refused, above. Both families are reloaded together, so "
                                  f"resolve the {bad} fault and this will go through with it")
        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"building DHCP config encountered problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
            validate4, validate6 = False, False
        return validate4 and validate6


    def dhcp6_unservable(self, subnets=None, shared=None, linksel=None, interfaces=None):
        """
        Report every DHCPv6 subnet kea will never be able to select. kea picks a subnet6 by the
        interface the request arrived on or by the relay that forwarded it; one with neither is
        accepted by the parser and then silently never served, so nothing downstream reports it.
        Mirrors the interface lookup the template does, per block type.
        """
        unservable = []
        for name, subnet in (subnets or {}).items():
            if name not in interfaces and 'dhcp_relay' not in subnet:
                unservable.append(name)
        for share, members in (shared or {}).items():
            for name, subnet in members.items():
                if name not in interfaces and share not in interfaces and 'dhcp_relay' not in subnet:
                    unservable.append(name)
        for name, link in (linksel or {}).items():
            if name not in interfaces and 'dhcp_relay' not in link['boot']:
                unservable.append(name)
        if unservable:
            self.logger.error(f"DHCPv6: network(s) {','.join(unservable)} have no controller "
                              "interface in range and no dhcp_relay. kea cannot select these "
                              "subnets, so they will not be served. give the controller an IPv6 "
                              "address inside the network, or configure dhcp_relay for it")
        return unservable


    def dhcp_group_shares_link (self, network=None, carrier=None, networksbyname=None):
        """
        Whether every relayed member of a shared group sits on the same link as this one, judged by
        the relays they have in common.

        luna's 'shared' carries two meanings. For a host and its BMC it says "the same wire", and a
        link anchor there belongs to the whole group. For a relayed network it is only the
        precondition dhcp_relay insists on, and the members can be quite separate links - so an
        anchor merged into that group would be reachable from every relayed member in it, and
        selection would land on whichever the render happened to put first. Relays in common are
        the evidence that the link really is shared; a member with no relay is on the wire and
        cannot be picked out by a relay anyway, so it does not argue either way.
        """
        def relays (name):
            nwk = (networksbyname or {}).get(name) or {}
            return {relay.strip() for relay in (nwk.get('dhcp_relay') or '').split(',') if relay.strip()}
        mine = relays(network)
        for member, nwk in (networksbyname or {}).items():
            if member == network:
                continue
            if member != carrier and (nwk.get('shared') or '') != carrier:
                continue
            theirs = relays(member)
            if theirs and not (theirs & mine):
                return False
        return True


    def dhcp_shared_pools (self, subnets=None, pools=None, group=None, carrier=None,
                           members=None, fence=None, policy=True):
        """
        Give each member of a shared group the pool that the ISC template takes from POOLS, so the
        kea templates can render the group as one shared-networks block through the same subnet
        macro as everything else.

        With policy, each pool also carries the class ISC writes as 'allow/deny members of': a
        piggyback serves its own class, the carrier serves whatever is in none of them. DHCPv6
        expresses the same choice at subnet level already and passes policy=False, so its pools are
        left alone.

        kea's client-class holds one class NAME and never an expression - an expression is read as
        a name, matches nothing, and takes the subnet out of selection with no error anywhere - so
        the negation, and any combination with the link fence, are emitted as derived classes and
        referenced by name. They come back in dependency order, because kea refuses a member()
        reference to a class defined later in the list.
        """
        derived = []
        carrier_class = f"{group}-carrier-class"
        for name, subnet in (subnets or {}).items():
            pool = (pools or {}).get(group if name == carrier else name) or {}
            if 'range_begin' not in pool or 'range_end' not in pool:
                continue
            subnet['range_begin'], subnet['range_end'] = pool['range_begin'], pool['range_end']
            # A relayed member is picked out by its relay, so its pool takes no policy class -
            # the classes only tell apart members that share a wire, and they all carry the same
            # udhcp test. Classing a relayed pool refuses its own network's PXE clients, which
            # then fall through to the carrier's pool and boot on the wrong subnet.
            if policy and 'dhcp_relay' not in subnet:
                subnet['pool_class'] = carrier_class if name == carrier else f"{name}-class"
            elif fence:
                subnet['pool_class'] = fence
        if policy and members and any(s.get('pool_class') == carrier_class
                                      for s in (subnets or {}).values()):
            derived.append({'name': carrier_class,
                            'test': ' and '.join(f"not member('{m}-class')" for m in members)})
        if fence:
            for name, subnet in (subnets or {}).items():
                base = subnet.get('pool_class')
                if not base or base == fence:
                    continue
                fenced = f"{group}-{name}-pool-class"
                subnet['pool_class'] = fenced
                derived.append({'name': fenced,
                                'test': f"member('{base}') and member('{fence}')"})
        return derived


    def dhcp6_select_class (self, subnet=None, name=None, group=None, piggyback=False):
        """
        The one class name that gates selection of a DHCPv6 subnet, and its definition.

        DHCPv6 carries the boot URL in a class (option 59), so the templates have always gated each
        subnet on the boot classes built for it - a list, which is the kea 3.0 spelling and which
        kea 2.6 refuses outright, taking DHCPv4 down with it because both families install together.
        The same choice as one derived class works on both. A piggyback with a pool and no relay is
        gated on its own class instead, exactly as before.

        Returns (class name, definition or None). The definition is None when the name is a class
        the template already defines.
        """
        if piggyback and 'dhcp_relay' not in subnet:
            return f"{name}-class", None
        suffix = f"{group}-{name}" if group else name
        members = ['arch-openpower']
        if subnet.get('nextserver'):
            members = [f"ipxe-{suffix}", f"arch-x86-{suffix}", f"arch-arm64-{suffix}"] + members
        select = f"{suffix}-select-class"
        return select, {'name': select,
                        'test': ' or '.join(f"member('{member}')" for member in members)}


    def dhcp_link_anchors (self, value=None, ipversion='ipv4'):
        """
        Split a dhcp_link_subnet CSV into normalised anchor prefixes (network form, e.g.
        10.144.35.253/24 -> 10.144.35.0/24). Entries of the wrong family or that will not parse
        are skipped loudly rather than reaching the Kea config, where they would fail the whole
        subnet element. Validation in base/network.py should have caught these already.
        """
        want_ipv6 = (ipversion == 'ipv6')
        anchors = []
        for entry in (value or '').split(','):
            entry = entry.strip()
            if not entry:
                continue
            try:
                net = ip_network(entry, strict=False)
            except (ValueError, TypeError) as exp:
                self.logger.error(f"Skipping invalid dhcp_link_subnet anchor {entry}: {exp}")
                continue
            if (net.version == 6) != want_ipv6:
                self.logger.error(f"Skipping dhcp_link_subnet anchor {entry}: wrong family for {ipversion}")
                continue
            anchors.append(str(net))
        return anchors


    def dhcp_subnet_config (self,nwk=[],shared=False,ipversion='ipv4'):
        """
        dhcp subnetblock with config
        glue between the various other subnet blocks: prepare for dhcp_subnet function
        """
        subnet={}
        add_string=''
        if ipversion == 'ipv6':
            add_string='_ipv6'
        network_id = nwk['id']
        network_name = nwk['name']+add_string
        network_ip = nwk['network'+add_string]
        if nwk['dhcp'] and not shared and not nwk.get('dhcp_nodes_only'):
            if nwk['dhcp_range_begin'+add_string] and nwk['dhcp_range_end'+add_string]:
                subnet['range_begin']=nwk['dhcp_range_begin'+add_string]
                subnet['range_end']=nwk['dhcp_range_end'+add_string]
        netmask = nwk['subnet_ipv6']
        subnet['prefix'] = nwk['subnet_ipv6']
        if ipversion == 'ipv4':
            subnet['prefix'] = nwk['subnet']
            netmask = Helper().get_netmask(f"{nwk['network']}/{nwk['subnet']}")
        controller_name = Controller().get_beacon()
        # ---------------------------------------------------
        ha_object=HA()
        ha_enabled=ha_object.get_hastate()
        ha_insync=ha_object.get_insync()
        ha_master=ha_object.get_role()
        ha_me=ha_object.get_me()
        # ---------------------------------------------------
        if ha_enabled and ha_insync:
                controller_name = ha_me
        # ---------------------------------------------------
        controller = Database().get_record_join(
            ['ipaddress.ipaddress','ipaddress.ipaddress_ipv6','network.name as networkname'],
            ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
            ['tableref="controller"', f"controller.hostname='{controller_name}'"]
        )
        self.logger.info(f"Building DHCP block for {network_name}")
        subnet['network']=nwk['network'+add_string]
        subnet['netmask']=netmask
        subnet['domain']=nwk['name']
        subnet['nameserver_ip']=nwk['nameserver_ip']
        subnet['nameserver_ip_ipv6']=nwk['nameserver_ip_ipv6']
        subnet['ntp_server']=nwk['ntp_server']
        # An ntp_server may be an IPv4 address, an IPv6 address, or a host name. Each DHCP family can
        # only carry some of these: the dhcp4 ntp-servers option (42) takes IPv4 addresses, and the
        # dhcp6 ntp-server option (56) takes an IPv6 address (srv-addr) or a name (srv-fqdn). Classify
        # it once here - through the shared helper, never a hand-rolled test - so each template emits
        # only what its option accepts and drops what it cannot represent rather than feeding kea a
        # value it rejects (which fails the whole subnet element).
        if nwk['ntp_server']:
            if Helper().check_if_ipv6(nwk['ntp_server']):
                subnet['ntp_server_kind']='ipv6'
            elif Helper().check_ip(nwk['ntp_server']):
                subnet['ntp_server_kind']='ipv4'
            else:
                subnet['ntp_server_kind']='fqdn'
        # dhcp_relay is one field feeding both the dhcp4 and dhcp6 templates, and it has no _ipv6
        # twin to pick the family for us, so we filter here. a config may only carry its own family:
        # kea fails the whole subnet element on a mismatch - not just the relay line - so a single
        # IPv6 relay would take DHCPv4 down for everything in this subnet.
        relays = [relay.strip() for relay in (nwk.get('dhcp_relay') or '').split(',') if relay.strip()]
        relays = [relay for relay in relays if Helper().check_if_ipv6(relay) == (ipversion == 'ipv6')]
        if relays:
            subnet['dhcp_relay']=relays
        if nwk['gateway'+add_string] and nwk['gateway'+add_string] != "None": # left over from database().update/insert bug - Antoine
            subnet['gateway']=nwk['gateway'+add_string]
        if controller and (controller[0]['networkname'] == nwk['name'] or 'gateway' in subnet):
            # if the controller is in this network (cluster default as such), we can serve next-server stuff.
            # we allow to have an alternate route to the next-server (which is us) but ONLY when gateway is configured,
            # this is usefull if we want to support booting on other networks as well.
            serverport = 7050
            if CONSTANT['API']['PROTOCOL'] == 'https' and 'WEBSERVER' in CONSTANT and 'PORT' in CONSTANT['WEBSERVER']:
                # we rely on nginx serving non https stuff for e.g. /boot.
                # ipxe does support https but has issues dealing with self signed certificates
                serverport = CONSTANT['WEBSERVER']['PORT']
            if controller[0]['ipaddress'+add_string]:
                subnet['nextserver']=controller[0]['ipaddress'+add_string]
            else:
                subnet['nextserver']=controller[0]['ipaddress']
            subnet['nextport']=serverport
        if not controller:
            self.logger.warning(f"no controller details found using {controller_name}")
        if not 'nextserver' in subnet:
            self.logger.info(f"no next server defined for network {nwk['name']} using {controller_name}")
        self.logger.debug(f"SUBNET: {subnet}")
        return subnet

    def dhcp_zone_config (self,nwk=[],ipversion='ipv4'):
        """ 
        dhcp subnetblock with config
        glue between the variouszone blocks: prepare for dhcp_subnet function
        """
        zone={}
        rev = ''
        zone['domain'] = nwk['name']
        zone['primary'] = Controller().get_beaconip()
        zone['forward'] = nwk['name']
        if ipversion == 'ipv4':
            rev = ip_address(nwk['network']).reverse_pointer
            rev = rev.split('.')
            rev = '.'.join(rev[2:])
        elif ipversion == 'ipv6':
            rev = ip_address(nwk['network_ipv6']).reverse_pointer
            rev = rev.split('.')
            rev = '.'.join(rev[16:])
        zone['reverse'] = rev# + '.in-addr.arpa'
        self.logger.debug(f"ZONE: {zone}")
        return zone

    def dhcp_empty_config (self,nwk=[],ipversion='ipv4'):
        """
        for empty, non dhcp zones, just as declaration
        """
        subnet={}
        add_string=''
        if ipversion == 'ipv6':
            add_string='_ipv6'
        netmask = nwk['subnet_ipv6']
        if ipversion == 'ipv4':
            netmask = Helper().get_netmask(f"{nwk['network']}/{nwk['subnet']}")
        subnet['network']=nwk['network'+add_string]
        subnet['netmask']=netmask
        return subnet


    def dns_configure(self):
        """
        This method will write /etc/named.conf and zone files for every network
        """
        self.hooks_plugins = Helper().plugin_finder(f'{self.plugins_path}/hooks')
        dns_plugin = Helper().plugin_load(self.hooks_plugins, 'hooks/config', 'dns')
        validate = True
        mgmt_iface_ids = self.effective_mgmt_iface_ids()
        template_dns_conf = 'templ_dns_conf.cfg' # i.e. /etc/named.conf
        template_dns_zones_conf = 'templ_dns_zones_conf.cfg' # i.e. /etc/named.luna.zones
        template_dns_zone = 'templ_dns_zone.cfg' # the actual zone data
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template_dns_conf}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            self.logger.error(f"Error building dns config. {template_path} does not exist")
            return False
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template_dns_zones_conf}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            self.logger.error(f"Error building dns config. {template_path} does not exist")
            return False
        template_path = f'{CONSTANT["TEMPLATES"]["TEMPLATE_FILES"]}/{template_dns_zone}'
        check_template = Helper().check_jinja(template_path)
        if not check_template:
            self.logger.error(f"Error building dns config. {template_path} does not exist")
            return False
        file_loader = FileSystemLoader(CONSTANT["TEMPLATES"]["TEMPLATE_FILES"])
        env = Environment(loader=file_loader)

        omapikey=None
        tsigkey=None
        tsigalgo=None
        if 'OMAPIKEY' in CONSTANT['DHCP'] and CONSTANT['DHCP']['OMAPIKEY']:
            omapikey=CONSTANT['DHCP']['OMAPIKEY']
        if 'TSIGKEY' in CONSTANT['DHCP'] and 'TSIGALGO' in CONSTANT['DHCP']:
            if CONSTANT['DHCP']['TSIGKEY'] and CONSTANT['DHCP']['TSIGALGO']:
                tsigkey=CONSTANT['DHCP']['TSIGKEY']
                tsigalgo=CONSTANT['DHCP']['TSIGALGO']

        tmpdir=f"{CONSTANT['TEMPLATES']['TMP_DIRECTORY']}"
        files, forwarder = [], []
        unix_time = int(time())
        dns_allowed_query=['any']
        dns_zones=[]
        dns_zone_records={}
        dns_zone_forwarders={}
        dns_authoritative={}
        dns_rev_domain={}
        dns_dynamic_updates={}
 
        cluster = Database().get_record(table='cluster')
        controller = Database().get_record_join(
            ['ipaddress.ipaddress','ipaddress.ipaddress_ipv6','network.name as networkname'],
            ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
            ['tableref="controller"', 'controller.beacon=1']
        )
        if (not controller) or (not cluster):
            self.logger.error("Error building dns config. either controller or cluster does not exist")
            return False
        controller_name = Controller().get_beacon()
        controller_ip = controller[0]['ipaddress']
        controller_ip_ipv6 = controller[0]['ipaddress_ipv6']
        controller_network = controller[0]['networkname']
        if 'forwardserver_ip' in cluster[0] and cluster[0]['forwardserver_ip']:
            forwarder = cluster[0]['forwardserver_ip'].split(',')
        bind_legacy = bool(cluster[0].get('bind_legacy'))
        dnssec_enable = None
        dnssec_validation = None
        if bind_legacy and cluster[0].get('dnssec_enable') is not None:
            dnssec_enable = 'yes' if cluster[0]['dnssec_enable'] else 'no'
        if cluster[0].get('dnssec_validation') is not None and dnssec_enable != 'no':
            dnssec_validation = 'yes' if cluster[0]['dnssec_validation'] else 'no'
        self.logger.info(f"bind_legacy: {bind_legacy}, dnssec_enable: {dnssec_enable}, dnssec validation: {dnssec_validation}")
        networks = Database().get_record(table='network')
        if networks:
            dns_allowed_query=['127.0.0.0/8']
 
        controller_ips = []
        for nwk in networks:
            network_id = nwk['id']
            networkname = None
            rev_ip, rev_ipv6 = None, None
            if (nwk['network'] or nwk['network_ipv6']) and nwk['name']:
                networkname = nwk['name']
                dns_dynamic_updates[networkname] = nwk['dhcp_nodes_in_pool'] or False
                self.logger.info(f"Building DNS block for {networkname}")
                try:
                    if nwk['network']:
                        rev_ip = ip_address(nwk['network']).reverse_pointer
                        rev_ip = rev_ip.split('.')
                        rev_ip = '.'.join(rev_ip[2:])
                        dns_allowed_query.append(nwk['network']+"/"+nwk['subnet']) # used for e.g. named. allow query
                        self.logger.info(f"Building DNS block for {rev_ip}")
                    if nwk['network_ipv6']:
                        rev_ipv6 = ip_address(nwk['network_ipv6']).reverse_pointer
                        rev_ipv6 = rev_ipv6.split('.')
                        rev_ipv6 = '.'.join(rev_ipv6[16:])
                        dns_allowed_query.append(nwk['network_ipv6']+"/"+nwk['subnet_ipv6'])
                        self.logger.info(f"Building DNS block for {rev_ipv6}")
                except Exception as exp:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    self.logger.error(f"defining DNS networks encountered problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")
                #
                dns_zones.append(networkname)
                dns_zone_records[networkname]={}

                # we always add a zone record for controller even when we're actually in it. we can override.
                dns_zone_records[networkname][controller_name]={}
                dns_zone_records[networkname][controller_name]['key']=controller_name
                if nwk['network_ipv6'] and controller_ip_ipv6:
                    dns_zone_records[networkname][controller_name]['type']='AAAA'
                    dns_zone_records[networkname][controller_name]['value']=controller_ip_ipv6
                else:
                    dns_zone_records[networkname][controller_name]['type']='A'
                    dns_zone_records[networkname][controller_name]['value']=controller_ip

                authoritative_server=None
                dns_zone_forwarders[networkname]=[]
                if not nwk['non_authoritative']:
                    authoritative_server=f"{controller_name}.{networkname}"
                dns_authoritative[networkname]=authoritative_server
                if nwk['nameserver_ip']:
                    dns_zone_forwarders[networkname] += nwk['nameserver_ip'].split(',')
                if nwk['nameserver_ip_ipv6']:
                    dns_zone_forwarders[networkname] += nwk['nameserver_ip_ipv6'].split(',')
                if len(dns_zone_forwarders[networkname]) == 0:
                    dns_zone_forwarders[networkname]=forwarder

            mergedlist = []
            controllers = Database().get_record_join(
                ['controller.hostname as host', 'ipaddress.ipaddress',
                 'ipaddress.ipaddress_ipv6','network.name as networkname'],
                ['ipaddress.tablerefid=controller.id','network.id=ipaddress.networkid'],
                ['ipaddress.tableref="controller"', f'ipaddress.networkid="{network_id}"']
            )
            if controllers:
                mergedlist.append(controllers)
                for controller in controllers:
                    if controller['ipaddress']:
                        controller_ips.append(controller['ipaddress'])
                    if controller['ipaddress_ipv6']:
                        controller_ips.append(controller['ipaddress_ipv6'])
            nodes = Database().get_record_join(
                ['node.name as host', 'ipaddress.ipaddress', 'ipaddress.ipaddress_ipv6',
                  'ipaddress.dhcp', 'network.name as networkname'],
                ['ipaddress.tablerefid=nodeinterface.id', 'nodeinterface.nodeid=node.id',
                 'network.id=ipaddress.networkid'],
                ['tableref="nodeinterface"', f'ipaddress.networkid="{network_id}"']
            )
            if nodes:
                mergedlist.append(nodes)

            for item in ['otherdevices','switch']:
                devices = Database().get_record_join(
                    [f'{item}.name as host', 'ipaddress.ipaddress',
                     'ipaddress.ipaddress_ipv6', 'network.name as networkname'],
                    [f'ipaddress.tablerefid={item}.id', 'network.id=ipaddress.networkid'],
                    [f'tableref="{item}"', f'ipaddress.networkid="{network_id}"']
                )
                if devices:
                    mergedlist.append(devices)

            # switch interfaces resolve as <switch>-<interface> so multiple interfaces of one
            # switch on the same network do not collide on the bare switch name. The join through
            # ipaddress+network self-gates: only an interface with an IP on an existing network
            # appears here, so a mac-only interface is skipped (it has no zone to live in).
            switch_ifaces = Database().get_record_join(
                ['switch.name as switchname', 'switchinterface.interface as interface',
                 'switchinterface.id as ifid',
                 'ipaddress.ipaddress', 'ipaddress.ipaddress_ipv6', 'network.name as networkname'],
                ['ipaddress.tablerefid=switchinterface.id', 'switchinterface.switchid=switch.id',
                 'network.id=ipaddress.networkid'],
                ['ipaddress.tableref="switchinterface"', f'ipaddress.networkid="{network_id}"']
            )
            if switch_ifaces:
                for switch_iface in switch_ifaces:
                    if switch_iface['ifid'] in mgmt_iface_ids:
                        switch_iface['host'] = switch_iface['switchname']
                    else:
                        switch_iface['host'] = f"{switch_iface['switchname']}-{switch_iface['interface']}"
                mergedlist.append(switch_ifaces)

            additional = Database().get_record_join(
                    ['dns.*','network.name as networkname'],
                    ['dns.networkid=network.id'],
                    [f"network.name='{networkname}'"])
            if additional:
                mergedlist.append(additional)

            # --------------------------------------------------------------------------------------------------
            # The big part where we go through each and every node, switch and controller in the mergedlist
            # and sort them out for forward and reverse ptr dns zones
            # --------------------------------------------------------------------------------------------------
            for hosts in mergedlist:
                for host in hosts:
                    if nwk['dhcp_nodes_in_pool']:
                        if 'dhcp' in host and host['dhcp']:
                            continue
                            # bit tricky situation as bind has a journal for the pure dhcp nodes
                            # but we create a zone with the non dhcp ones. this is known
                            # to clash and we might have to resort to nspdate through a plugin
                    try:
                        dns_zone_records[networkname][host['host']]={}
                        dns_zone_records[networkname][host['host']]['key']=host['host'].rstrip('.')
                        ipaddress = None
                        # --------------------------------------------------------------------------------------
                        # IPv6 ---------------------------------------------------------------------------------
                        # --------------------------------------------------------------------------------------
                        if 'ipaddress_ipv6' in host and host['ipaddress_ipv6']:
                            # ----- forward
                            dns_zone_records[networkname][host['host']]['type']='AAAA'
                            dns_zone_records[networkname][host['host']]['value']=host['ipaddress_ipv6']
                            ipaddress = host['ipaddress_ipv6']
                            self.logger.debug(f"DNS -- IPv6: host {host['host']}, AAAA ip [{host['ipaddress_ipv6']}]")
                            # ----- all reverse pointer PTR below
                            rev_ipv6 = ip_address(nwk['network_ipv6']).reverse_pointer
                            rev_ipv6 = rev_ipv6.split('.')
                            rev_ipv6 = '.'.join(rev_ipv6[16:])
                            if rev_ipv6:
                                ipv6_rev = ip_address(host['ipaddress_ipv6']).reverse_pointer
                                ipv6_list = ipv6_rev.split('.')
                                host_ptr = '.'.join(ipv6_list[0:16])
                                self.logger.debug(f"DNS -- IPv6: host {host['host']}, rev net [{rev_ipv6}], rev ip [{host_ptr}]")
                                if rev_ipv6 and rev_ipv6 not in dns_zones:
                                    dns_zones.append(rev_ipv6)
                                    dns_rev_domain[rev_ipv6]=networkname
                                    dns_dynamic_updates[rev_ipv6] = nwk['dhcp_nodes_in_pool'] or False
                                if rev_ipv6 not in dns_zone_records.keys():
                                    dns_zone_records[rev_ipv6]={}
                                    dns_authoritative[rev_ipv6]=authoritative_server
                                    dns_zone_forwarders[rev_ipv6]=dns_zone_forwarders[networkname]
                                if host['host'] not in dns_zone_records[rev_ipv6].keys():
                                    dns_zone_records[rev_ipv6][host['host']]={}
                                    dns_zone_records[rev_ipv6][host['host']]['key']=host_ptr
                                    dns_zone_records[rev_ipv6][host['host']]['type']='PTR'
                                    dns_zone_records[rev_ipv6][host['host']]['value']=f"{host['host'].rstrip('.')}.{host['networkname']}"
                        # --------------------------------------------------------------------------------------
                        # IPv4 ---------------------------------------------------------------------------------
                        # --------------------------------------------------------------------------------------
                        elif host['ipaddress']:
                            # ----- forward
                            dns_zone_records[networkname][host['host']]['type']='A'
                            dns_zone_records[networkname][host['host']]['value']=host['ipaddress']
                            ipaddress = host['ipaddress']
                            self.logger.debug(f"DNS -- IPv4: host {host['host']}, A ip [{host['ipaddress']}]")
                            # ----- all reverse pointer PTR below
                            rev_ip = ip_address(host['ipaddress']).reverse_pointer
                            rev_ip = rev_ip.split('.')
                            rev_ip = '.'.join(rev_ip[1:])
                            if rev_ip:
                                sub_ip = host['ipaddress'].split('.')
                                if len(sub_ip) == 4:
                                    host_ptr = sub_ip[3]
                                    self.logger.debug(f"DNS -- IPv4: host {host['host']}, rev net [{rev_ip}], rev ip [{host_ptr}]")
                                    if rev_ip not in dns_zones:
                                        dns_zones.append(rev_ip)
                                        dns_rev_domain[rev_ip]=networkname
                                        dns_dynamic_updates[rev_ip] = nwk['dhcp_nodes_in_pool'] or False
                                    if rev_ip not in dns_zone_records.keys():
                                        dns_zone_records[rev_ip]={}
                                        dns_authoritative[rev_ip]=authoritative_server
                                        dns_zone_forwarders[rev_ip]=dns_zone_forwarders[networkname]
                                    if host['host'] not in dns_zone_records[rev_ip].keys():
                                        dns_zone_records[rev_ip][host['host']]={}
                                        dns_zone_records[rev_ip][host['host']]['key']=host_ptr
                                        dns_zone_records[rev_ip][host['host']]['type']='PTR'
                                        dns_zone_records[rev_ip][host['host']]['value']=f"{host['host'].rstrip('.')}.{host['networkname']}"
                        # --------------------------------------------------------------------------------------
                        # DHCP ---------------------------------------------------------------------------------
                        # --------------------------------------------------------------------------------------
                        else: # we have nothing! are we doing pure dhcp?
                            if not host['dhcp']:
                                self.logger.warning(f"node {host['host']} does not appear to have any ipaddress configured")
                            del dns_zone_records[networkname][host['host']]
                        if ipaddress and nwk['dhcp_nodes_in_pool']:
                            return_code, message = dns_plugin().nsupdate(host=f"{host['host']}.{networkname}", ipaddress=ipaddress, ttl=3600,
                                                                         key_name='omapi_key', key_secret=omapikey)
                    except Exception as exp:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        self.logger.error(f"creating DNS zone encountered problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")

        # we create the zone files with zone info like addresses
        for zone in dns_zones:
            if not dns_authoritative[zone]:
                continue
            zone_file = {
                'source': f'{tmpdir}/{zone}.luna.zone',
                'destination': f'/var/named/{zone}.luna.zone'
            }
            files.append(zone_file)
            try:
                dns_zone_template = env.get_template(template_dns_zone)
                dns_zone_config = dns_zone_template.render(RECORDS=dns_zone_records[zone],
                                                           AUTHORITATIVE_SERVER=dns_authoritative[zone],
                                                           SERIAL=unix_time)
                with open(f'{tmpdir}/{zone}.luna.zone', 'w', encoding='utf-8') as filename:
                    filename.write(dns_zone_config)
                try:
                    zone_cmd = ['named-checkzone', f'luna.{zone}', f'{tmpdir}/{zone}.luna.zone']
                    validate_zone_name = subprocess.run(zone_cmd, check = True)
                    if validate_zone_name.returncode:
                        validate = False
                        self.logger.error(f'DNS zone file: {tmpdir}/{zone}.luna.zone containing errors.')
                except Exception as exp:
                    self.logger.error(f'DNS zone file: {tmpdir}/{zone}.luna.zone containing errors. {exp}')
            except Exception as exp:
                self.logger.error(f"Uh oh... {exp}")

        # we create the actual /etc/named.conf and /etc/named.luna.zones
        managed_keys="/trinity/local/var/lib/named/dynamic"
        if not os.path.exists(managed_keys):
            managed_keys=None
        dns_conf_template = env.get_template(template_dns_conf)
        dns_conf_config = dns_conf_template.render(ALLOWED_QUERY=dns_allowed_query,FORWARDERS=forwarder,
                                                   MANAGED_KEYS=managed_keys,OMAPIKEY=omapikey,
                                                   TSIGKEY=tsigkey,TSIGALGO=tsigalgo,
                                                   BIND_LEGACY=bind_legacy,
                                                   DNSSEC_ENABLE=dnssec_enable,
                                                   DNSSEC_VALIDATION=dnssec_validation)
        dns_zones_conf_template = env.get_template(template_dns_zones_conf)
        dns_zones_conf_config = dns_zones_conf_template.render(ZONES=dns_zones,OMAPIKEY=omapikey,
                                                               TSIGKEY=tsigkey,TSIGALGO=tsigalgo,
                                                               AUTHORITATIVE=dns_authoritative,
                                                               FORWARDERS=dns_zone_forwarders,
                                                               ALLOW_UPDATES=controller_ips,
                                                               DYNAMIC_UPDATES=dns_dynamic_updates)

        dns_file = {'source': f'{tmpdir}/named.conf', 'destination': '/etc/named.conf'}
        files.append(dns_file)
        dns_zone_file = {
                'source': f'{tmpdir}/named.luna.zones',
                'destination': '/etc/named.luna.zones'
        }
        files.append(dns_zone_file)
        try:
            with open(dns_file["source"], 'w', encoding='utf-8') as dns:
                dns.write(dns_conf_config)
            with open(dns_zone_file["source"], 'w', encoding='utf-8') as dns_zone:
                dns_zone.write(dns_zones_conf_config)
            if validate:
                if not os.path.exists('/var/named'):
                    os.makedirs('/var/named')
                for dns_files in files:
                    shutil.copyfile(dns_files["source"], dns_files["destination"])
        except Exception as exp:
            self.logger.error(f"Uh oh... {exp}")
        return validate


    # ----------------------------------------------------------------------------------------------

    def device_raw_ipaddress_config(self, device_id=None, device=None, ipaddress=None):
        """
        This method will set the ipaddress as is. no checks.
        """
        if not ipaddress:
            return False, "IP address not supplied"
        result_ip = False
        my_ipaddress = {}
        if Helper().check_if_ipv6(ipaddress):
            my_ipaddress={'ipaddress_ipv6': ipaddress, 'networkid': None}
        else:
            my_ipaddress={'ipaddress': ipaddress, 'networkid': None}
        where = f'tablerefid = "{device_id}" AND tableref = "{device}"'
        check_ip = Database().get_record(table='ipaddress', where=where)
        if check_ip:
            row = Helper().make_rows(my_ipaddress)
            where = [
                {"column": "tablerefid", "value": device_id},
                {"column": "tableref", "value": device}
            ]
            result_ip=Database().update('ipaddress', row, where)
        else:
            my_ipaddress['tableref'] = device
            my_ipaddress['tablerefid'] = device_id
            row = Helper().make_rows(my_ipaddress)
            result_ip=Database().insert('ipaddress', row)
            self.logger.info(f"IP for {device} created => {result_ip}.")
        if result_ip is False:
            return False,"IP address assignment failed"
        return True,"ipaddress changed"

    def device_ipaddress_config(self, device_id=None, device=None, ipaddress=None, network=None):
        """
        This method will verify the ipaddress with supplied or pre-configured network and sets it 
        """
        if network:
            network_id = Database().id_by_name('network', network)
        else:
            network_details = Database().get_record_join(
                ['network.name as network', 'network.id'],
                [f'ipaddress.tablerefid={device}.id', 'network.id=ipaddress.networkid'],
                [f'tableref="{device}"', f"{device}.id='{device_id}'"]
            )
            if network_details:
                network_id = network_details[0]['id']
            else:
                return False,"Network not specified"
        if ipaddress and device_id and network_id:
            my_ipaddress = {}
            my_ipaddress['networkid'] = network_id
            result_ip, valid_ip = False, None
            network_details = Database().get_record(table='network', where=f"id='{network_id}'")
            if Helper().check_if_ipv6(ipaddress):
                valid_ip = Helper().check_ip_range(
                    ipaddress,
                    f"{network_details[0]['network_ipv6']}/{network_details[0]['subnet_ipv6']}"
                )
            else:
                valid_ip = Helper().check_ip_range(
                    ipaddress,
                    f"{network_details[0]['network']}/{network_details[0]['subnet']}"
                )
            self.logger.info(f"Ipaddress {ipaddress} for {device} is [{valid_ip}]")
            if valid_ip is False:
                message = f"invalid IP address for {device}. Network {network_details[0]['name']}: "
                message += f"{network_details[0]['network']}/{network_details[0]['subnet']}"
                return False, message

            if Helper().check_if_ipv6(ipaddress):
                my_ipaddress['ipaddress_ipv6']=ipaddress
            else:
                my_ipaddress['ipaddress']=ipaddress
            where = f'tablerefid = "{device_id}" AND tableref = "{device}"'
            check_ip = Database().get_record(table='ipaddress', where=where)
            if check_ip:
                row = Helper().make_rows(my_ipaddress)
                where = [
                    {"column": "tablerefid", "value": device_id},
                    {"column": "tableref", "value": device}
                ]
                Database().update('ipaddress', row, where)
            else:
                my_ipaddress['tableref'] = device
                my_ipaddress['tablerefid'] = device_id
                row = Helper().make_rows(my_ipaddress)
                result_ip=Database().insert('ipaddress', row)
                self.logger.info(f"IP for {device} created => {result_ip}.")
                if result_ip is False:
                    return False,"IP address assignment failed"
            return True,"ipaddress changed"
        return False,"not enough details"

    def device_interface_clear_ipaddress(self, device_id=None, device=None, ipversion='ipv4'):
        """Clear (None) one address family of a device interface's ipaddress row, leaving the other
        family untouched. Generic, device-parameterised parallel of device_ipaddress_config; device
        is the tableref (e.g. 'switchinterface'). Mirrors node_interface_clear_ipaddress but by
        tableref so it is not node-specific."""
        where = f'tableref="{device}" AND tablerefid={device_id}'
        check_ipaddress = Database().get_record(table='ipaddress', where=where)
        if not check_ipaddress:
            return True, "interface had no address configuration to clear"
        clear_ip = {}
        if ipversion == 'ipv4':
            clear_ip['ipaddress'] = None
        if ipversion == 'ipv6':
            clear_ip['ipaddress_ipv6'] = None
        row = Helper().make_rows(clear_ip)
        result = Database().update('ipaddress', row,
                                   [{"column": "tableref", "value": device},
                                    {"column": "tablerefid", "value": device_id}])
        if result:
            return True, f"{ipversion} address cleared"
        return False, f"failed to clear {ipversion} address"

    # ----------------------------------------------------------------------------------------------

    def node_interface_rename(self, nodeid=None, interface_name=None, new_interface_name=None):
        """
        This method renames the interface name for a given interface.
        It validates whether all minimum requirements are met before proceeding
        """
        result_if = False
        my_interface = {}

        where_interface = f'nodeid = "{nodeid}"'
        check_interface = Database().get_record(table='nodeinterface', where=where_interface)
        interface_byname = Helper().convert_list_to_dict(check_interface, 'interface')

        if not check_interface: # ----> easy. interfaces do not exist
            message = f"no interfaces defined"
            return False, message
        elif interface_name not in interface_byname.keys():
            message = f"interface {interface_name} does not exist"
            return False, message
        elif interface_name == new_interface_name:
            message = f"current and new interface name are the same"
            return False, message
        elif new_interface_name in interface_byname.keys():
            message = f"interface {new_interface_name} already exists"
            return False, message
        else:
            # we have to update the interface
            my_interface['interface'] = new_interface_name
            row = Helper().make_rows(my_interface)
            where = [{"column": "id", "value": interface_byname[interface_name]['id']}]
            result_if = Database().update('nodeinterface', row, where)

        if result_if:
            message = f"interface {interface_name} renamed to {new_interface_name}"
            return True, message
        message = f"interface {interface_name} could not be renamed"
        return False, message


    def node_interface_config(self, nodeid=None, interface_name=None, macaddress=None, mtu=None, vlanid=None, vlan_parent=None, bond_mode=None, bond_slaves=None, options=None):
        """
        This method will collect node interfaces and return configuration.
        """
        result_if = False
        my_interface = {}

        if mtu and ((not mtu.isnumeric()) or int(mtu) > 65535 or int(mtu) < 68):
            message = f"mtu size out of range"
            return False, message
        elif bond_mode and bond_mode not in ['balance-rr','active-backup','balance-xor',
                                           'broadcast','802.3ad','balance-tlb','balance-alb',
                                           '0','1','2','3','4','5','6']:
            message = f"bonding mode {bond_mode} not supported." 
            message += "choose from balance-rr, active-backup, balance-xor, broadcast, 802.3ad, balance-tlb or balance-alb"
            return False, message
        elif vlanid and ((not vlanid.isnumeric()) or int(vlanid) > 4096):
            message = "vlanid has to be a value between 0 and 4096"
            return False, message
        elif (bond_mode or bond_slaves) and vlan_parent:
            message = f"bonded interface can not have a vlan_parent"
            return False, message

        where_interface = f'nodeid = "{nodeid}" AND interface = "{interface_name}"'
        check_interface = Database().get_record(table='nodeinterface', where=where_interface)

        if bond_slaves or bond_mode or vlan_parent or mtu:
            if check_interface:
                if (bond_mode or bond_slaves) and check_interface[0]['vlan_parent']:
                    message = "bonding interface using a vlan_parent not supported"
                    return False, message
                elif vlan_parent and (check_interface[0]['bond_mode'] or check_interface[0]['bond_slaves']):
                    message = "bonding interface using a vlan_parent not supported"
                    return False, message
                elif vlan_parent and (not vlanid) and not check_interface[0]['vlanid']:
                    message = "vlan_parent requires a vlanid"
                    return False, message
                elif bond_slaves and (not bond_mode) and not check_interface[0]['bond_mode']:
                    message = "bonding requires a bond_mode and bond_slaves"
                    return False, message
                elif bond_mode and (not bond_slaves) and not check_interface[0]['bond_slaves']:
                    message = "bonding requires a bond_mode and bond_slaves"
                    return False, message
                elif check_interface[0]['vlan_parent'] and mtu:
                    message = "MTU cannot be set on an interface with a vlan_parent"
                    return False, message
                elif vlan_parent and check_interface[0]['mtu']:
                    my_interface['mtu'] = None # we clear the MTU as it's the parent who sets it
            elif vlan_parent and mtu:
                message = "MTU cannot be set on an interface with a vlan_parent"
                return False, message
            elif vlan_parent and not vlanid:
                message = "vlan_parent requires a vlanid"
                return False, message
            elif bond_mode and not bond_slaves:
                message = "bonding requires a bond_mode and bond_slaves"
                return False, message
            elif bond_slaves and not bond_mode:
                message = "bonding requires a bond_mode and bond_slaves"
                return False, message
                   
        if macaddress is not None:
            my_interface['macaddress'] = macaddress.lower()
        if mtu is not None:
            my_interface['mtu'] = mtu
        if options is not None:
            my_interface['options'] = options
        if vlanid is not None:
            my_interface['vlanid'] = vlanid
        if vlan_parent is not None:
            my_interface['vlan_parent'] = vlan_parent
        if bond_mode is not None:
            my_interface['bond_mode'] = bond_mode
        if bond_slaves is not None:
            bond_slaves = bond_slaves.replace(' ',',')
            bond_slaves = bond_slaves.replace(',,',',')
            my_interface['bond_slaves'] = bond_slaves
            if (bond_slaves.count(',') < 1):
                message = f"bond_slaves should contain at least two interfaces"
                return False, message

        # we force a NULL in the database - clean
        for item in ['macaddress','mtu','options','vlanid','vlan_parent','bond_mode','bond_slaves']:
            if item in my_interface and not my_interface[item]:
                my_interface[item] = None
                if item == 'vlanid':
                   my_interface['vlan_parent'] = None
                elif item == 'bond_mode':
                   my_interface['bond_slaves'] = None

        if not check_interface: # ----> easy. both the interface and ipaddress do not exist
            my_interface['interface'] = interface_name
            my_interface['nodeid'] = nodeid
            row = Helper().make_rows(my_interface)
            result_if = Database().insert('nodeinterface', row)
        else:
            # we have to update the interface
            if my_interface:
                row = Helper().make_rows(my_interface)
                where = [{"column": "id", "value": check_interface[0]['id']}]
                result_if = Database().update('nodeinterface', row, where)
            else:
                # no change here, we bail
                result_if=True

        if result_if:
            message = f"interface {interface_name} created or changed with result {result_if}"
            self.logger.info(message)
            return True, message
        message = f"interface {interface_name} config failed with result {result_if}"
        self.logger.info(message)
        return False, message

    # ----------------------------------------------------------------------------------------------

    def node_interface_clear_ipaddress(self, nodeid, interface_name, ipversion='ipv4'):
        """
        This method will clear (None) the ipaddress config of a given node interface
        """
        where_interface = f'nodeid = "{nodeid}" AND interface = "{interface_name}"'
        check_interface = Database().get_record(table='nodeinterface', where=where_interface)
        result_if = "not able to clear ipaddress config. interface not configured"
        if check_interface:
            tablerefid = check_interface[0]['id']
            where_ipaddress = f'tableref="nodeinterface" AND tablerefid={tablerefid}'
            check_ipaddress = Database().get_record(table='ipaddress', where=where_ipaddress)
            if check_ipaddress:
                clear_ip={}
                if ipversion == 'ipv4':
                    clear_ip['ipaddress'] = None
                if ipversion == 'ipv6':
                    clear_ip['ipaddress_ipv6'] = None
                row = Helper().make_rows(clear_ip)
                where = [{"column": "tableref", "value": "nodeinterface"},
                         {"column": "tablerefid", "value": tablerefid}]
                result_if = Database().update('ipaddress', row, where)
            else:
                message = f"interface {interface_name} had no address configuration and did not to be cleared"
                self.logger.info(message)
                return True, message
            if result_if:
                message = f"interface {interface_name} cleared of {ipversion} address with result {result_if}"
                self.logger.info(message)
                return True, message
        message = f"interface {interface_name} config failed with result {result_if}"
        self.logger.info(message)
        return False, message


    def node_interface_dhcp_config(self, nodeid, interface_name, dhcp, network=None):
        """
        This method sets dhcp for interface of nodes.
        """
        result_ip = False
        my_dhcp = {}

        if network is not None:
            network_details = Database().get_record(table='network', where=f'name="{network}"')
        else:
            network_details = Database().get_record_join(
                ['network.*'],
                ['ipaddress.tablerefid=nodeinterface.id', 'network.id=ipaddress.networkid'],
                [
                    'tableref="nodeinterface"',
                    f'nodeinterface.nodeid="{nodeid}"',
                    f'nodeinterface.interface="{interface_name}"'
                ]
            )

        if not network_details:
            message = "not enough information provided. network name incorrect or need network name if there is no existing config for dhcp"
            self.logger.info(message)
            return False, message

        my_dhcp['networkid'] = network_details[0]['id']
        dhcp = Helper().bool_to_string(dhcp)
        my_dhcp['dhcp'] = dhcp
        if my_dhcp['dhcp'] not in ['0','1']:
            message = f"dhcp should be y, yes, n or no"
            return False, message

        my_interface = Database().get_record_join(
            ['ipaddress.*'],
            ['ipaddress.tablerefid=nodeinterface.id'],
            [
                'tableref="nodeinterface"',
                f'nodeinterface.nodeid="{nodeid}"',
                f'nodeinterface.interface="{interface_name}"'
                ]
            )

        if my_interface: # existing ip config we need to modify
            row = Helper().make_rows(my_dhcp)
            where = [{"column": "id", "value": my_interface[0]['id']}]
            result_ip = Database().update('ipaddress', row, where)

        else:
            # no config set yet for the interface
            where = f'nodeid = "{nodeid}" AND interface = "{interface_name}"'
            my_interface = Database().get_record(table='nodeinterface', where=where)
            if my_interface:
                my_dhcp['tableref'] = 'nodeinterface'
                my_dhcp['tablerefid'] = my_interface[0]['id']
                row = Helper().make_rows(my_dhcp)
                result_ip = Database().insert('ipaddress', row)

        if result_ip:
            message = f"dhcp configured for {interface_name} with result {result_ip}"
            self.logger.info(message)
            return True, message
        message = f"dhcp config for {interface_name} failed with result {result_ip}"
        self.logger.info(message)
        return False, message


    def node_interface_ipaddress_config(self, nodeid, interface_name, ipaddress, network=None, force=False):
        """
        This method configures ipaddresses for interface of nodes.
        """
        ipaddress_check, valid_ip, result_ip = False, False, False
        my_ipaddress = {}
        message = ''

        if network is not None:
            network_details = Database().get_record(table='network', where=f'name="{network}"')
        else:
            network_details = Database().get_record_join(
                ['network.*'],
                ['ipaddress.tablerefid=nodeinterface.id', 'network.id=ipaddress.networkid'],
                [
                    'tableref="nodeinterface"',
                    f'nodeinterface.nodeid="{nodeid}"',
                    f'nodeinterface.interface="{interface_name}"'
                ]
            )

        if not network_details:
            message = "not enough information provided. network name incorrect or need network name if there is no existing ipaddress"
            self.logger.info(message)
            return False, message

        my_ipaddress['networkid'] = network_details[0]['id']
        if ipaddress:
            if Helper().check_if_ipv6(ipaddress):
                my_ipaddress['ipaddress_ipv6'] = ipaddress
                valid_ip = Helper().check_ip_range(
                    ipaddress,
                    f"{network_details[0]['network_ipv6']}/{network_details[0]['subnet_ipv6']}"
                )
            else:
                my_ipaddress['ipaddress'] = ipaddress
                valid_ip = Helper().check_ip_range(
                    ipaddress,
                    f"{network_details[0]['network']}/{network_details[0]['subnet']}"
                )

        if not valid_ip:
            message = f"invalid IP address {ipaddress} for {interface_name}. "
            message += f"Network {network_details[0]['name']}: "
            if network_details[0]['network']:
                message += f"{network_details[0]['network']}/{network_details[0]['subnet']}"+" "
            if network_details[0]['network_ipv6']:
                message += f"{network_details[0]['network_ipv6']}/{network_details[0]['subnet_ipv6']}"
            self.logger.info(message)
            return False, message

        if ipaddress:
            ipaddress_check = Database().get_record(table='ipaddress', where=f"ipaddress='{ipaddress}' or ipaddress_ipv6='{ipaddress}'")
            if ipaddress_check:
                ipaddress_type='ipaddress'
                ipversion='ipv4'
                if Helper().check_if_ipv6(ipaddress):
                    ipaddress_type='ipaddress_ipv6'
                    ipversion='ipv6'
                ipaddress_check_own = Database().get_record_join(
                    ['node.id as nodeid','node.name as nodename','nodeinterface.interface'],
                    ['ipaddress.tablerefid=nodeinterface.id','nodeinterface.nodeid=node.id'],
                    ['tableref="nodeinterface"',f"ipaddress.{ipaddress_type}='{ipaddress}'"]
                )
                if ipaddress_check_own and ((ipaddress_check_own[0]['nodeid'] != nodeid) or (interface_name != ipaddress_check_own[0]['interface'])):
                    if not force:
                        message = f"ipaddress {ipaddress} is already in use "
                        message += f"on interface {ipaddress_check_own[0]['interface']} "
                        message += f"for node {ipaddress_check_own[0]['nodename']}"
                        return False, message
                    else:
                        status, message = self.node_interface_clear_ipaddress(
                            ipaddress_check_own[0]['nodeid'],
                            ipaddress_check_own[0]['interface'],
                            ipversion=ipversion
                        )
                        if not status:
                            message = f"ipaddress {ipaddress} on interface "
                            message += f"{ipaddress_check_own[0]['interface']} "
                            message += f"for node {ipaddress_check_own[0]['nodename']} "
                            message += "could not be cleared"
                            return False, message
                        message = f"ipaddress {ipaddress} cleared on interface "
                        message += f"{ipaddress_check_own[0]['interface']} "
                        message += f"for node {ipaddress_check_own[0]['nodename']}, "

        my_interface = Database().get_record_join(
            ['ipaddress.*'],
            ['ipaddress.tablerefid=nodeinterface.id'],
            [
                'tableref="nodeinterface"',
                f'nodeinterface.nodeid="{nodeid}"',
                f'nodeinterface.interface="{interface_name}"'
                ]
            )

        if my_interface: # existing ip config we need to modify
            row = Helper().make_rows(my_ipaddress)
            where = [{"column": "id", "value": my_interface[0]['id']}]
            result_ip = Database().update('ipaddress', row, where)

        else:
            # no ip set yet for the interface
            where = f'nodeid = "{nodeid}" AND interface = "{interface_name}"'
            my_interface = Database().get_record(table='nodeinterface', where=where)
            if my_interface:
                my_ipaddress['tableref']='nodeinterface'
                my_ipaddress['tablerefid']=my_interface[0]['id']
                row = Helper().make_rows(my_ipaddress)
                result_ip = Database().insert('ipaddress', row)

        if result_ip:
            message += f"ipaddress {ipaddress} for {interface_name} configured successfully"
            self.logger.info(message+f"  with result {result_ip}")
            return True, message
        message = f"ipaddress {ipaddress} for {interface_name} config failed"
        self.logger.info(message+f" with result {result_ip}")
        return False, message

    # ----------------------------------------------------------------------------------------------

    def group_interface_rename(self, groupid=None, interface_name=None, new_interface_name=None):
        """
        This method renames the interface name for a given interface.
        """
        result_if = False
        my_interface = {}

        where_interface = f'groupid = "{groupid}"'
        check_interface = Database().get_record(table='groupinterface', where=where_interface)
        interface_byname = Helper().convert_list_to_dict(check_interface, 'interface')

        if not check_interface: # ----> easy. interfaces do not exist
            message = f"no interfaces defined"
            return False, message
        elif interface_name not in interface_byname.keys():
            message = f"interface {interface_name} does not exist"
            return False, message
        elif interface_name == new_interface_name:
            message = f"current and new interface name are the same"
            return False, message
        elif new_interface_name in interface_byname.keys():
            message = f"interface {new_interface_name} already exists"
            return False, message
        else:
            # we have to update the interface
            my_interface['interface'] = new_interface_name
            row = Helper().make_rows(my_interface)
            where = [{"column": "id", "value": interface_byname[interface_name]['id']}]
            result_if = Database().update('groupinterface', row, where)

        if result_if:
            message = f"interface {interface_name} renamed to {new_interface_name}"
            return True, message
        message = f"interface {interface_name} could not be renamed"
        return False, message


    def group_interface_config(self, groupid=None, interface_name=None, network=None, mtu=None, vlanid=None, vlan_parent=None, bond_mode=None, bond_slaves=None, dhcp=None, options=None):
        """
        This method configures/set interface config for a group.
        """
        result_if = False
        my_interface = {}

        if mtu and ((not mtu.isnumeric()) or int(mtu) > 65535 or int(mtu) < 68):
            message = f"mtu size out of range"
            return False, message
        elif bond_mode and bond_mode not in ['balance-rr','active-backup','balance-xor',
                                           'broadcast','802.3ad','balance-tlb','balance-alb',
                                           '0','1','2','3','4','5','6']:
            message = f"bonding mode {bond_mode} not supported." 
            message += "choose from balance-rr, active-backup, balance-xor, broadcast, 802.3ad, balance-tlb or balance-alb"
            return False, message
        elif vlanid and ((not vlanid.isnumeric()) or int(vlanid) > 4096):
            message = "vlanid has to be a value between 0 and 4096"
            return False, message
        elif (bond_mode or bond_slaves) and vlan_parent:
            message = f"bonded interface can not have a vlan_parent"
            return False, message

        where_interface = f'groupid = "{groupid}" AND interface = "{interface_name}"'
        check_interface = Database().get_record(table='groupinterface', where=where_interface)

        if bond_slaves or bond_mode or vlan_parent or mtu:
            if check_interface:
                if (bond_mode or bond_slaves) and check_interface[0]['vlan_parent']:
                    message = "bonding interface using a vlan_parent not supported"
                    return False, message
                elif vlan_parent and (check_interface[0]['bond_mode'] or check_interface[0]['bond_slaves']):
                    message = "bonding interface using a vlan_parent not supported"
                    return False, message
                elif vlan_parent and (not vlanid) and not check_interface[0]['vlanid']:
                    message = "vlan_parent requires a vlanid"
                    return False, message
                elif bond_slaves and (not bond_mode) and not check_interface[0]['bond_mode']:
                    message = "bonding requires a bond_mode and bond_slaves"
                    return False, message
                elif bond_mode and (not bond_slaves) and not check_interface[0]['bond_slaves']:
                    message = "bonding requires a bond_mode and bond_slaves"
                    return False, message
                elif check_interface[0]['vlan_parent'] and mtu:
                    message = "MTU cannot be set on an interface with a vlan_parent"
                    return False, message
                elif vlan_parent and check_interface[0]['mtu']:
                    my_interface['mtu'] = None # we clear the MTU as it's the parent who sets it
            elif vlan_parent and mtu:
                message = "MTU cannot be set on an interface with a vlan_parent"
                return False, message
            elif vlan_parent and not vlanid:
                message = "vlan_parent requires a vlanid"
                return False, message
            elif bond_mode and not bond_slaves:
                message = "bonding requires a bond_mode and bond_slaves"
                return False, message
            elif bond_slaves and not bond_mode:
                message = "bonding requires a bond_mode and bond_slaves"
                return False, message
                   
        if mtu is not None:
            my_interface['mtu'] = mtu
        if options is not None:
            my_interface['options'] = options
        if vlanid is not None:
            my_interface['vlanid'] = vlanid
        if vlan_parent is not None:
            my_interface['vlan_parent'] = vlan_parent
        if bond_mode is not None:
            my_interface['bond_mode'] = bond_mode
        if bond_slaves is not None:
            bond_slaves = bond_slaves.replace(' ',',')
            bond_slaves = bond_slaves.replace(',,',',')
            my_interface['bond_slaves'] = bond_slaves
            if (bond_slaves.count(',') < 1):
                message = f"bond_slaves should contain at least two interfaces"
                return False, message
        if dhcp is not None:
            my_interface['dhcp'] = Helper().bool_to_string(dhcp)
            if my_interface['dhcp'] not in ['0','1']:
                message = f"dhcp should be y, yes, n or no"
                return False, message

        # we force a NULL in the database - clean
        for item in ['macaddress','mtu','options','vlanid','vlan_parent','bond_mode','bond_slaves','dhcp']:
            if item in my_interface and not my_interface[item]:
                my_interface[item] = None
                if item == 'vlanid':
                   my_interface['vlan_parent'] = None
                elif item == 'bond_mode':
                   my_interface['bond_slaves'] = None

        networkid = None
        if network:
            networkid = Database().id_by_name('network', network)
        else:
            nwk=Database().get_record_join(
                ['network.name as network', 'network.id as networkid'],
                [
                    'network.id=groupinterface.networkid',
                    'groupinterface.groupid=group.id'
                ],
                [
                    f"`group`.id='{groupid}'",
                    f"groupinterface.interface='{interface_name}'"
                ]
            )
            if nwk and 'networkid' in nwk[0]:
                networkid=nwk[0]['networkid']
        if networkid is None:
            message = "Network not provided or does not exist"
            return False, message 
        my_interface['networkid'] = networkid

        if not check_interface: # ----> easy. both the interface and ipaddress do not exist
            my_interface['interface'] = interface_name
            my_interface['groupid'] = groupid
            row = Helper().make_rows(my_interface)
            result_if = Database().insert('groupinterface', row)
        else:
            # we have to update the interface
            if my_interface:
                row = Helper().make_rows(my_interface)
                where = [{"column": "id", "value": check_interface[0]['id']}]
                result_if = Database().update('groupinterface', row, where)
            else:
                # no change here, we bail
                result_if=True

        if result_if:
            message = f"interface {interface_name} created or changed with result {result_if}"
            self.logger.info(message)
            return True, message
        message = f"interface {interface_name} config failed with result {result_if}"
        self.logger.info(message)
        return False, message


    def update_interface_on_group_nodes(self, name=None, request_id=None):
        """
        This method will update node/group interfaces.
        It's called from a group add/change (base/group + base/interface). it handles all nodes in that group.
        """
        self.logger.info(f'request_id: {request_id}')
        self.logger.info("update_interface_on_group_nodes called")
        try:
            while next_id := Queue().next_task_in_queue('group_interface'):
                message = f"update_interface_on_group_nodes sees job in queue as next: {next_id}"
                self.logger.info(message)
                details=Queue().get_task_details(next_id)
                # request_id = details['request_id']
                action = details['task']
                group, interface, *_ = details['param'].split(':') + [None]

                if group == name:
                    # RENAMING ---------------------------------------------------------------
                    if (action in ['rename_interface_for_group_nodes']) and interface:
                        old_interface, new_interface = interface.split('+')
                        self.logger.info(f"Renaming interface {old_interface} to {new_interface} for group {group} nodes")
                        nodes = Database().get_record_join(
                            ['node.id as nodeid','nodeinterface.id as nodeinterfaceid'],
                            ['node.groupid=group.id','nodeinterface.nodeid=node.id'],
                            [f"`group`.name='{group}'",f"nodeinterface.interface='{old_interface}'"]
                        )
                        if nodes:
                            for node in nodes:
                                self.logger.debug(f"renaming interface {old_interface} to {new_interface} for node.id {node['nodeid']}/group {group}")
                                my_interface = {}
                                my_interface['interface'] = new_interface
                                row = Helper().make_rows(my_interface)
                                where = [{"column": "id", "value": node['nodeinterfaceid']}]
                                result_if = Database().update('nodeinterface', row, where)
                                if not result_if:
                                    self.logger.error(f"rename failed for node.id {node['nodeid']}/group {group}: {result_if}")
                        else:
                            self.logger.warning(f"No nodes found for group {group}")
                    # ADDING/UPDATING --------------------------------------------------------
                    elif (action in ['add_interface_to_group_nodes', 'update_interface_for_group_nodes']) and interface:
                        network = Database().get_record_join(
                            [
                                'ipaddress.ipaddress',
                                'ipaddress.ipaddress_ipv6',
                                'ipaddress.networkid as networkid',
                                'network.network', 'network.network_ipv6',
                                'network.subnet', 'network.subnet_ipv6',
                                'network.name as networkname',
                                'groupinterface.mtu',
                                'groupinterface.vlanid',
                                'groupinterface.vlan_parent',
                                'groupinterface.bond_mode',
                                'groupinterface.bond_slaves',
                                'groupinterface.dhcp'
                            ],
                            [
                                'ipaddress.networkid=network.id',
                                'network.id=groupinterface.networkid',
                                'groupinterface.groupid=group.id'
                            ],
                            [f"`group`.name='{group}'", f"groupinterface.interface='{interface}'"]
                        )
                        if not network: # as in we did not have any ipaddress used...
                            network = Database().get_record_join(
                                [
                                    'network.id as networkid',
                                    'network.network', 'network.network_ipv6',
                                    'network.subnet', 'network.subnet_ipv6',
                                    'network.name as networkname',
                                    'groupinterface.vlanid',
                                    'groupinterface.vlan_parent',
                                    'groupinterface.bond_mode',
                                    'groupinterface.bond_slaves',
                                    'groupinterface.dhcp'
                                ],
                                [
                                    'network.id=groupinterface.networkid',
                                    'groupinterface.groupid=group.id'
                                ],
                                [
                                    f"`group`.name='{group}'",
                                    f"groupinterface.interface='{interface}'"
                                ]
                            )
                        dhcp_ips = []
                        dhcp6_ips = []
                        vlanid, vlan_parent, bond_mode, bond_slaves, dhcp, mtu = None, None, None, None, None, None
                        if network:
                            dhcp_ips = self.get_dhcp_range_ips_from_network(network[0]['networkname'])
                            dhcp6_ips = self.get_dhcp_range_ips_from_network(network[0]['networkname'],'ipv6')
                            vlanid = network[0]['vlanid']
                            vlan_parent = network[0]['vlan_parent']
                            bond_mode = network[0]['bond_mode']
                            bond_slaves = network[0]['bond_slaves']
                            dhcp = network[0]['dhcp']
                            mtu = network[0]['mtu']
                        ips = dhcp_ips.copy()
                        ips6 = dhcp6_ips.copy()
                        if network: 
                            if 'ipaddress' in network[0]:
                                for ip in network:
                                    if ip['ipaddress']:
                                        ips.append(ip['ipaddress'])
                            if 'ipaddress_ipv6' in network[0]:
                                for ip in network:
                                    if ip['ipaddress_ipv6']:
                                        ips6.append(ip['ipaddress_ipv6'])
                        nodes = Database().get_record_join(
                            ['node.id as nodeid'],
                            ['node.groupid=group.id'],
                            [f"`group`.name='{group}'"]
                        )
                        if nodes:
                            for node in nodes:
                                check, text = self.node_interface_config(nodeid=node['nodeid'], interface_name=interface, mtu=mtu, vlanid=vlanid,
                                                                         vlan_parent=vlan_parent, bond_mode=bond_mode, bond_slaves=bond_slaves)
                                message = f"Adding/Updating interface {interface} to node id "
                                message += f"{node['nodeid']} for group {group}. {text}"
                                self.logger.info(message)
                                if check and network:
                                    valid_ip, avail, valid_ip6, avail6, avail_dhcp = None, None, None, None, None
                                    if action == 'update_interface_for_group_nodes':
                                        ip_details = Database().get_record_join(
                                            ['ipaddress.ipaddress','ipaddress.ipaddress_ipv6','ipaddress.dhcp'],
                                            ['ipaddress.tablerefid=nodeinterface.id'],
                                            [
                                                "ipaddress.tableref='nodeinterface'",
                                                f"nodeinterface.nodeid=\"{node['nodeid']}\"",
                                                f"nodeinterface.interface='{interface}'"
                                            ]
                                        )
                                        if ip_details:
                                            avail_dhcp = ip_details[0]['dhcp'] or False
                                            if network[0]['network'] and ip_details[0]['ipaddress']:
                                                valid_ip = Helper().check_ip_range(
                                                    ip_details[0]['ipaddress'],
                                                    f"{network[0]['network']}/{network[0]['subnet']}"
                                                )
                                            if network[0]['network_ipv6'] and ip_details[0]['ipaddress_ipv6']:
                                                valid_ip6 = Helper().check_ip_range(
                                                    ip_details[0]['ipaddress_ipv6'],
                                                    f"{network[0]['network_ipv6']}/{network[0]['subnet_ipv6']}"
                                                )
                                            if valid_ip and ip_details[0]['ipaddress'] and ip_details[0]['ipaddress'] not in dhcp_ips:
                                                avail = ip_details[0]['ipaddress']
                                                self.logger.info(f"---> reusing ipaddress {avail}")
                                            if valid_ip6 and ip_details[0]['ipaddress_ipv6'] and ip_details[0]['ipaddress_ipv6'] not in dhcp6_ips:
                                                avail6 = ip_details[0]['ipaddress_ipv6']
                                                self.logger.info(f"---> reusing ipaddress {avail6}")

                                    # IPv4, ipv4 ------------------------------
                                    if network[0]['network'] and (not avail) and (not avail_dhcp):
                                        avail = Helper().get_available_ip(
                                            network[0]['network'],
                                            network[0]['subnet'],
                                            ips, ping=True
                                        )

                                    if avail:
                                        ipaddress = avail
                                        ips.append(ipaddress)
                                        _, response = self.node_interface_ipaddress_config(
                                            node['nodeid'],
                                            interface,
                                            ipaddress,
                                            network[0]['networkname']
                                        )
                                        message = f"Adding IP {ipaddress} to node id "
                                        message += f"{node['nodeid']} for group {group} interface "
                                        message += f"{interface}. {response}"
                                        self.logger.info(message)

                                    if not network[0]['network']:
                                        _, response = self.node_interface_clear_ipaddress(
                                            node['nodeid'],
                                            interface,
                                            'ipv4'
                                        )

                                    # IPv6, ipv6 ------------------------------
                                    if network[0]['network_ipv6'] and (not avail6) and (not avail_dhcp):
                                        avail6 = Helper().get_available_ip(
                                            network[0]['network_ipv6'],
                                            network[0]['subnet_ipv6'],
                                            ips6, ping=True
                                        )

                                    if avail6:
                                        ipaddress = avail6
                                        ips6.append(ipaddress)
                                        _, response = self.node_interface_ipaddress_config(
                                            node['nodeid'],
                                            interface,
                                            ipaddress,
                                            network[0]['networkname']
                                        )
                                        message = f"Adding IP {ipaddress} to node id "
                                        message += f"{node['nodeid']} for group {group} interface "
                                        message += f"{interface}. {response}"
                                        self.logger.info(message)

                                    if not network[0]['network_ipv6']:
                                        _, response = self.node_interface_clear_ipaddress(
                                            node['nodeid'],
                                            interface,
                                            'ipv6'
                                        )

                                    # DHCP ------------------------------------
                                    if dhcp is not None:
                                        _, response = self.node_interface_dhcp_config(
                                            node['nodeid'],
                                            interface,
                                            dhcp
                                        )

                    # DELETING --------------------------------------------------------------
                    elif action == 'delete_interface_from_group_nodes' and interface:
                        nodes = Database().get_record_join(
                            [
                                'node.id as nodeid',
                                'nodeinterface.id as ifid',
                                'ipaddress.id as ipid'
                            ],
                            [
                                'ipaddress.tablerefid=nodeinterface.id',
                                'nodeinterface.nodeid=node.id',
                                'node.groupid=group.id'
                            ],
                            [
                                f"`group`.name='{name}'",
                                f"nodeinterface.interface='{interface}'",
                                'ipaddress.tableref="nodeinterface"'
                            ]
                        )
                        if nodes:
                            for node in nodes:
                                Database().delete_row(
                                    'ipaddress',
                                    [{"column": "id", "value": node['ipid']}]
                                )
                                Database().delete_row(
                                    'nodeinterface',
                                    [{"column": "id", "value": node['ifid']}]
                                )

                        nodes = Database().get_record_join(
                            ['node.id as nodeid', 'nodeinterface.id as ifid'],
                            ['nodeinterface.nodeid=node.id','node.groupid=group.id'],
                            [f"`group`.name='{name}'",f"nodeinterface.interface='{interface}'"]
                        )
                        if nodes:
                            for node in nodes:
                                Database().delete_row(
                                    'nodeinterface',
                                    [{"column": "id", "value": node['ifid']}]
                                )
                    Queue().remove_task_from_queue(next_id)
                    Queue().add_task_to_queue(task='reload', param='dns',
                                              subsystem='housekeeper',
                                              request_id='__update_interface_on_group_nodes__')
                else:
                    self.logger.info(f"{details['task']} is not for us.")
                    sleep(10)
        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"update_interface_on_group_nodes has problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")


    def update_interface_ipaddress_on_network_change(self, name=None, request_id=None):  #name=network
        """
        This method will update ipaddress of node/group interface.
        """
        self.logger.info(f'request_id: {request_id}')
        self.logger.info("update_interface_ipaddress_on_network_change called")
        try:
            while next_id := Queue().next_task_in_queue('network_change'):
                message = "update_interface_ipaddress_on_network_change "
                message += f"sees job in queue as next: {next_id}"
                self.logger.info(message)
                details = Queue().get_task_details(next_id)
                action = details['task']
                network, *_ = details['param'].split(':') + [None]

                if (name and network==name) or network:
                    Queue().update_task_status_in_queue(next_id,'in progress')
                    if action == 'update_all_interface_ipaddress':
                        ips = self.get_dhcp_range_ips_from_network(network)
                        ips6 = self.get_dhcp_range_ips_from_network(network,'ipv6')
                        ipaddress_list = Database().get_record_join(
                            [
                                'ipaddress.ipaddress',
                                'ipaddress.ipaddress_ipv6',
                                'ipaddress.dhcp',
                                'ipaddress.networkid as networkid',
                                'network.network',
                                'network.subnet',
                                'network.dhcp as networkdhcp',
                                'network.network_ipv6',
                                'network.subnet_ipv6',
                                'network.name as networkname',
                                'ipaddress.id as ipaddressid',
                                'ipaddress.tableref',
                                'ipaddress.tablerefid'
                            ],
                            ['ipaddress.networkid=network.id'],
                            [f"network.name='{network}'"]
                        )
                        if ipaddress_list:
                            for ipaddress in ipaddress_list:
                                # we assume that there's always either configured. ipv4 or ipv6
                                ret, avail, avail6, maximum = 0, ipaddress['ipaddress'], ipaddress['ipaddress_ipv6'], 5
                                we_continue = False
                                we_continue6 = False
                                we_dhcp = ipaddress['networkdhcp'] and (ipaddress['dhcp'] or False)
                                if ipaddress['network']:
                                    if not ipaddress['network_ipv6']:
                                        avail6 = None
                                        we_continue6 = True
                                    if ipaddress['ipaddress']:
                                        valid_ip = Helper().check_ip_range(ipaddress['ipaddress'],
                                            f"{ipaddress['network']}/{ipaddress['subnet']}"
                                        )
                                        if valid_ip and ipaddress['ipaddress'] not in ips:
                                            ips.append(ipaddress['ipaddress'])
                                            self.logger.info(f"For network {network} no change for IP {ipaddress['ipaddress']}")
                                            we_continue = True
                                if ipaddress['network_ipv6']:
                                    if not ipaddress['network']:
                                        avail = None
                                        we_continue = True
                                    if ipaddress['ipaddress_ipv6']:
                                        valid_ip6 = Helper().check_ip_range(ipaddress['ipaddress_ipv6'],
                                            f"{ipaddress['network_ipv6']}/{ipaddress['subnet_ipv6']}"
                                        )
                                        if valid_ip6 and ipaddress['ipaddress_ipv6'] not in ips6:
                                            ips6.append(ipaddress['ipaddress_ipv6'])
                                            self.logger.info(f"For network {network} no change for IP {ipaddress['ipaddress_ipv6']}")
                                            we_continue6 = True
                                if we_continue and we_continue6:
                                    continue
                                if not we_dhcp:
                                    if not we_continue:
                                        avail = Helper().get_available_ip(
                                            ipaddress['network'],
                                            ipaddress['subnet'],
                                            ips, ping=True
                                        )
                                    if not we_continue6:
                                        avail6 = Helper().get_available_ip(
                                            ipaddress['network_ipv6'],
                                            ipaddress['subnet_ipv6'],
                                            ips6, ping=True
                                        )
                                message = f"For network {network} changing IP "
                                if avail:
                                    Database().delete_row(
                                        'ipaddress',
                                        [{"column": "ipaddress", "value": avail}]
                                    )
                                    ips.append(avail)
                                if avail6:
                                    Database().delete_row(
                                        'ipaddress',
                                        [{"column": "ipaddress_ipv6", "value": avail6}]
                                    )
                                    ips6.append(avail6)
                                if avail or avail6:
                                    Database().delete_row(
                                        'ipaddress',
                                        [
                                            {"column": "tableref", "value": ipaddress['tableref']},
                                            {"column": "tablerefid", "value": ipaddress['tablerefid']}
                                        ]
                                    )
                                    row = [
                                        {"column": "ipaddress", "value": avail},
                                        {"column": "ipaddress_ipv6", "value": avail6},
                                        {"column": "dhcp", "value": ipaddress['dhcp']},
                                        {"column": "networkid", "value": ipaddress['networkid']},
                                        {"column": "tableref", "value": ipaddress['tableref']},
                                        {"column": "tablerefid", "value": ipaddress['tablerefid']}
                                    ]
                                    result = Database().insert('ipaddress', row)

                                    message += f"{ipaddress['ipaddress']} to {avail} and {ipaddress['ipaddress_ipv6']} to {avail6}. {result}"
                                    self.logger.info(message)
                                elif not we_dhcp:
                                    message += f"{ipaddress['ipaddress']} or {ipaddress['ipaddress_ipv6']} not possible. "
                                    message += "no free IP addresses available."
                                    self.logger.error(message)
                    Queue().remove_task_from_queue(next_id)
                    Queue().add_task_to_queue(task='reload', param='dns', subsystem='housekeeper',
                                              request_id='__update_interface_ipaddress_on_network_change__')
                    Queue().add_task_to_queue(task='restart', param='dhcp', subsystem='housekeeper',
                                              request_id='__update_interface_ipaddress_on_network_change__')
                    Queue().add_task_to_queue(task='restart', param='dhcp6', subsystem='housekeeper',
                                              request_id='__update_interface_ipaddress_on_network_change__')
                else:
                    self.logger.info(f"{details['task']} is not for us.")
                    sleep(10)
        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"update_interface_ipaddress_on_network_change has problems: {exp}, {exc_type}, in {exc_tb.tb_lineno}")


    def update_dhcp_range_on_network_change(self, name=None, request_id=None): # name=network
        """
        This method will update dhcp range, when network will changes.
        """
        self.logger.info(f'request_id: {request_id}')
        network = Database().get_record(table='network', where=f'name = "{name}"')
        if network:
            for ipv in ['', '_ipv6']:
                if network[0]['dhcp_range_begin'+ipv] and network[0]['dhcp_range_end'+ipv]:
                    subnet = network[0]['network'+ipv]+'/'+network[0]['subnet'+ipv]
                    dhcp_begin_ok = Helper().check_ip_range(network[0]['dhcp_range_begin'+ipv], subnet)
                    dhcp_end_ok = Helper().check_ip_range(network[0]['dhcp_range_end'+ipv], subnet)
                    if dhcp_begin_ok and dhcp_end_ok:
                        message = f"{network[0]['network'+ipv]}/{network[0]['subnet'+ipv]} :: dhcp "
                        message += f"{network[0]['dhcp_range_begin'+ipv]}-{network[0]['dhcp_range_end'+ipv]} "
                        message += "fits with in network range. no change"
                        self.logger.info(message)
                        return True
                    dhcp_size = Helper().get_ip_range_size(
                        network[0]['dhcp_range_begin'+ipv],
                        network[0]['dhcp_range_end'+ipv]
                    )
                    nwk_size = Helper().get_network_size(network[0]['network'+ipv], network[0]['subnet'+ipv])
                    if ((100 * dhcp_size) / nwk_size) > 50 and not network[0]['dhcp_nodes_in_pool']: # 50 == 50%
                        dhcp_size = int(nwk_size / 10)
                        # we reduce this to 10%
                        # how many,  offset start
                    dhcp_begin, dhcp_end = Helper().get_ip_range_first_last_ip(
                        network[0]['network'+ipv],
                        network[0]['subnet'+ipv],
                        dhcp_size, (int(nwk_size / 2) - 4)
                    )
                    message = f"{network[0]['network'+ipv]}/{network[0]['subnet'+ipv]}"
                    message += f" :: new dhcp range {dhcp_begin}-{dhcp_end}"
                    self.logger.info(message)
                    if dhcp_begin and dhcp_end:
                        row = [
                            {"column": f"dhcp_range_begin{ipv}", "value": dhcp_begin},
                            {"column": f"dhcp_range_end{ipv}", "value": dhcp_end}
                        ]
                        where = [{"column": "name", "value": name}]
                        Database().update('network', row, where)
                        Queue().add_task_to_queue(task='restart', param='dhcp', subsystem='housekeeper',
                                                  request_id='__update_dhcp_range_on_network_change__')


    def get_dhcp_range_ips_from_network(self, network=None, ipversion='ipv4'):
        """
        This method will return dhcp range for network.
        """
        ips = []
        network_details = Database().get_record(table='network', where=f'name = "{network}"')
        if network_details:
            if ipversion == 'ipv6' and network_details[0]['dhcp_range_begin_ipv6'] and network_details[0]['dhcp_range_end_ipv6']:
                ips = Helper().get_ip_range_ips(
                    network_details[0]['dhcp_range_begin_ipv6'],
                    network_details[0]['dhcp_range_end_ipv6']
                )
            elif network_details[0]['dhcp_range_begin'] and network_details[0]['dhcp_range_end']:
                ips = Helper().get_ip_range_ips(
                    network_details[0]['dhcp_range_begin'],
                    network_details[0]['dhcp_range_end']
                )
        return ips


    def get_all_occupied_ips_from_network(self, network=None, ipversion='ipv4'):
        """
        This method will return all occupied IP from a network.
        """
        ips = []
        network_details = Database().get_record(table='network', where=f'name = "{network}"')
        if network_details:
            if ipversion == 'ipv6' and network_details[0]['dhcp_range_begin_ipv6'] and network_details[0]['dhcp_range_end_ipv6']:
                ips = Helper().get_ip_range_ips(
                    network_details[0]['dhcp_range_begin_ipv6'],
                    network_details[0]['dhcp_range_end_ipv6']
                )
            elif network_details[0]['dhcp_range_begin'] and network_details[0]['dhcp_range_end']:
                ips = Helper().get_ip_range_ips(
                    network_details[0]['dhcp_range_begin'],
                    network_details[0]['dhcp_range_end']
                )
        network_details = Database().get_record_join(
            ['ipaddress.ipaddress','ipaddress.ipaddress_ipv6'],
            ['network.id=ipaddress.networkid'],
            [f"network.name='{network}'"]
        )
        if network_details:
            if ipversion == 'ipv6':
                for each in network_details:
                    ips.append(each['ipaddress_ipv6'])
            else:
                for each in network_details:
                    ips.append(each['ipaddress'])
        reserved_details = Database().get_record(table="reservedipaddress", where=f"version='{ipversion}'")
        if reserved_details:
            for each in reserved_details:
                ips.append(each['ipaddress'])
        return ips

