
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This Is the Control Class, to offload the API

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2025, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


import concurrent.futures
from time import sleep
from utils.log import Log
from utils.database import Database
from utils.helper import Helper
from utils.status import Status
from common.constant import CONSTANT


class Control():
    """
    All kind of helper methods.
    """

    def __init__(self):
        """
        Constructor - As of now, nothing have to initialize.
        """
        self.logger = Log.get_logger()
        plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIRECTORY"]
        self.control_plugins = Helper().plugin_finder(f'{plugins_path}/control')
        self.hooks_plugins = Helper().plugin_finder(f'{plugins_path}/hooks')


    def control_child(self, pipeline, t=0):
        """
        This method will control the child process
        """
        run = 1
        while run:
            nodename, command = pipeline.get_node()
            if nodename:
                message = f"control_child thread {t} called for: {nodename} {command}"
                self.logger.info(message)
                # node = Database().get_record(table='node', where=f'name = "{nodename}"')
                node = Database().get_record_join(
                    [
                        'node.id as nodeid',
                        'node.name as nodename',
                        'node.groupid as groupid',
                        'group.name as groupname',
                        'ipaddress.ipaddress as device',
                        'node.bmcsetupid'
                    ],
                    [
                        'nodeinterface.nodeid=node.id',
                        'ipaddress.tablerefid=nodeinterface.id',
                        'group.id=node.groupid'
                    ],
                    [
                        'tableref="nodeinterface"',
                        "nodeinterface.interface='BMC'",
                        f"node.name='{nodename}'"
                    ]
                )
                if node:
                    bmcsetupid = None
                    if 'bmcsetupid' in node[0] and not node[0]['bmcsetupid']:
                        groupid = node[0]['groupid']
                        group = Database().get_record(table='group', where=f'id = "{groupid}"')
                        if group:
                            bmcsetupid = group[0]['bmcsetupid']
                        else:
                            self.logger.info(f'{nodename} not have any group')
                            pipeline.add_message({nodename: command+':None:does not have any group'})
                    else:
                        bmcsetupid = node[0]['bmcsetupid']
                    bmcsetup = Database().get_record(table='bmcsetup', where=f'id = "{bmcsetupid}"')
                    if bmcsetup and 'device' in node[0] and node[0]['device']:
                        self.logger.debug(f"control_child thread {t}: bmcsetup: {bmcsetup}")
                        try:
                            device   = node[0]['device']
                            username = bmcsetup[0]['username']
                            password = bmcsetup[0]['password']
                            command = command.replace('_', '')
                            ret, status = self.control_action(
                                node[0]['nodename'],
                                node[0]['groupname'],
                                command,
                                device,
                                username,
                                password
                            )
                            self.logger.debug(f"control: ret=[{ret}], status=[{status}]")
                            runret, runstatus = self.control_hook(
                                node[0]['nodename'],
                                node[0]['groupname'],
                                command,
                            )
                            self.logger.debug(f"run: ret=[{runret}], status=[{runstatus}]")
                        except Exception as exp:
                            status=f'command returned {exp}'
                            self.logger.error(f"uh oh... {exp}")
                        pipeline.add_message({nodename: command+':'+str(ret)+':'+status})
                    else:
                        self.logger.info(f'{nodename} does not have a suitable bmcsetup. Device or IP address not configured')
                        pipeline.add_message({nodename: command+':None:does not have a suitable bmcsetup'})
                else:
                    self.logger.info(f'{nodename} does not have any suitable config or BMC interface not found.')
                    pipeline.add_message({nodename: command+':None:does not exist or does not have BMC configured'})
                run = 0
                # setting this to 0 means we only do one iteration.
                # we can do loops, but we let mother control this
            else:
                self.logger.info('empty pipe.')
                run = 0


    def control_action(self, nodename=None, groupname=None,
                       command=None, device=None, username=None, password=None):
        """
        This method will handle the power control actions.
        """
        self.logger.debug(nodename)
        self.logger.debug(groupname)
        return_code, message = False, ""
        # class TimeoutError(Exception):
        #     pass

        # def handler(signum, frame):
        #     raise TimeoutError()

        # signal.signal(signal.SIGALRM, handler)
        # signal.alarm(60)
        try:
            control_plugin = Helper().plugin_load(
                self.control_plugins,
                'control',
                [nodename,groupname]
            )
            match command:
                case 'power on':
                    return_code, message = control_plugin().power_on(
                        device=device, 
                        username=username, 
                        password=password
                    )
                case 'power off':
                    return_code, message = control_plugin().power_off(
                        device = device,
                        username = username,
                        password = password
                    )
                case 'power status':
                    return_code, message = control_plugin().power_status(
                        device = device,
                        username = username,
                        password = password
                    )
                case 'power reset':
                    return_code, message = control_plugin().power_reset(
                        device = device,
                        username = username,
                        password = password
                    )
                case 'power cycle':
                    return_code, message = control_plugin().power_cycle(
                        device = device,
                        username = username,
                        password = password
                    )
                case 'chassis identify':
                    return_code, message = control_plugin().identify(
                        device = device,
                        username = username,
                        password = password
                    )
                case 'chassis noidentify':
                    return_code, message = control_plugin().no_identify(
                        device = device,
                        username = username,
                        password = password
                    )
                case 'sel list':
                    return_code, message = control_plugin().sel_list(
                        device = device,
                        username = username,
                        password = password
                    )
                    message = message.replace("\n",";;")
                case 'sel clear':
                    return_code, message = control_plugin().sel_clear(
                        device = device,
                        username = username,
                        password = password
                    )
                case _:
                    return_code, message = False, "Instruction not implemented"

            self.logger.debug(f"return_code=[{return_code}], mesg=[{message}]")

        except TimeoutError:
            return_code = False
            message = "Timeout"
        except Exception as exp:
            return_code = False
            message = exp
        # finally:
        #     signal.alarm(0)
        return return_code, message


    def control_hook(self, nodename=None, groupname=None, command=None):
        """
        This method will handle the optional run during a power control action.
        """
        self.logger.debug(nodename)
        self.logger.debug(groupname)
        return_code, message = False, ""
        # class TimeoutError(Exception):
        #     pass

        # def handler(signum, frame):
        #     raise TimeoutError()

        # signal.signal(signal.SIGALRM, handler)
        # signal.alarm(60)
        try:
            hook_plugin = Helper().plugin_load(
                self.hooks_plugins,
                'hooks/control',
                [nodename,groupname]
            )
            match command:
                case 'power on':
                    return_code, message = hook_plugin().power_on(
                        nodename=nodename, groupname=groupname
                    )
                case 'power off':
                    return_code, message = hook_plugin().power_on(
                        nodename=nodename, groupname=groupname
                    )
                case 'power status':
                    return_code, message = hook_plugin().power_on(
                        nodename=nodename, groupname=groupname
                    )
                case 'power reset':
                    return_code, message = hook_plugin().power_on(
                        nodename=nodename, groupname=groupname
                    )
                case 'power cycle':
                    return_code, message = hook_plugin().power_on(
                        nodename=nodename, groupname=groupname
                    )
                case 'chassis identify':
                    return_code, message = hook_plugin().power_on(
                        nodename=nodename, groupname=groupname
                    )
                case 'chassis noidentify':
                    return_code, message = hook_plugin().power_on(
                        nodename=nodename, groupname=groupname
                    )
                case 'sel list':
                    return_code, message = hook_plugin().power_on(
                        nodename=nodename, groupname=groupname
                    )
                    message = message.replace("\n",";;")
                case 'sel clear':
                    return_code, message = hook_plugin().power_on(
                        nodename=nodename, groupname=groupname
                    )
                case _:
                    return_code, message = False, "Instruction not implemented"

            if message != "success": # the default bogus message...
                self.logger.info(f"return_code={return_code}, mesg='{message}'")

        except TimeoutError:
            return_code = False
            message = "Timeout"
            self.logger.error(message)
        except Exception as exp:
            return_code = False
            message = exp
            self.logger.error(message)
        # finally:
        #     signal.alarm(0)
        return return_code, message


    def control_mother(self, pipeline=None, request_id=None, batch=10, delay=10):
        """
        This method will handle main thread of power control.
        """
        # self.logger.info("control_mother called")
        try:
            while pipeline.has_nodes():
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    _ = [executor.submit(self.control_child, pipeline,t) for t in range(1,batch)]
                sleep(0.1)
                # not needed but just in case a child does a lock right after i fetch the list.
                results=pipeline.get_messages()

                for key in list(results):
                    self.logger.debug(f"control_mother result: {key}: {results[key]}")
                    Status().add_message(request_id, "lpower", f"{key}:{results[key]}")
                    pipeline.del_message(key)
                sleep(delay)
            Status().add_message(request_id, "lpower", "EOF")
        except Exception as exp:
            self.logger.error(f"service_mother has problems: {exp}")
