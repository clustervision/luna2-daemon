
# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This Is the Redfish Class, a client for one BMC.

Core builds it and hands it to whatever needs to talk Redfish - a control
plugin, an inventory collector - so that no plugin has to know how we reach a
BMC, and no plugin ever sees the credentials on an argument list.

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


from time import sleep, time
from json import dumps
import requests
import urllib3
from utils.log import Log
from utils.database import Database
from utils.helper import Helper

# BMCs ship self-signed certificates and we do not verify them by default, which
# is what the curl based predecessor did with -k. Without this the daemon's error
# log carries one warning per request, which at cluster scale is thousands a sweep.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Redfish():
    """
    A Redfish client bound to a single BMC.
    """

    def __init__(self, device=None, username=None, password=None, scheme='https',
                 port=None, verify=False, timeout=15, connect_timeout=5):
        """
        Constructor - binds this client to one BMC and its credentials.
        """
        self.logger = Log.get_logger()
        self.device = device
        self.timeout = (connect_timeout, timeout)
        self.base = f'{scheme}://{self.netloc(device, port)}'
        self.session = requests.Session()
        self.session.verify = verify
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'OData-Version': '4.0'
        })
        if username is not None and password is not None:
            self.session.auth = (str(username), str(password))
        self.cache = {}


    def netloc(self, device=None, port=None):
        """
        This method will build the host part of the URL. A BMC can hold an IPv6
        address, and a bare one makes the URL unparsable - it needs brackets.
        """
        host = str(device)
        if ':' in host and not host.startswith('['):
            host = f'[{host}]'
        if port:
            return f'{host}:{port}'
        return host


    def reason(self, data=None, http_code=None):
        """
        This method will dig the human readable reason out of a Redfish error.
        The status line rarely carries it - the service puts it in the extended
        info, and without this an operator only ever sees the HTTP code.
        """
        messages = []
        if isinstance(data, dict):
            extended = data.get('error', {}).get('@Message.ExtendedInfo', [])
            if not extended:
                extended = data.get('@Message.ExtendedInfo', [])
            for entry in extended:
                if isinstance(entry, dict):
                    text = entry.get('Message') or entry.get('MessageId')
                    if text and text not in messages:
                        messages.append(str(text))
            if not messages:
                text = data.get('error', {}).get('message')
                if text:
                    messages.append(str(text))
        elif isinstance(data, str) and data.strip():
            messages.append(data.strip())
        if messages:
            return '; '.join(messages)
        return f'Redfish HTTP {http_code}'


    def transport_reason(self, exp=None):
        """
        This method will say why a BMC could not be reached, in a few words.

        The exception itself carries a paragraph of urllib3 internals - the pool
        object, the retry count, the nested cause - and a hostlist run prints one
        of these per node into a fixed-width column. What an operator needs is
        which of the handful of things went wrong.
        """
        if isinstance(exp, requests.exceptions.ConnectTimeout):
            return f'connect timed out after {self.timeout[0]}s'
        if isinstance(exp, requests.exceptions.ReadTimeout):
            return f'no answer within {self.timeout[1]}s'
        if isinstance(exp, requests.exceptions.SSLError):
            return 'TLS handshake failed (check the scheme and the verify setting)'
        if isinstance(exp, requests.exceptions.ConnectionError):
            return 'connection refused or host unreachable'
        if isinstance(exp, requests.exceptions.TooManyRedirects):
            return 'too many redirects'
        text = str(exp).split('\n')[0]
        return text[:120] if text else exp.__class__.__name__


    def call(self, method='GET', path='/redfish/v1/', payload=None, headers=None):
        """
        This method will perform one Redfish request and return
        (status, http_code, data). Data is the parsed body where the service
        answered JSON, the raw text where it did not, and the failure reason
        where the call did not succeed.
        """
        if not self.device:
            return False, 0, 'No BMC address configured for this node'
        if not path:
            return False, 0, 'No Redfish resource requested'
        if not str(path).startswith('/'):
            path = f'/{path}'
        url = f'{self.base}{path}'
        body = None
        if payload is not None:
            body = payload if isinstance(payload, str) else dumps(payload)
        try:
            response = self.session.request(
                method,
                url,
                data=body,
                headers=headers,
                timeout=self.timeout
            )
        except requests.exceptions.RequestException as exp:
            self.logger.debug(f'redfish {method} {url} failed: {exp}')
            return False, 0, f'{self.device}: {self.transport_reason(exp)}'

        data = response.text
        if response.content:
            try:
                data = response.json()
            except ValueError:
                data = response.text
        if not response.ok:
            self.logger.debug(f'redfish {method} {url} answered {response.status_code}')
            return False, response.status_code, self.reason(data, response.status_code)
        return True, response.status_code, data


    def get(self, path='/redfish/v1/', cache=False):
        """
        This method will read one Redfish resource. Discovery reads the same few
        resources repeatedly, so a caller walking the tree can ask for the cached
        copy rather than paying a round trip per step.
        """
        if cache and path in self.cache:
            return True, self.cache[path]
        status, _, data = self.call(method='GET', path=path)
        if status and cache:
            self.cache[path] = data
        return status, data


    def post(self, path=None, payload=None):
        """
        This method will submit a resource or invoke a Redfish action.
        """
        status, _, data = self.call(method='POST', path=path, payload=payload)
        return status, data


    def delete(self, path=None):
        """
        This method will remove a Redfish resource.
        """
        status, _, data = self.call(method='DELETE', path=path)
        return status, data


    def patch(self, path=None, payload=None):
        """
        This method will modify properties of an existing Redfish resource.

        A service that publishes an ETag for the resource expects it back as
        If-Match, and refuses the write without it. Where there is no ETag the
        header is left off rather than invented - a service refusing the write is
        an answer, and papering over it would hide a concurrent change.
        """
        headers = None
        status, current = self.get(path=path)
        if status and isinstance(current, dict):
            etag = current.get('@odata.etag')
            if etag:
                headers = {'If-Match': etag}
        status, _, data = self.call(method='PATCH', path=path, payload=payload, headers=headers)
        return status, data


    def first_member(self, path=None):
        """
        This method will return the first member of a Redfish collection. Nearly
        every walk into the tree starts with one, and single-system machines are
        the case Luna manages.
        """
        status, data = self.get(path=path, cache=True)
        if not status:
            return False, data
        for member in data.get('Members', []):
            member_path = member.get('@odata.id')
            if member_path:
                return True, member_path
        return False, f'No members found in {path}'


    def service_root(self):
        """
        This method will read the Redfish service root.
        """
        return self.get(path='/redfish/v1/', cache=True)


    def resource(self, collection=None):
        """
        This method will resolve a named service-root collection down to its
        first member, and return (status, path, data) for it.
        """
        status, root = self.service_root()
        if not status:
            return False, root, None
        collection_path = root.get(collection, {}).get('@odata.id')
        if not collection_path:
            return False, f'{collection} collection missing from the Redfish root', None
        status, member_path = self.first_member(path=collection_path)
        if not status:
            return False, member_path, None
        status, member_data = self.get(path=member_path, cache=True)
        if not status:
            return False, member_data, None
        return True, member_path, member_data


    def system(self):
        """
        This method will resolve the first ComputerSystem.
        """
        return self.resource(collection='Systems')


    def manager(self):
        """
        This method will resolve the first Manager - the BMC itself.
        """
        return self.resource(collection='Managers')


    def chassis(self):
        """
        This method will resolve the first Chassis.
        """
        return self.resource(collection='Chassis')


    def poll_task(self, location=None, deadline=60, interval=5):
        """
        This method will follow a Redfish task to completion within a bounded
        deadline, and say plainly that it is still running when the deadline is
        reached. It is deliberately bounded: the control pipeline holds a worker
        for the whole call, so anything that genuinely takes minutes belongs in
        the queue rather than here.
        """
        if not location:
            return False, 'No task location returned by the Redfish service'
        expires = time() + deadline
        state = 'Unknown'
        while time() < expires:
            status, data = self.get(path=location)
            if not status:
                return False, data
            if not isinstance(data, dict):
                return True, 'task completed'
            state = str(data.get('TaskState', 'Unknown'))
            if state in ['Completed', 'OK']:
                return True, 'task completed'
            if state in ['Exception', 'Killed', 'Cancelled', 'Interrupted']:
                return False, self.reason(data, 0)
            sleep(interval)
        return False, f'task still {state} after {deadline} seconds: {location}'


# The privileges a Redfish role carries, from the DMTF's predefined roles. Named
# rather than ranked, because an operation needs a privilege and not a seniority:
# resetting a system needs ConfigureComponents, which an Operator has, while
# creating an account needs ConfigureUsers, which only an Administrator has.
#
# A vendor may define roles of its own with any privilege set it likes, so a name
# absent from here is unknown rather than known-unable - see pick_account.
LOGIN = 'Login'
CONFIGURE_COMPONENTS = 'ConfigureComponents'
CONFIGURE_USERS = 'ConfigureUsers'
CONFIGURE_MANAGER = 'ConfigureManager'

ROLE_PRIVILEGES = {
    'readonly': (LOGIN, 'ConfigureSelf'),
    'operator': (LOGIN, 'ConfigureSelf', CONFIGURE_COMPONENTS),
    'administrator': (LOGIN, 'ConfigureSelf', CONFIGURE_COMPONENTS,
                      CONFIGURE_USERS, CONFIGURE_MANAGER),
}


class RedfishAccess():
    """
    Resolves which Redfish setup and account a node is reached with.
    """

    def __init__(self):
        """
        Constructor - As of now, nothing have to initialize.
        """
        self.logger = Log.get_logger()


    def setup_id(self, nodename=None):
        """
        This method will resolve the redfishsetup a node points at - the node
        first, then its group, which is exactly how bmcsetup and osimage resolve.
        """
        node = Database().get_record(table='node', where=f'name = "{nodename}"')
        if not node:
            return None
        setupid = node[0]['redfishsetupid'] if 'redfishsetupid' in node[0] else None
        if setupid:
            return setupid
        groupid = node[0]['groupid']
        group = Database().get_record(table='group', where=f'id = "{groupid}"')
        if group and 'redfishsetupid' in group[0]:
            return group[0]['redfishsetupid']
        return None


    def pick_account(self, accounts=None, needs=LOGIN):
        """
        This method will pick the weakest account that carries the privilege an
        operation actually needs.

        One rule for reads and writes alike. It used to be two - reads took the
        weakest account and writes took the strongest - and the second was wrong
        in a way that quietly undid what an administrator had configured: power
        control is a write, so a setup holding both an Operator and an
        Administrator used the Administrator, and the reason for having two
        accounts disappeared.

        'write' could not express it either way, because a write is not one
        privilege. Resetting a system needs ConfigureComponents, which an Operator
        has; creating an account needs ConfigureUsers, which only an Administrator
        has. Asking for the privilege rather than for a rank is what lets the same
        rule serve both.

        A role we do not rank is *unknown*, not known-unable. Redfish lets a vendor
        define roles with arbitrary privilege sets, so one of those is tried rather
        than refused - stranding a node on a name we have not seen would be worse
        than attempting the call and reading the answer.
        """
        candidates = []
        unknown = []
        for account in accounts or []:
            role = str(account['role'] or '').strip()
            if not role:
                # no role recorded: usable for anything, which is what a setup
                # holding a single administrator has always relied on
                unknown.append((0, account))
                continue
            privileges = ROLE_PRIVILEGES.get(role.lower())
            if privileges is None:
                unknown.append((0, account))
            elif needs in privileges:
                candidates.append((len(privileges), account))
        if candidates:
            # fewest privileges first: the weakest account that can do the job
            return min(candidates, key=lambda entry: entry[0])[1]
        if unknown:
            return unknown[0][1]
        return None


    def for_node(self, nodename=None, needs=LOGIN):
        """
        This method will return how to reach a node's BMC over Redfish.

        Two answers now, and TRIX-2027 is why there are no longer three:
        (True, dict)   these settings and this account
        (False, text)  Redfish cannot be used for this node, and the reason is said
                       out loud per node rather than worked around.

        There used to be a third - no redfishsetup meant "carry on with the bmcsetup
        credentials". It worked, because IPMI and Redfish share one user store on
        the BMC, and that is exactly what made it wrong: an administrator who
        deliberately assigned no redfishsetup still got Redfish traffic, on
        credentials they had nominated for IPMI. The absence of configuration did
        not mean the absence of Redfish, so there was no way to say "do not touch
        this over Redfish" short of taking the BMC off the network.

        Capability is now the gate, which needs no flag: no redfishsetup, no
        Redfish. The protocol fallback is untouched - control still tries Redfish
        and then ipmitool - because that is a different mechanism and it is the
        feature.
        """
        setupid = self.setup_id(nodename=nodename)
        if not setupid:
            return False, (f'{nodename} has no redfishsetup assigned, so Redfish is '
                           'not configured for it')
        setup = Database().get_record(table='redfishsetup', where=f'id = "{setupid}"')
        if not setup:
            return False, f'redfishsetup {setupid} assigned to {nodename} no longer exists'
        accounts = Database().get_record(table='redfishaccount',
                                         where=f'redfishsetupid = "{setupid}"')
        if not accounts:
            return False, f"redfishsetup {setup[0]['name']} has no accounts"
        account = self.pick_account(accounts=accounts, needs=needs)
        if not account:
            return False, (f"redfishsetup {setup[0]['name']} has no account carrying "
                           f'{needs}; add one with a role that does, or this node '
                           'cannot be asked to do that over Redfish by configuration')
        return True, {
            'scheme': setup[0]['scheme'] or 'https',
            'port': setup[0]['port'],
            # a row written before verify had a default reads as None; make it a
            # real bool here rather than relying on None being falsy downstream
            'verify': bool(Helper().make_bool(setup[0]['verify'])),
            'username': account['username'],
            'password': account['password'],
            'account': account['name']
        }


    def hardware(self, nodename=None):
        """
        This method returns (vendor, model) for a node, normalised into the tokens
        the plugin search path uses, or (None, None) where nothing is known yet.

        The manufacturer is derived rather than configured: nodeinventory already
        holds it per node, so there is no column for an administrator to set and
        get wrong, and it stays true when hardware is replaced.

        A node can hold a snapshot per source and the two can disagree - dmidecode
        and Redfish do not always return the same vendor string for the same
        machine - so redfish wins where both exist. It is the BMC's own answer,
        and it is the one that exists before a node has ever been provisioned.
        """
        rows = Database().get_record(table='nodeinventory',
                                     where=f'nodeid IN (SELECT id FROM node WHERE name = "{nodename}")')
        if not rows:
            return None, None
        chosen = None
        for row in rows:
            if str(row['source'] or '').strip().lower() == 'redfish':
                chosen = row
                break
            if chosen is None:
                chosen = row
        return self.token(chosen['manufacturer']), self.token(chosen['product'], first=False)


    def token(self, value=None, first=True):
        """
        This method turns a hardware string into a plugin name.

        Vendor strings carry punctuation and a company suffix - 'Dell Inc.',
        'VMware, Inc.' - so the first word is what names the file. A model does not
        split usefully that way ('PowerEdge R650' is one model, not a family called
        PowerEdge), so the whole string is used for that.
        """
        text = str(value or '').strip()
        if not text:
            return None
        if first:
            text = text.split(' ')[0]
        text = ''.join(character for character in text.lower() if character.isalnum())
        return text or None


    def speaks_redfish(self, nodename=None):
        """
        This method says whether there is evidence that a node's BMC speaks Redfish.

        It gates the generic redfish plugin, and the reason is scale rather than
        tidiness. A redfish control plugin tries Redfish and falls back to ipmitool,
        so offering it to a BMC that does not speak Redfish costs a connect timeout
        per node before the fallback runs - invisible on a rig, and half an hour
        added to a sweep of a few thousand dark nodes.

        Evidence is an administrator having assigned a redfishsetup, or an inventory
        snapshot that came from Redfish and therefore proves it answered.
        """
        if self.setup_id(nodename=nodename):
            return True
        rows = Database().get_record(
            table='nodeinventory',
            where=f'source = "redfish" AND nodeid IN (SELECT id FROM node WHERE name = "{nodename}")')
        return bool(rows)


    def plugin_candidates(self, nodename=None, groupname=None, generic=None):
        """
        This method builds a plugin search path for a node, and the model that
        narrows each step of it.

        Node name and group name come first and are unchanged, so anything an
        administrator has explicitly named still wins. After them comes the node's
        manufacturer, derived from nodeinventory rather than configured, so the
        derived candidates can only take a slot that would otherwise have gone to
        default.

        A caller that has a vendor-neutral plugin to fall back on names it as
        generic, and it is offered only where there is evidence the BMC speaks
        Redfish. The control family has one; boot/bmc does not, because its plugins
        emit a shell snippet for the install rather than talking to a service.

        The model is returned separately because it is the loader's second level:
        it tries <name><model>.py, then <name>/<model>.py, then <name>/default.py,
        then <name>.py. Hardware from one vendor does differ, and that is where the
        difference goes.
        """
        candidates = [nodename, groupname]
        vendor, model = self.hardware(nodename=nodename)
        if vendor:
            candidates.append(vendor)
        if generic and self.speaks_redfish(nodename=nodename):
            candidates.append(generic)
        return [candidate for candidate in candidates if candidate], model
