#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"

"""
This File is a Service Class, responsible to perform start, stop, reload, restart and action items for provided service name.
TODO: Excat response should be return instead of generic.

"""

from utils.helper import *

class Service(object):

    def __init__(self):
        pass


    def luna_service(self, name, action):
        match name:
            case "dhcpd" | "named":
                match action:
                    case "start" | "stop" | "reload" | "restart" | "status":
                        command = "/usr/bin/systemctl {} {}".format(action, name)
                        output = Helper.runcommand(command)
                        response, code = self.service_status(name, action, output)
                    case _:
                        response = {"error": "Service Action {} is not recognized.".format(action)}
                        code = 400
            case _:
                response = {"error": "Service Name {} is not recognized.".format(name)}
                code = 400
        return response, code

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
