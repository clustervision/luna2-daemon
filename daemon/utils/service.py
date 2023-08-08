#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This File is a Service Class, responsible to perform start, stop, reload, status,
or restart action on provided service name.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

from utils.helper import Helper
from utils.log import Log
from utils.config import Config
from common.constant import CONSTANT
from utils.status import Status
import concurrent.futures
from time import sleep,time
from utils.queue import Queue

class Service(object):
    """
    Manage All service operations.
    """

    def __init__(self):
        """
        Constructor - Initialize The Service Names.
        """
        self.dhcp = CONSTANT['SERVICES']['DHCP']
        self.dns = CONSTANT['SERVICES']['DNS']
        self.logger = Log.get_logger()


    def luna_service(self, name, action):
        """
        Input - name of service and action need to be perform
        Process - Validate the Service Name and Action and perform the action
                with the help of runcommand method from Helper Class.
        Output - Success or Failure.
        """

        if "dhcp" == name:
            name = CONSTANT['SERVICES']['DHCP']
        if "dns" == name:
            name = CONSTANT['SERVICES']['DNS']
       
        status=False 
        match name:
            case self.dhcp:
                match action:
                    case 'start' | 'stop' | 'reload' | 'restart':
                        command = f'{CONSTANT["SERVICES"]["COMMAND"]} {action} {name}'
                        check_dhcp = Config().dhcp_overwrite()
                        if check_dhcp:
                            output, exit_code = Helper().runcommand(command,True,60)
                            sleep(2)
                            status, response = self.service_status(name, action, exit_code, output)
                        else:
                            response = f'{name} config file has errors'
                            status=False
                    case 'status':
                        command = f'{CONSTANT["SERVICES"]["COMMAND"]} {action} {name}'
                        output, exit_code = Helper().runcommand(command,True,60)
                        status, response = self.service_status(name, action, exit_code, output)
                    case _:
                        response = f'Service Action {action} Is Not Recognized'
                        status=False
            case self.dns:
                match action:
                    case 'start' | 'stop' | 'reload' | 'restart':
                        command = f'{CONSTANT["SERVICES"]["COMMAND"]} {action} {name}'
                        check_dns = Config().dns_configure()
                        if check_dns:
                            output, exit_code = Helper().runcommand(command,True,60)
                            sleep(2)
                            status, response = self.service_status(name, action, exit_code, output)
                        else:
                            response = f'{name} config file has errors.'
                            status=False
                    case 'status':
                        command = f'{CONSTANT["SERVICES"]["COMMAND"]} {action} {name}'
                        output, exit_code = Helper().runcommand(command,True,60)
                        status, response = self.service_status(name, action, exit_code, output)
                    case _:
                        response = f'Service Action {action} Is Not Recognized.'
                        status=False
            case 'luna2':
                match action:
                    case 'start' | 'stop' | 'reload' | 'restart':
                        response = 'not implemented'
                        status=True
                    case 'status':
                        response = 'not implemented'
                        status=True
                    case _:
                        response = f'Service Action {action} Is Not Recognized.'
                        status=False
            case _:
                self.logger.error(f'Service Name {name} Is Not Recognized.')
                response = f'Service Name {name} Is Not Recognized.'
                status=False
        return status, response


    def service_status(self, name, action, exit_code=0, output=None):
        """
        Input - name of service and action need to be perform
        Process - After Validating Token, Check Queue if the same request is enque in last two
                seconds. If Not Then only execute the action with the Help of Service Class.
        Output - Success or Failure.
        """

        status=False
        match action:
            case 'start':
                if exit_code == 0 or "(b'', b'')" in str(output):
                    self.logger.info(f'Service {name} is {action}ed.')
                    response = f'Service {name} is {action}ed.'
                    status=True
                else:
                    self.logger.error(f'Service {name} is Failed to {action}: {output}')
                    response = f'Service {name} is Failed to {action}.'
                    status=False
            case 'stop':
                if exit_code == 0 or "(b'', b'')" in str(output):
                    self.logger.info(f'Service {name} is {action}ped.')
                    response = f'Service {name} is {action}ped.'
                    status=True
                else:
                    self.logger.error(f'Service {name} is Failed to {action}: {output}')
                    response = f'Service {name} is Failed to {action}.'
                    status=False
            case 'reload':
                if exit_code != 0 or "Failed" in str(output):
                    self.logger.error(f'Service {name} is Failed to {action}: {output}')
                    response = f'Service {name} is Failed to {action}.'
                    status=False
                else:
                    self.logger.info(f'Service {name} is {action}ed.')
                    response = f'Service {name} is {action}ed.'
                    status=True
            case 'restart':
                if exit_code == 0 or "(b'', b'')" in str(output):
                    self.logger.info(f'Service {name} is {action}ed.')
                    response = f'Service {name} is {action}ed.'
                    status=True
                else:
                    self.logger.error(f'Service {name} is Failed to {action}: {output}')
                    response = f'Service {name} is Failed to {action}.'
                    status=False
            case 'status':
                if exit_code == 0 or 'active (running)' in str(output):
                    self.logger.info(f'Service {name} is Active & Running.')
                    #response = {'monitor': {'Service': { name: 'OK, running'} } }
                    response = 'OK, running'
                    status=True
                else:
                    self.logger.error(f'Service {name} is Not Active & Running: {output}')
                    #response = {'monitor': {'Service': { name: 'FAIL, not running'} } }
                    response = 'FAIL, not running'
                    status=False
        return status, response

    def service_mother(self,service,action,request_id):  # service and action not really mandatory unless we use the below commented block

        self.logger.info(f"service_mother called")
        try:
#            # Below section is already done in config/pack GET call but kept here in case we want to move it back
#            queue_id,response = Queue().add_task_to_queue(f'{service}:{action}','service',request_id)
#            if not queue_id:
#                self.logger.info(f"service_mother cannot get queue_id")
#                Status().add_message(request_id,"luna",f"error queuing my task")
#                return
#            self.logger.info(f"service_mother added task to queue: {queue_id}")
#            Status().add_message(request_id,"luna",f"queued pack service {service} with queue_id {queue_id}")
#
#            next_id = Queue().next_task_in_queue('service')
#            if queue_id != next_id:
#                # little tricky. we assume that another mother proces was spawned that took care of the runs... 
#                # we need a check based on last hear queue entry, then we continue. pending in next_task_in_queue.
#                return

            while next_id := Queue().next_task_in_queue('service'):
                self.logger.info(f"service_mother sees job in queue as next: {next_id}")
                details=Queue().get_task_details(next_id)
                request_id=details['request_id']
                service,action=details['task'].split(':')

                if action and service:
    
                    Queue().update_task_status_in_queue(next_id,'in progress')
                    Status().add_message(request_id,"luna",f"{action} service {service}")

                    status, response = self.luna_service(service, action)

                    if status is True:
                        self.logger.info(f'service {service} {action} successful.')
                        Status().add_message(request_id,"luna",f"finished {action} service {service}")
                    else:
                        self.logger.info(f'service {service} {action} error: {response}.')
                        Status().add_message(request_id,"luna",f"error {action} service {service}: {response}")

                    Queue().remove_task_from_queue(next_id)
                    Status().add_message(request_id,"luna",f"EOF")
                else:
                    self.logger.info(f"{details['task']} is not for us.")
                    sleep(10)

        except Exception as exp:
            self.logger.error(f"service_mother has problems: {exp}")


    def queue(self,service,action):
        queue_id,response = Queue().add_task_to_queue(f'{service}:{action}','service','__internal__')
        if queue_id:
            next_id = Queue().next_task_in_queue('service')
            if queue_id == next_id:
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                executor.submit(self.service_mother,service,action,'__internal__')
                executor.shutdown(wait=False)
        else: # fallback, worst case
            status, response = self.luna_service(service, action)

