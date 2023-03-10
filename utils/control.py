
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

    def control_child(self,pipeline,t=0):
         run=1
         while run:
             hostname,action=pipeline.get_node()
             if hostname:
                 self.logger.info("control_child thread "+str(t)+": "+hostname+" -> called for "+action)
                 node = Database().get_record(None, 'node', f' WHERE name = "{hostname}"')
                 if node:
                     groupid = node[0]['groupid']
                     group = Database().get_record(None, 'group', f' WHERE id = "{groupid}"')
                     if group:
                         bmcsetupid = group[0]['bmcsetupid']
                         bmcsetup = Database().get_record(None, 'bmcsetup', f' WHERE id = "{bmcsetupid}"')
                         if bmcsetup:
                             self.logger.info("control_child thread "+str(t)+": bmcsetup: "+str(bmcsetup))
                             try:
                                 username = bmcsetup[0]['username']
                                 password = bmcsetup[0]['password']
                                 #self.logger.info("control_child thread "+str(t)+": "+hostname+" -> performing "+action+", with user/pass "+username+"/"+password)
                                 status = self.ipmi_action(hostname, action, username, password) or 'no response or timeout'
                             except:
                                 status='bmc credentials not found'
                             pipeline.add_message({hostname: status})
                         else:
                             self.logger.info(f'{hostname} not have any bmcsetup.')
                             pipeline.add_message({hostname: 'does not have any bmcsetup'})
                     else:
                         self.logger.info(f'{hostname} not have any group.')
                         pipeline.add_message({hostname: 'does not have any group'})
                 else:
                     self.logger.info(f'{hostname} not have any node.')
                     pipeline.add_message({hostname: 'does not have any node information'})
                 run=0 # setting this to 0 means we only do one iteration. we can do loops, but we let mother control this
             else:
                 run=0

    # -----------------------------------------------------------------

    def control_mother(self,pipeline,request_id,batch=10,delay=10):
        #self.logger.info("control_mother called")
        while(pipeline.has_nodes()):

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                 _ = [executor.submit(self.control_child, pipeline,t) for t in range(1,batch)]

            sleep(0.1) # not needed but just in case a child does a lock right after i fetch the list.
            results=pipeline.get_messages()

            for key in list(results):
                self.logger.info(f"control_mother result: {key}: {results[key]}")
                Helper().insert_mesg_in_status(request_id,"lpower",f"{key}:{results[key]}")
                pipeline.del_message(key)
            sleep(delay)

        Helper().insert_mesg_in_status(request_id,"lpower",f"EOF")


