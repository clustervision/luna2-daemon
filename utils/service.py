#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File is a Service Class, responsible to perform start, stop, reload, status, or restart action on provided service name.
"""

from utils.helper import *
from utils.log import *


class Service(object):

    """
    Constructor - Initialize The Service Names.
    """
    def __init__(self):
        self.DHCP = DHCP
        self.DNS = DNS
        self.logger = Log.get_logger()


    """
    Input - name of service and action need to be perform
    Process - Validate the Service Name and Action and perform the action with the help of runcommand method from Helper Class.
    Output - Success or Failure.
    """
    def luna_service(self, name, action):
        match name:
            case self.DHCP | self.DNS:
                match action:
                    case "start" | "stop" | "reload" | "restart" | "status":
                        command = "{} {} {}".format(COMMAND, action, name) ## Fetch the command from the .conf file
                        output = Helper.runcommand(command)
                        response, code = self.service_status(name, action, output)
                    case _:
                        response = {"error": "Service Action {} is not recognized.".format(action)}
                        code = 400
            case _:
                response = {"error": "Service Name {} is not recognized.".format(name)}
                code = 400
        return response, code


    """
    Input - name of service and action need to be perform
    Process - After Validating Token, Check Queue if the same request is enque in last two seconds. If Not Then only execute the action with the Help of Service Class.
    Output - Success or Failure.
    """
    def service_status(self, name, action, output):
        match action:
            case "start":
                if "(b'', b'')" in str(output):
                    response = "Service {} is {}ed.".format(name, action)
                    code = 200
                else:
                    response = "Service {} is Failed to {}.".format(name, action)
                    code = 200
            case "stop":
                if "(b'', b'')" in str(output):
                    response = "Service {} is {}ped.".format(name, action)
                    code = 200
                else:
                    response = "Service {} is Failed to {}.".format(name, action)
                    code = 200
            case "reload":
                if "Failed" in str(output):
                    response = "Service {} is Failed to {}.".format(name, action)
                    code = 200
                else:
                    response = "Service {} is {}ed.".format(name, action)
                    code = 200
            case "restart":
                if "(b'', b'')" in str(output):
                    self.logger.info("This is Boot API. It will start render boot_ipxe.cfg")
                    response = "Service {} is {}ed.".format(name, action)
                    code = 200
                else:
                    response = "Service {} is Failed to {}.".format(name, action)
                    code = 200
            case "status":
                if "active (running)" in str(output):
                    response = "Service {} is Active & Running.".format(name)
                    code = 200
                else:
                    response = "Service {} is Not Active & Running.".format(name)
                    code = 200
        return response, code
