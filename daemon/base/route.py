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
Route Class will handle the reusable static-route catalog (route) and the
coupling of routes to networks, groups and nodes (routemap).
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import ipaddress
from utils.database import Database
from utils.log import Log
from utils.helper import Helper
from utils.model import Model


class Route():
    """
    This class is responsible for the static-route catalog and its couplings.
    """

    COUPLE_TABLES = ['network', 'group', 'node']

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()

    def get_routes(self, name=None):
        """
        This method returns the whole route catalog, or a single route by name.
        """
        where = f"name='{name}'" if name else None
        routes = Database().get_record(table='route', where=where)
        if not routes:
            return False, f"Route {name} does not exist" if name else "No routes are available"
        response = {'config': {'route': {}}}
        for route in routes:
            targets = self.coupled_targets(route['id'])
            response['config']['route'][route['name']] = {
                'name': route['name'],
                'destination': route['destination'],
                'gateway': route['gateway'],
                'metric': route['metric'],
                'device': route['device'],
                'comment': route['comment'],
                'assigned': ','.join(targets),
            }
        return True, response

    def update_route(self, name=None, request_data=None):
        """
        This method creates or updates a single route in the catalog.
        """
        if not request_data:
            return False, "Invalid request: Did not receive data"
        data = request_data['config']['route'][name]
        # a change only carries the edited fields, so fall back to the stored route
        exist = Database().get_record(table='route', where=f"name='{name}'")
        current = exist[0] if exist else {}
        newname = data.get('newname')
        if newname and exist:
            if Database().get_record(table='route', where=f"name='{newname}'"):
                return False, f"Invalid request: route {newname} already exists"
        target_name = newname if (newname and exist) else name
        destination = data.get('destination', current.get('destination'))
        gateway = data.get('gateway', current.get('gateway')) or ''
        device = data.get('device', current.get('device')) or ''
        metric = data.get('metric', current.get('metric'))
        comment = data.get('comment', current.get('comment'))
        valid, message = self.validate_route(destination, gateway, device, metric)
        if not valid:
            return False, message
        row_data = {
            'name': target_name,
            'destination': destination,
            'gateway': gateway,
            'device': device,
            'metric': metric,
            'comment': comment,
        }
        row = Helper().make_rows(row_data)
        if exist:
            Database().update('route', row, [{"column": "id", "value": current['id']}])
            if target_name != name:
                return True, f"Route {name} renamed to {target_name}"
            return True, f"Route {name} updated"
        Database().insert('route', row)
        return True, f"Route {name} created"

    def delete_route(self, name=None):
        """
        This method deletes a route, refusing while it is still coupled
        (osimage-style in-use guard). The operator must uncouple it first.
        """
        route = Database().get_record(table='route', where=f"name='{name}'")
        if not route:
            return False, f"Route {name} does not exist"
        targets = self.coupled_targets(route[0]['id'])
        if targets:
            inuse = ', '.join(targets[:10])
            return False, f"Invalid request: route {name} currently in use by {inuse} ..."
        return Model().delete_record(name=name, table='route', table_cap='Route')

    def couple_route(self, name=None, target_ref=None):
        """
        This method couples (stacks) a route onto a network, group or node.
        target_ref is a 'tableref/target' string (e.g. 'group/compute'), kept as a
        single param so HA journal replay maps (object, param) correctly.
        """
        valid, ref = self.resolve_target(name, target_ref)
        if not valid:
            return False, ref
        tableref, target, routeid, tablerefid = ref
        exist = Database().get_record(
            table='routemap',
            where=f"tableref='{tableref}' AND tablerefid='{tablerefid}' AND routeid='{routeid}'"
        )
        if exist:
            return True, f"Route {name} already coupled to {tableref} {target}"
        Database().insert('routemap', Helper().make_rows(
            {'tableref': tableref, 'tablerefid': tablerefid, 'routeid': routeid}))
        return True, f"Route {name} coupled to {tableref} {target}"

    def decouple_route(self, name=None, target_ref=None):
        """
        This method removes a route coupling from a network, group or node.
        """
        valid, ref = self.resolve_target(name, target_ref)
        if not valid:
            return False, ref
        tableref, target, routeid, tablerefid = ref
        exist = Database().get_record(
            table='routemap',
            where=f"tableref='{tableref}' AND tablerefid='{tablerefid}' AND routeid='{routeid}'"
        )
        if not exist:
            return False, f"Route {name} is not coupled to {tableref} {target}"
        Database().delete_row('routemap', [{"column": "id", "value": exist[0]['id']}])
        return True, f"Route {name} decoupled from {tableref} {target}"

    def resolve_target(self, route_name, target_ref):
        """Validate a couple request and return (tableref, target, routeid, tablerefid)."""
        tableref, _, target = (target_ref or '').partition('/')
        if tableref not in self.COUPLE_TABLES:
            return False, f"Invalid request: {tableref} cannot carry routes"
        if not target:
            return False, "Invalid request: missing target name"
        route = Database().get_record(table='route', where=f"name='{route_name}'")
        if not route:
            return False, f"Route {route_name} does not exist"
        tablerefid = Database().id_by_name(tableref, target)
        if not tablerefid:
            return False, f"{tableref.capitalize()} {target} does not exist"
        return True, (tableref, target, route[0]['id'], tablerefid)

    def coupled_targets(self, routeid):
        """Return human-readable 'type/name' labels for everything a route is coupled to."""
        targets = []
        for row in Database().get_record(table='routemap', where=f"routeid='{routeid}'") or []:
            name = Database().name_by_id(row['tableref'], row['tablerefid'])
            if name:
                targets.append(f"{row['tableref']}/{name}")
        return targets

    def assigned_names(self, tableref=None, tablerefid=None):
        """Return the names of routes coupled to a network/group/node (for show/list)."""
        rows = Database().get_record(
            table='routemap', where=f"tableref='{tableref}' AND tablerefid='{tablerefid}'")
        ids = [str(row['routeid']) for row in rows or []]
        if not ids:
            return []
        routes = Database().get_record(table='route', where=f"id IN ({','.join(ids)})") or []
        return [route['name'] for route in routes]

    def reconcile(self, tableref=None, tablerefid=None, names=None):
        """
        Make the couplings of a target match the given route names (inline -R/--routes).
        An empty/None list clears all couplings. Unknown names are ignored.
        """
        if tableref not in self.COUPLE_TABLES or not tablerefid:
            return
        if isinstance(names, str):
            names = names.split(',')
        wanted = set()
        for name in names or []:
            name = name.strip()
            if not name:
                continue
            route = Database().get_record(table='route', where=f"name='{name}'")
            if route:
                wanted.add(route[0]['id'])
        current = {}
        rows = Database().get_record(
            table='routemap', where=f"tableref='{tableref}' AND tablerefid='{tablerefid}'")
        for row in rows or []:
            current[row['routeid']] = row['id']
        for routeid in wanted - set(current):
            Database().insert('routemap', Helper().make_rows(
                {'tableref': tableref, 'tablerefid': tablerefid, 'routeid': routeid}))
        for routeid, mapid in current.items():
            if routeid not in wanted:
                Database().delete_row('routemap', [{"column": "id", "value": mapid}])

    def copy_couplings(self, tableref=None, source_id=None, target_id=None):
        """Copy all route couplings from one target id to another (used on clone)."""
        rows = Database().get_record(
            table='routemap', where=f"tableref='{tableref}' AND tablerefid='{source_id}'")
        for row in rows or []:
            Database().insert('routemap', Helper().make_rows(
                {'tableref': tableref, 'tablerefid': target_id, 'routeid': row['routeid']}))

    def delete_couplings(self, tableref=None, tablerefid=None):
        """Remove all route couplings of a target (used when a network/group/node is deleted)."""
        Database().delete_row('routemap', [
            {"column": "tableref", "value": tableref},
            {"column": "tablerefid", "value": tablerefid}])

    def effective_for_node(self, nodeid=None, groupid=None, networkids=None):
        """
        Strict override, like provision_interface: the highest level that has any coupled
        routes wins outright -- node overrides group overrides the network base -- and the
        lower levels are then ignored. networkids are the ids of the networks the node is
        attached to. Returns the winning level's routes, deduped by (destination, metric).
        """
        levels = [f'tableref="node" AND tablerefid="{nodeid}"']
        if groupid:
            levels.append(f'tableref="group" AND tablerefid="{groupid}"')
        if networkids:
            ids = ",".join(str(n) for n in networkids)
            levels.append(f'tableref="network" AND tablerefid IN ({ids})')
        for where in levels:
            routeids = [str(row['routeid']) for row in
                        Database().get_record(table='routemap', where=where) or []]
            if not routeids:
                continue
            routes = Database().get_record(table='route', where=f"id IN ({','.join(routeids)})") or []
            best = {}
            for route in routes:
                best[(route['destination'], route['metric'])] = route
            return list(best.values())
        return []

    def resolve_for_node(self, interfaces=None, nodeid=None, provision_interface=None):
        """
        Distribute the node's effective static routes onto its already-built interfaces for
        template rendering (mutates the interfaces in place). Additive: with no coupled
        routes the interfaces are untouched. Any error is logged and skipped so existing
        provisioning behaviour is never affected.
        """
        try:
            if not interfaces or not nodeid:
                return
            node = Database().get_record(table='node', where=f'id="{nodeid}"')
            groupid = node[0]['groupid'] if node else None
            networkids = [i['networkid'] for i in interfaces.values() if i.get('networkid')]
            routes = self.effective_for_node(nodeid, groupid, networkids)
            for route in routes:
                self._bind_route(interfaces, provision_interface, route)
        except Exception as exp:
            self.logger.error(f"TRIX-1481 static route resolution skipped: {exp}")

    def network_ids_for_node(self, nodeid=None):
        """Ids of the networks a node's own interfaces are attached to (network-base fallback)."""
        rows = Database().get_record_join(
            ['ipaddress.networkid'],
            ['ipaddress.tablerefid=nodeinterface.id'],
            ['tableref="nodeinterface"', f"nodeinterface.nodeid='{nodeid}'"])
        return [row['networkid'] for row in rows or [] if row.get('networkid')]

    def network_ids_for_group(self, groupid=None):
        """Ids of the networks a group's interfaces are attached to (network-base fallback)."""
        rows = Database().get_record(table='groupinterface', where=f"groupid='{groupid}'")
        return [row['networkid'] for row in rows or [] if row.get('networkid')]

    def network_route_names(self, networkids=None):
        """Route names coupled to any of the given networks (deduped, order-preserving)."""
        names = []
        for networkid in networkids or []:
            for name in self.assigned_names('network', networkid):
                if name not in names:
                    names.append(name)
        return names

    def _bind_route(self, interfaces, provision_interface, route):
        """Attach one route to the interface selected by device or next-hop subnet."""
        destination = route.get('destination')
        if not destination:
            return
        nexthop = route.get('gateway') or ''
        device = route.get('device') or ''
        family = 'routes_ipv6' if ':' in destination else 'routes'
        entry = {'destination': destination, 'gateway': nexthop, 'metric': route.get('metric')}
        target = None
        if device:
            target = provision_interface if device == 'BOOTIF' else (device if device in interfaces else None)
        elif nexthop:
            target = self._interface_for_nexthop(interfaces, nexthop, family)
        if not target or target not in interfaces:
            target = provision_interface
        if target in interfaces:
            if nexthop and not self._nexthop_on_link(interfaces[target], nexthop, family):
                entry['on_link'] = True
            interfaces[target].setdefault(family, []).append(entry)

    def _nexthop_on_link(self, iface, nexthop, family):
        """True if the next-hop lives inside the interface's own subnet (directly reachable)."""
        cidr = iface.get('network_ipv6' if family == 'routes_ipv6' else 'network')
        if not cidr:
            return False
        try:
            return ipaddress.ip_address(nexthop) in ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            return False

    def _interface_for_nexthop(self, interfaces, nexthop, family):
        """Return the interface whose network subnet contains the next-hop, else None."""
        for name, iface in interfaces.items():
            if self._nexthop_on_link(iface, nexthop, family):
                return name
        return None

    def validate_route(self, destination, gateway, device, metric):
        """
        Boundary validation: destination must be a valid CIDR, at least one of
        {device, gateway} must be set, a gateway (if given) must be a valid IP,
        and a metric (if given) must be an integer.
        """
        if not destination:
            return False, "Invalid request: destination is required"
        try:
            network = ipaddress.ip_network(destination, strict=False)
        except ValueError:
            return False, f"Invalid request: {destination} is not a valid network/host"
        if not gateway and not device:
            return False, "Invalid request: a route needs a gateway (next-hop) or a device"
        if gateway and not Helper().check_ip(gateway):
            return False, f"Invalid request: {gateway} is not a valid next-hop address"
        if gateway and ipaddress.ip_address(gateway).version != network.version:
            return False, f"Invalid request: next-hop {gateway} does not match the IPv{network.version} destination"
        if metric not in (None, '') and not str(metric).isdigit():
            return False, "Invalid request: metric must be a number"
        return True, "valid"
