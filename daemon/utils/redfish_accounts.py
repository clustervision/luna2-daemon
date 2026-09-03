#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
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
Redfish Accounts :: make a BMC's AccountService match the node's redfishsetup

A redfishsetup describes the accounts Luna wants on a BMC, with their roles.
Nothing on the hardware has heard of them until this runs: the in-band step of
an install creates only the bmcsetup user, over ipmitool, and cannot set a
Redfish role at all.

This reconciles out of band, once the BMC has an address. It authenticates with
the bmcsetup credential - the one account that exists on a fresh BMC, and a
Redfish administrator on every BMC that keeps one user store behind both front
ends - and that is the single, bounded exception to TRIX-2027: it is used to
create the accounts the administrator asked for, and never for an operation.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from concurrent.futures import ThreadPoolExecutor
from os import getpid
from random import randint
from time import time
from common.constant import CONSTANT
from utils.log import Log
from utils.database import Database
from utils.helper import Helper
from utils.status import Status
from utils.redfish import Redfish, RedfishAccess

# unmanaged_bmc_users values that the in-band step acts on; anything else is skip
DISABLING = ('disable', 'delete')


class RedfishAccounts():
    """
    Creates and corrects the Redfish accounts a node's redfishsetup describes.
    """

    def __init__(self):
        self.logger = Log.get_logger()
        plugins_path = CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
        self.redfish_plugins = Helper().plugin_finder(f'{plugins_path}/redfish')

    # --- what the node wants ------------------------------------------------

    def wanted(self, nodename=None):
        """
        This method answers whether Luna may manage this node's Redfish accounts:
        setupredfish on the node, else on its group, and a redfishsetup assigned.
        """
        node = Database().get_record(table='node', where=f'name = "{nodename}"')
        if not node:
            return False
        flag = node[0].get('setupredfish')
        if flag is None:
            group = Database().get_record(table='group', where=f"id = \"{node[0]['groupid']}\"")
            flag = group[0].get('setupredfish') if group else None
        if not Helper().make_bool(flag):
            return False
        return bool(RedfishAccess().setup_id(nodename=nodename))

    def desired(self, nodename=None):
        """
        This method gathers everything a reconciliation needs: the BMC address,
        the bmcsetup credential to bootstrap with, the redfishsetup and its
        accounts, and the node's unmanaged-users policy.
        """
        node = Database().get_record_join(
            ['node.id as nodeid', 'node.name as nodename', 'node.groupid as groupid',
             'node.bmcsetupid', 'node.unmanaged_bmc_users', 'node.setupredfish',
             'ipaddress.ipaddress as device'],
            ['nodeinterface.nodeid=node.id', 'ipaddress.tablerefid=nodeinterface.id'],
            ['tableref="nodeinterface"', "nodeinterface.interface='BMC'",
             f"node.name='{nodename}'"])
        if not node:
            return False, f'{nodename} does not exist or has no BMC interface configured'
        node = node[0]
        if not node['device']:
            return False, f'{nodename} has no BMC address configured'
        group = Database().get_record(table='group', where=f"id = \"{node['groupid']}\"")
        group = group[0] if group else {}
        flag = node.get('setupredfish')
        if flag is None:
            flag = group.get('setupredfish')
        if not Helper().make_bool(flag):
            return False, f'{nodename} has setupredfish off, so its Redfish accounts are not managed'
        bmcsetupid = node.get('bmcsetupid') or group.get('bmcsetupid')
        bmcsetup = Database().get_record(table='bmcsetup', where=f'id = "{bmcsetupid}"')
        if not bmcsetup:
            return False, f'{nodename} has no bmcsetup, so there is no credential to bootstrap with'
        setupid = RedfishAccess().setup_id(nodename=nodename)
        if not setupid:
            return False, f'{nodename} has no redfishsetup assigned'
        setup = Database().get_record(table='redfishsetup', where=f'id = "{setupid}"')
        accounts = Database().get_record(table='redfishaccount',
                                         where=f'redfishsetupid = "{setupid}"')
        if not setup or not accounts:
            return False, f'{nodename}: redfishsetup {setupid} has no accounts to provision'
        policy = node.get('unmanaged_bmc_users') or group.get('unmanaged_bmc_users') or 'skip'
        return True, {
            'device': node['device'],
            'groupname': group.get('name'),
            'bootstrap': {'username': bmcsetup[0]['username'],
                          'password': bmcsetup[0]['password']},
            'scheme': setup[0]['scheme'] or 'https',
            'port': setup[0]['port'],
            'verify': bool(Helper().make_bool(setup[0]['verify'])),
            'accounts': [{'username': row['username'], 'password': row['password'],
                          'role': str(row['role'] or '').strip()} for row in accounts],
            'policy': str(policy).strip().lower(),
        }

    # --- the reconciliation ---------------------------------------------------

    def client(self, wanted=None, username=None, password=None):
        return Redfish(device=wanted['device'], username=username, password=password,
                       scheme=wanted['scheme'], port=wanted['port'], verify=wanted['verify'])

    def existing(self, redfish=None):
        """
        This method reads the AccountService and every account on it, keyed by
        user name. Slots with no user name are the empty ones a board that
        refuses POST wants a PATCH on.
        """
        status, root = redfish.service_root()
        if not status:
            return False, root, None
        service_path = (root.get('AccountService') or {}).get('@odata.id')
        if not service_path:
            return False, 'AccountService missing from the Redfish root', None
        status, service = redfish.get(path=service_path)
        if not status:
            return False, service, None
        collection_path = (service.get('Accounts') or {}).get('@odata.id')
        if not collection_path:
            return False, 'Accounts collection missing from the AccountService', None
        status, collection = redfish.get(path=collection_path)
        if not status:
            return False, collection, None
        accounts = {}
        for member in collection.get('Members', []):
            path = member.get('@odata.id')
            if not path:
                continue
            status, data = redfish.get(path=path)
            if status and isinstance(data, dict):
                accounts[path] = data
        return True, collection_path, accounts

    def by_username(self, accounts=None):
        return {str(data.get('UserName') or ''): (path, data)
                for path, data in (accounts or {}).items() if data.get('UserName')}

    def password_works(self, wanted=None, username=None, password=None):
        """
        A BMC never hands a password back, so the only way to know whether the
        one Luna holds is the one the board holds is to log in with it.
        """
        status, _ = self.client(wanted, username, password).service_root()
        return status

    def reconcile(self, nodename=None):
        """
        This method makes the BMC's accounts match the node's redfishsetup.

        Luna's record is the desired state, and it converges loudly: an account
        that is missing is created, a wrong role or a disabled state is corrected,
        and a password the board no longer accepts is set again and said so. It
        never removes an account the redfishsetup names, and it touches accounts
        it does not name only under the node's unmanaged-users policy - the same
        policy the in-band step applies to IPMI users, so one setting governs
        both protocols.

        The collection is read back at the end. What the board holds is the
        answer, not what the writes returned.
        """
        status, wanted = self.desired(nodename=nodename)
        if not status:
            return False, wanted
        redfish = self.client(wanted, wanted['bootstrap']['username'],
                              wanted['bootstrap']['password'])
        status, collection_path, accounts = self.existing(redfish=redfish)
        if not status:
            return False, f'{nodename}: {collection_path}'
        plugin = Helper().plugin_load(self.redfish_plugins, 'redfish',
                                      [nodename, wanted['groupname']])()
        present = self.by_username(accounts)
        done, failed = [], []
        for account in wanted['accounts']:
            username = account['username']
            if username not in present:
                status, message = plugin.create_account(
                    redfish=redfish, collection=collection_path, username=username,
                    password=account['password'], role=account['role'])
                (done if status else failed).append(
                    f"{username}: {'created as ' + account['role'] if status else message}")
                continue
            path, data = present[username]
            changes = {}
            if account['role'] and str(data.get('RoleId') or '') != account['role']:
                changes['RoleId'] = account['role']
            if data.get('Enabled') is False:
                changes['Enabled'] = True
            if not self.password_works(wanted, username, account['password']):
                # converging, and saying so: the password Luna holds is the one an
                # operator set, and a board that stopped accepting it would refuse
                # every later operation with a 401 nothing explains
                changes['Password'] = account['password']
                self.logger.warning(f'{nodename}: the board no longer accepts the password '
                                    f'Luna holds for {username}; setting it again')
            if not changes:
                done.append(f'{username}: as configured')
                continue
            status, message = redfish.patch(path=path, payload=changes,
                                            etag=data.get('@odata.etag'))
            what = ', '.join('password' if key == 'Password' else f'{key}={value}'
                             for key, value in changes.items())
            (done if status else failed).append(
                f"{username}: {what if status else message}")
        failed += self.apply_policy(nodename, wanted, redfish, present)
        # what the board holds now, not what the writes said
        status, _, accounts = self.existing(redfish=redfish)
        if not status:
            return False, f'{nodename}: written but unreadable afterwards: {accounts}'
        present = self.by_username(accounts)
        for account in wanted['accounts']:
            entry = present.get(account['username'])
            if not entry:
                failed.append(f"{account['username']}: not on the board after writing it")
            elif account['role'] and str(entry[1].get('RoleId') or '') != account['role']:
                failed.append(f"{account['username']}: board reports role "
                              f"{entry[1].get('RoleId')}, wanted {account['role']}")
            elif entry[1].get('Enabled') is False:
                failed.append(f"{account['username']}: still disabled on the board")
        summary = '; '.join(done + failed)
        return (not failed), summary

    def apply_policy(self, nodename=None, wanted=None, redfish=None, present=None):
        """
        This method applies unmanaged_bmc_users to the Redfish accounts: every
        enabled account that is neither the bmcsetup user nor one the redfishsetup
        names is disabled. 'delete' disables too, for now - removing a vendor's
        built-in account is refused by some boards and not undone by any, so
        that step waits for a board it has been tried on.
        """
        if wanted['policy'] not in DISABLING:
            return []
        if wanted['policy'] == 'delete':
            self.logger.info(f'{nodename}: unmanaged_bmc_users=delete disables Redfish '
                             'accounts rather than deleting them')
        managed = {wanted['bootstrap']['username']} | {a['username'] for a in wanted['accounts']}
        failed = []
        for username, (path, data) in present.items():
            if username in managed or data.get('Enabled') is not True:
                continue
            status, message = redfish.patch(path=path, payload={'Enabled': False},
                                            etag=data.get('@odata.etag'))
            if status:
                self.logger.info(f'{nodename}: disabled unmanaged Redfish account {username}')
            else:
                failed.append(f'{username}: could not disable: {message}')
        return failed

    # --- fan-out --------------------------------------------------------------

    def provision_child(self, name=None, request_id=None):
        """
        This method reconciles one node and records the outcome against the
        request, in the shape the status channel already carries for inventory.
        """
        try:
            status, message = self.reconcile(nodename=name)
        except Exception as exp:
            status, message = False, f'{exp}'
            self.logger.error(f'redfish accounts for {name} raised: {exp}')
        # named as the redfish subsystem so the status reader hands the text on:
        # what was created or corrected is the answer, not a bare OK
        Status().add_message(request_id=request_id, username_initiator='redfish_accounts',
                             message=f"{name}:redfish accounts:{status}:{message}",
                             status=200 if status else 500)
        return status

    def settle(self, provision=None, collect=None, request_id=None):
        """
        This method runs the provisioning and the inventory collections a boot
        storm queued, in one bounded sweep. A node in both lists is provisioned
        first and collected after, because the collection authenticates as the
        account the provisioning has just created.
        """
        # function-local for the same reason bios_push does it: base imports
        # utils, so a top-level import here would be a cycle
        from base.nodeinventory import NodeInventory
        provision = sorted(set(provision or []))
        collect = set(collect or [])
        hosts = sorted(set(provision) | collect)
        batch = int(CONSTANT['BMCCONTROL']['BMC_BATCH_SIZE'])
        request_id = request_id or str(time()) + str(randint(1001, 9999)) + str(getpid())
        Status().add_message(request_id, 'redfish_accounts', 'Settling Redfish accounts...')
        Status().mark_messages_read(request_id)

        def one(host):
            if host in provision:
                self.provision_child(host, request_id)
            if host in collect:
                NodeInventory().collect_child(host, request_id)

        def sweep():
            with ThreadPoolExecutor(max_workers=batch) as executor:
                for host in hosts:
                    executor.submit(one, host)
            Status().add_message(request_id, 'redfish_accounts', 'EOF')

        starter = ThreadPoolExecutor(max_workers=1)
        starter.submit(sweep)
        starter.shutdown(wait=False)
        return request_id

    def bulk_provision(self, request_data=None):
        """
        This method reconciles the accounts of a hostlist or a group, on demand.
        The same work the install event queues, without the five-minute wait: the
        BMC an operator asks about is one that already answers.
        """
        if not request_data:
            return False, 'Invalid request: Did not receive data'
        try:
            asked = request_data['config']['node']
        except (KeyError, TypeError):
            return False, 'Invalid request: no hostlist supplied'
        if asked.get('group'):
            group = asked['group']
            members = Database().get_record_join(
                ['node.name as name'], ['group.id=node.groupid'],
                [f'`group`.name="{group}"'])
            if not members:
                exists = Database().get_record(table='group', where=f'name = "{group}"')
                return False, (f'Group {group} has no nodes' if exists
                               else f'Group {group} is not available')
            hostlist = [member['name'] for member in members]
        else:
            raw_hosts = asked.get('hostlist')
            if not raw_hosts:
                return False, 'Invalid request: no hostlist supplied'
            hostlist = Helper().get_hostlist(raw_hosts)
            if not hostlist:
                return False, 'Invalid request: invalid hostlist'
        request_id = self.settle(provision=hostlist)
        return True, {'request_id': request_id,
                      'config': {'node': {'accounts': {'queued': len(hostlist)}}}}
