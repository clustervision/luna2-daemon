
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This Is the Control Class, to offload the API

"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
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
        plugins_path=CONSTANT["PLUGINS"]["PLUGINS_DIR"]
        self.control_plugins = Helper().plugin_finder(f'{plugins_path}/control')
        # needs to be with constants. pending


    def control_child(self, pipeline, t=0):
        """
        This method will control the child process
        """
        run = 1
        while run:
            nodename, action = pipeline.get_node()
            if nodename:
                message = f"control_child thread {t} called for: {nodename} {action}"
                self.logger.info(message)
                # node = Database().get_record(None, 'node', f' WHERE name = "{nodename}"')
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
                    if 'bmcsetupid' in node[0] and str(node[0]['bmcsetupid']) == 'None':
                        groupid = node[0]['groupid']
                        group = Database().get_record(None, 'group', f' WHERE id = "{groupid}"')
                        if group:
                            bmcsetupid = group[0]['bmcsetupid']
                        else:
                            self.logger.info(f'{nodename} not have any group.')
                            pipeline.add_message({nodename: 'None:does not have any group'})
                    else:
                        bmcsetupid = node[0]['bmcsetupid']
                    where = f' WHERE id = "{bmcsetupid}"'
                    bmcsetup = Database().get_record(None, 'bmcsetup', where)
                    if bmcsetup and 'device' in node[0] and node[0]['device']:
                        self.logger.debug(f"control_child thread {t}: bmcsetup: {bmcsetup}")
                        try:
                            device   = node[0]['device']
                            username = bmcsetup[0]['username']
                            password = bmcsetup[0]['password']
                            action = action.replace('_', '')
                            # self.logger.info("control_child thread "+str(t)+": "+nodename+" ->
                            # performing "+action+", with user/pass "+username+"/"+password)
                            # status = Helper().ipmi_action(nodename, action, username, password)
                            # or 'no response or timeout'
                            ret, status = self.control_action(
                                node[0]['nodename'],
                                node[0]['groupname'],
                                action,
                                device,
                                username,
                                password
                            )
                            self.logger.debug(f"ret=[{ret}], status=[{status}]")
                        except Exception as exp:
                            status=f'command returned {exp}'
                            self.logger.error(f"uh oh... {exp}")
                        pipeline.add_message({nodename: str(ret)+':'+status})
                    else:
                        self.logger.info(f'{nodename} not have any bmcsetup.')
                        pipeline.add_message({nodename: 'None:does not have any bmcsetup'})
                else:
                    self.logger.info(f'{nodename} does not have any suitable config.')
                    pipeline.add_message({nodename: 'None:does not have any node information'})
                run = 0
                # setting this to 0 means we only do one iteration.
                # we can do loops, but we let mother control this
            else:
                self.logger.info('empty pipe.')
                run = 0


    def control_action(self, nodename=None, groupname=None, action=None, device=None, username=None, password=None):
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
                ['nodename,groupname']
            )
            match action:
                case 'power on':
                    return_code, message = control_plugin().power_on(
                        device=device, username=username, password=password
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
                case 'power identify':
                    return_code, message = control_plugin().identify(
                        device = device,
                        username = username,
                        password = password
                    )
                case 'power noidentify':
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
                case 'sel clear':
                    return_code, message = control_plugin().sel_clear(
                        device = device,
                        username = username,
                        password = password
                    )
                case _:
                    return_code, message = False, "NO-Match"

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

