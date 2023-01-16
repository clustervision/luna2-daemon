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
from common.constant import CONSTANT

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

        match name:
            case self.dhcp | self.dns | 'luna2':
                match action:
                    case 'start' | 'stop' | 'reload' | 'restart':
                        command = f'{CONSTANT["SERVICES"]["COMMAND"]} {action} {name}'
                        check_dhcp = Helper().dhcp_overwrite()
                        if check_dhcp:
                            output = Helper().runcommand(command)
                            response, code = self.service_status(name, action, output)
                        else:
                            response = f'{name} service file have errors.'
                            code = 500
                    case 'status':
                        command = f'{CONSTANT["SERVICES"]["COMMAND"]} {action} {name}'
                        output = Helper().runcommand(command)
                        response, code = self.service_status(name, action, output)
                    case _:
                        self.logger.error(f'Service Action {name} Is Not Recognized')
                        response = {'error': f'Service Action {action} Is Not Recognized.'}
                        code = 404
            case _:
                self.logger.error(f'Service Name {name} Is Not Recognized.')
                response = {'error': f'Service Name {name} Is Not Recognized.'}
                code = 404
        return response, code


    def service_status(self, name, action, output):
        """
        Input - name of service and action need to be perform
        Process - After Validating Token, Check Queue if the same request is enque in last two
                seconds. If Not Then only execute the action with the Help of Service Class.
        Output - Success or Failure.
        """

        match action:
            case 'start':
                if "(b'', b'')" in str(output):
                    self.logger.info(f'Service {name} is {action}ed.')
                    response = f'Service {name} is {action}ed.'
                    code = 200
                else:
                    self.logger.error(f'Service {name} is Failed to {action}.')
                    response = f'Service {name} is Failed to {action}.'
                    code = 500
            case 'stop':
                if "(b'', b'')" in str(output):
                    self.logger.info(f'Service {name} is {action}ped.')
                    response = f'Service {name} is {action}ped.'
                    code = 200
                else:
                    self.logger.error(f'Service {name} is Failed to {action}.')
                    response = f'Service {name} is Failed to {action}.'
                    code = 500
            case 'reload':
                if "Failed" in str(output):
                    self.logger.error(f'Service {name} is Failed to {action}.')
                    response = f'Service {name} is Failed to {action}.'
                    code = 500
                else:
                    self.logger.info(f'Service {name} is {action}ed.')
                    response = f'Service {name} is {action}ed.'
                    code = 200
            case 'restart':
                if "(b'', b'')" in str(output):
                    self.logger.info(f'Service {name} is {action}ed.')
                    response = f'Service {name} is {action}ed.'
                    code = 200
                else:
                    self.logger.error(f'Service {name} is Failed to {action}.')
                    response = f'Service {name} is Failed to {action}.'
                    code = 500
            case 'status':
                if 'active (running)' in str(output):
                    self.logger.info(f'Service {name} is Active & Running.')
                    response = {'monitor': {'Service': { name: 'OK, running'} } }
                    code = 200
                else:
                    self.logger.error('Service {name} is Not Active & Running.')
                    response = {'monitor': {'Service': { name: 'FAIL, not running'} } }
                    code = 500
        return response, code
