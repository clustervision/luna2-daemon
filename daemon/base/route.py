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
        destination = data.get('destination')
        gateway = data.get('gateway') or ''
        device = data.get('device') or ''
        valid, message = self.validate_route(destination, gateway, device, data.get('metric'))
        if not valid:
            return False, message
        row_data = {
            'name': name,
            'destination': destination,
            'gateway': gateway,
            'device': device,
            'metric': data.get('metric'),
            'comment': data.get('comment'),
        }
        row = Helper().make_rows(row_data)
        exist = Database().get_record(table='route', where=f"name='{name}'")
        if exist:
            Database().update('route', row, [{"column": "id", "value": exist[0]['id']}])
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

    def couple_route(self, tableref=None, target=None, route_name=None):
        """
        This method couples (stacks) a route onto a network, group or node.
        """
        valid, ref = self.resolve_target(tableref, target, route_name)
        if not valid:
            return False, ref
        routeid, tablerefid = ref
        exist = Database().get_record(
            table='routemap',
            where=f"tableref='{tableref}' AND tablerefid='{tablerefid}' AND routeid='{routeid}'"
        )
        if exist:
            return True, f"Route {route_name} already coupled to {tableref} {target}"
        Database().insert('routemap', Helper().make_rows(
            {'tableref': tableref, 'tablerefid': tablerefid, 'routeid': routeid}))
        return True, f"Route {route_name} coupled to {tableref} {target}"

    def decouple_route(self, tableref=None, target=None, route_name=None):
        """
        This method removes a route coupling from a network, group or node.
        """
        valid, ref = self.resolve_target(tableref, target, route_name)
        if not valid:
            return False, ref
        routeid, tablerefid = ref
        exist = Database().get_record(
            table='routemap',
            where=f"tableref='{tableref}' AND tablerefid='{tablerefid}' AND routeid='{routeid}'"
        )
        if not exist:
            return False, f"Route {route_name} is not coupled to {tableref} {target}"
        Database().delete_row('routemap', [{"column": "id", "value": exist[0]['id']}])
        return True, f"Route {route_name} decoupled from {tableref} {target}"

    def resolve_target(self, tableref, target, route_name):
        """Validate a couple request and return (routeid, tablerefid)."""
        if tableref not in self.COUPLE_TABLES:
            return False, f"Invalid request: {tableref} cannot carry routes"
        route = Database().get_record(table='route', where=f"name='{route_name}'")
        if not route:
            return False, f"Route {route_name} does not exist"
        tablerefid = Database().id_by_name(tableref, target)
        if not tablerefid:
            return False, f"{tableref.capitalize()} {target} does not exist"
        return True, (route[0]['id'], tablerefid)

    def coupled_targets(self, routeid):
        """Return human-readable 'type/name' labels for everything a route is coupled to."""
        targets = []
        for row in Database().get_record(table='routemap', where=f"routeid='{routeid}'") or []:
            name = Database().name_by_id(row['tableref'], row['tablerefid'])
            if name:
                targets.append(f"{row['tableref']}/{name}")
        return targets

    def validate_route(self, destination, gateway, device, metric):
        """
        Boundary validation: destination must be a valid CIDR, at least one of
        {device, gateway} must be set, a gateway (if given) must be a valid IP,
        and a metric (if given) must be an integer.
        """
        if not destination:
            return False, "Invalid request: destination is required"
        try:
            ipaddress.ip_network(destination, strict=False)
        except ValueError:
            return False, f"Invalid request: {destination} is not a valid network/host"
        if not gateway and not device:
            return False, "Invalid request: a route needs a gateway (next-hop) or a device"
        if gateway and not Helper().check_ip(gateway):
            return False, f"Invalid request: {gateway} is not a valid next-hop address"
        if metric not in (None, '') and not str(metric).isdigit():
            return False, "Invalid request: metric must be a number"
        return True, "valid"
