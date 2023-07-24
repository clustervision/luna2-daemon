
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

import os
import pwd
import subprocess
import json
from utils.log import Log
from utils.database import Database
import concurrent.futures
import threading
from time import sleep
from datetime import datetime
from utils.helper import Helper
from utils.status import Status
import signal

    # -----------------------------------------------------------------

class Control(object):
    """
    All kind of helper methods.
    """

    def __init__(self):
        """
        Constructor - As of now, nothing have to initialize.
        """
        self.logger = Log.get_logger()
        self.control_plugins = Helper().plugin_finder('/trinity/local/luna/plugins/control')  # needs to be with constants. pending

    # -----------------------------------------------------------------


    def control_child(self,pipeline,t=0):
         run=1
         while run:
             nodename,action=pipeline.get_node()
             if nodename:
                 self.logger.info("control_child thread "+str(t)+": "+nodename+" -> called for "+action)
                 #node = Database().get_record(None, 'node', f' WHERE name = "{nodename}"')
                 node = Database().get_record_join(
                      ['node.id as nodeid','node.name as nodename','node.groupid as groupid','group.name as groupname','ipaddress.ipaddress as device','node.bmcsetupid'],
                      ['nodeinterface.nodeid=node.id','ipaddress.tablerefid=nodeinterface.id','group.id=node.groupid'],
                      ['tableref="nodeinterface"',f"nodeinterface.interface='BMC'",f"node.name='{nodename}'"]
                 )
                 if node:
                     bmcsetupid=None
                     if 'bmcsetupid' in node[0] and str(node[0]['bmcsetupid']) == 'None':
                         groupid = node[0]['groupid']
                         group = Database().get_record(None, 'group', f' WHERE id = "{groupid}"')
                         if group:
                             bmcsetupid = group[0]['bmcsetupid']
                         else:
                             self.logger.info(f'{nodename} not have any group.')
                             pipeline.add_message({nodename: 'does not have any group'})
                     else:
                         bmcsetupid = node[0]['bmcsetupid']
                     bmcsetup = Database().get_record(None, 'bmcsetup', f' WHERE id = "{bmcsetupid}"')
                     if bmcsetup and 'device' in node[0] and node[0]['device']:
                         self.logger.info("control_child thread "+str(t)+": bmcsetup: "+str(bmcsetup))
                         try:
                             device   = node[0]['device']
                             username = bmcsetup[0]['username']
                             password = bmcsetup[0]['password']
                             action = action.replace('_', '')
                             #self.logger.info("control_child thread "+str(t)+": "+nodename+" -> performing "+action+", with user/pass "+username+"/"+password)
                             #status = Helper().ipmi_action(nodename, action, username, password) or 'no response or timeout'
                             ret,status = self.control_action(node[0]['nodename'], node[0]['groupname'], action, device, username, password, position=None)
                             self.logger.debug(f"ret=[{ret}], status=[{status}]")
                         except Exception as exp:
                             status=f'command returned {exp}'
                             self.logger.error(f"uh oh... {exp}")
                         pipeline.add_message({nodename: status})
                     else:
                         self.logger.info(f'{nodename} not have any bmcsetup.')
                         pipeline.add_message({nodename: 'does not have any bmcsetup'})
                 else:
                     self.logger.info(f'{nodename} not have any suitable config.')
                     pipeline.add_message({nodename: 'does not have any node information'})
                 run=0 # setting this to 0 means we only do one iteration. we can do loops, but we let mother control this
             else:
                 self.logger.info(f'empty pipe.')
                 run=0

    # -----------------------------------------------------------------

    def control_action(self,nodename,groupname,action,device,username,password,position=None):

        ret,mesg = False,""

#        class TimeoutError(Exception):
#            pass
#
#        def handler(signum, frame):
#            raise TimeoutError()
#
#        signal.signal(signal.SIGALRM, handler)
#        signal.alarm(60)

        try:

            ControlPlugin=Helper().plugin_load(self.control_plugins,'control',['nodename,groupname'])
            match action:
                case 'on':
                    ret,mesg=ControlPlugin().on(device=device, username=username, password=password, position=None)
                case 'off':
                    ret,mesg=ControlPlugin().off(device=device, username=username, password=password, position=None)
                case 'status':
                    ret,mesg=ControlPlugin().status(device=device, username=username, password=password, position=None)
                case 'reset':
                    ret,mesg=ControlPlugin().reset(device=device, username=username, password=password, position=None)
                case 'cycle':
                    ret,mesg=ControlPlugin().cycle(device=device, username=username, password=password, position=None)
                case 'identify':
                    ret,mesg=ControlPlugin().identify(device=device, username=username, password=password, position=None)
                case 'noidentify':
                    ret,mesg=ControlPlugin().no_identify(device=device, username=username, password=password, position=None)

            self.logger.debug(f"mesg=[{mesg}]")
       
        except TimeoutError as exc:
            ret=False
            mesg="Timeout"
        except Exception as exp:
            ret=False
            mesg=exp
#        finally:
#            signal.alarm(0)

        return ret,mesg



    # -----------------------------------------------------------------

    def control_mother(self,pipeline,request_id,batch=10,delay=10):
        #self.logger.info("control_mother called")
        try:
            while(pipeline.has_nodes()):

                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                     _ = [executor.submit(self.control_child, pipeline,t) for t in range(1,batch)]

                sleep(0.1) # not needed but just in case a child does a lock right after i fetch the list.
                results=pipeline.get_messages()

                for key in list(results):
                    self.logger.info(f"control_mother result: {key}: {results[key]}")
                    Status().add_message(request_id,"lpower",f"{key}:{results[key]}")
                    pipeline.del_message(key)
                sleep(delay)

            Status().add_message(request_id,"lpower",f"EOF")

        except Exception as exp:
            self.logger.error(f"service_mother has problems: {exp}")


