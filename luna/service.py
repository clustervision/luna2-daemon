#!/usr/bin/env python3

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Production"

"""

"""
import os
import configparser
from pathlib import Path

from luna.utils.helper import *
import logging

class Service(object):

    def __init__(self, params):
        self.base_dir = params.base_dir
        self.args = params.args
        self.logger = params.logger
        self.CONFIGFILE = params.CONFIGFILE

        match self.args["action"]:
            case "start" | "stop" | "reload" | "restart" | "enable" | "disable" | "status" | "isactive" | "isenabled" | "isfailed":
                self.service_action(self.args)
            case "add":
                self.service_add(self.args)
            case "rename":
                self.service_rename(self.args)
            case "remove":
                self.service_remove(self.args)
            case "showall":
                self.service_showall(self.args)
            case _:
                self.logger.error("No Action Matched.")


    def getarguments(self, parser, subparsers):
        ServiceMenu = subparsers.add_parser('service', help='Setup Luna Application.')
        ServiceArgs = ServiceMenu.add_subparsers(dest='action')

        cmd = ServiceArgs.add_parser('add', help='Add New Service To Manage.')
        cmd.add_argument('--name', '-n', help='Actuall Name Of Service.')
        cmd = ServiceArgs.add_parser('rename', help='Rename A Managed Service.')
        cmd.add_argument('--name', '-n', help='Actuall Name Of Service.')
        cmd.add_argument('--newname', '-nw', help='Actuall Name Of Service.')
        cmd = ServiceArgs.add_parser('remove', help='Remove A Managed Service..')
        cmd.add_argument('--name', '-n', help='Actuall Name Of Service.')
        cmd = ServiceArgs.add_parser('showall', help='Show All Managed Services By Luna.')
        cmd.add_argument('--json', '-j', action='store_true', help='JSON output')

        ###=========>> Method 1: To Show All Actions then Services

        if self.SERVICES:
            self.SERVICES = self.SERVICES.replace(" ", "")
            self.SERVICES = self.SERVICES.split(",")

            servicestart = ServiceArgs.add_parser('start', help='Start A Service.')
            servicestartArgs = servicestart.add_subparsers(dest="service")
            servicestop = ServiceArgs.add_parser('stop', help='Stop A Service.')
            servicestopArgs = servicestop.add_subparsers(dest="service")
            servicereload = ServiceArgs.add_parser('reload', help='Reload Only Configuration Of A Service.')
            servicereloadArgs = servicereload.add_subparsers(dest="service")            
            servicerestart = ServiceArgs.add_parser('restart', help='Restart A Service.')
            servicerestartArgs = servicerestart.add_subparsers(dest="service")            
            serviceenable = ServiceArgs.add_parser('enable', help='Start A Service At Boot.')
            serviceenableArgs = serviceenable.add_subparsers(dest="service")
            servicedisable = ServiceArgs.add_parser('disable', help='Disable A Service From Starting Automatically.')
            servicedisableArgs = servicedisable.add_subparsers(dest="service")
            servicestatus = ServiceArgs.add_parser('status', help='Check The Status Of A Service.')
            servicestatusArgs = servicestatus.add_subparsers(dest="service")
            serviceisactive = ServiceArgs.add_parser('isactive', help='Check If A Serive Is Currently Active')
            serviceisactiveArgs = serviceisactive.add_subparsers(dest="service")
            serviceisenabled = ServiceArgs.add_parser('isenabled', help='Check If A Serive Is Enabled.')
            serviceisenabledArgs = serviceisenabled.add_subparsers(dest="service")
            serviceisfailed = ServiceArgs.add_parser('isfailed', help='Check If A Status Is Failed.')
            serviceisfailedArgs = serviceisfailed.add_subparsers(dest="service")

            for serviceX in self.SERVICES:
                serviceXcmd = servicestartArgs.add_parser(serviceX, help='Start {} Service.'.format(serviceX))
                serviceXcmd = servicestopArgs.add_parser(serviceX, help='Stop {} Service.'.format(serviceX))
                serviceXcmd = servicereloadArgs.add_parser(serviceX, help='Reload {} Service.'.format(serviceX))
                serviceXcmd = servicerestartArgs.add_parser(serviceX, help='Restart {} Service.'.format(serviceX))
                serviceXcmd = serviceenableArgs.add_parser(serviceX, help='Start {} Service At Boot.'.format(serviceX))
                serviceXcmd = servicedisableArgs.add_parser(serviceX, help='Disable {} ServiceFrom Starting Automatically.'.format(serviceX))
                serviceXcmd = servicestatusArgs.add_parser(serviceX, help='Check Status Of {} Service.'.format(serviceX))
                serviceXcmd = serviceisactiveArgs.add_parser(serviceX, help='Check If {} Serive Is Currently Active.'.format(serviceX))
                serviceXcmd = serviceisenabledArgs.add_parser(serviceX, help='Check If {} Serive Is Enabled.'.format(serviceX))
                serviceXcmd = serviceisfailedArgs.add_parser(serviceX, help='Check If {} Status Is Failed.'.format(serviceX))


        ###=========>> Method 2: To Show Services And then All Actions

        # if self.SERVICES:
        #     self.SERVICES = self.SERVICES.replace(" ", "")
        #     self.SERVICES = self.SERVICES.split(",")

        #     for serviceX in self.SERVICES:
        #         serviceXcmd = ServiceArgs.add_parser(serviceX, help='Manage {} Service.'.format(serviceX.capitalize()))
        #         XArgs = serviceXcmd.add_subparsers(dest="action")
        #         cmd = XArgs.add_parser('start', help='Start {} Service.'.format(serviceX))
        #         cmd = XArgs.add_parser('stop', help='Stop {} Service.'.format(serviceX))
        #         cmd = XArgs.add_parser('reload', help='Reload Configuration Only Of {} Service.'.format(serviceX))
        #         cmd = XArgs.add_parser('restart', help='Restart {} Service.'.format(serviceX))
        #         cmd = XArgs.add_parser('enable', help='Start {} Service At Boot.'.format(serviceX))
        #         cmd = XArgs.add_parser('disable', help='Disable {} Service From Starting Automatically.'.format(serviceX))
        #         cmd = XArgs.add_parser('status', help='Check The Status Of {} Service.'.format(serviceX))
        #         cmd = XArgs.add_parser('isactive', help='Check If {} Serive Is Currently Active.'.format(serviceX))
        #         cmd = XArgs.add_parser('isenabled', help='Check If {} Serive Is Enabled.'.format(serviceX))
        #         cmd = XArgs.add_parser('isfailed', help='Check If {} Status Is Failed.'.format(serviceX))
        else:
            self.logger.warning("No Services are defined to Use. Kindly define the services to use.")
        return parser

    def service_action(self, args=None):
        result = ""
        match self.args["action"]:
            case "isactive":
                self.args["action"] = "is-active"
            case "isenabled":
                self.args["action"] = "is-enabled"
            case "isfailed":
                self.args["action"] = "is-failed"
        command = "/usr/bin/systemctl {} {}".format(self.args["action"], self.args["service"])
        output = Helper.runcommand(self, command)
        match self.args["action"]:
            case "start":
                if "(b'', b'')" in str(output):
                    result = "Service {} is {}ed.".format(self.args["service"], self.args["action"])
                else:
                    result = "Service {} is Failed to {}.".format(self.args["service"], self.args["action"])
            case "stop":
                if "(b'', b'')" in str(output):
                    result = "Service {} is {}ped.".format(self.args["service"], self.args["action"])
                else:
                    result = "Service {} is Failed to {}.".format(self.args["service"], self.args["action"])
            case "status":
                if "active (running)" in str(output):
                    result = "Service {} is Active & Running.".format(self.args["service"])
                else:
                    result = "Service {} is Not Active & Running.".format(self.args["service"])
            case "reload":
                if "Failed" in str(output):
                    result = "Service {} is Failed to {}.".format(self.args["service"], self.args["action"])
                else:
                    result = "Service {} is {}ed.".format(self.args["service"], self.args["action"])
            case "restart":
                if "(b'', b'')" in str(output):
                    result = "Service {} is {}ed.".format(self.args["service"], self.args["action"])
                else:
                    result = "Service {} is Failed to {}.".format(self.args["service"], self.args["action"])
            case "enable":
                if "(b'', b'')" in str(output) or "Created symlink" in str(output):
                    result = "Service {} is {}d.".format(self.args["service"], self.args["action"])
                else:
                    result = "Service {} is Failed to {}.".format(self.args["service"], self.args["action"])
            case "disable":
                if "(b'', b'')" in str(output) or "Removed" in str(output):
                    result = "Service {} is {}d.".format(self.args["service"], self.args["action"])
                else:
                    result = "Service {} is Failed to {}.".format(self.args["service"], self.args["action"])
            case "is-active":
                if "(b'active\\n', b'')" in str(output):
                    result = "Service {} is active.".format(self.args["service"])
                else:
                    result = "Service {} is Not active".format(self.args["service"])
            case "is-enabled":
                if "(b'enabled\\n', b'')" in str(output):
                    result = "Service {} is Enabled.".format(self.args["service"])
                else:
                    result = "Service {} is Not Enabled".format(self.args["service"])
            case "is-failed":
                if "(b'active\\n', b'')" in str(output):
                    result = "Service {} is Active.".format(self.args["service"])
                elif "(b'inactive\\n', b'')" in str(output):
                    result = "Service {} is InActive.".format(self.args["service"])
                else:
                    result = "Service {} is Failed".format(self.args["service"])
        return result


    def service_add(self, args=None):
        configParser = configparser.RawConfigParser()
        configParser.read(self.CONFIGFILE)
        try:
            self.SERVICES = configParser.get("SERVICES", "service")
            self.SERVICES = self.SERVICES.replace(" ", "")
            self.SERVICES = self.SERVICES.split(",")
        except Exception as e:
            self.SERVICES = []
            self.logger.warning("No Services are defined to Use. Kindly define the services to use.")
        
        if self.args["name"]:
            if self.args["name"] not in self.SERVICES: 
                self.SERVICES.append(self.args["name"])
                self.SERVICES = ",".join(self.SERVICES)
                with open(self.CONFIGFILE) as file:
                    newText = file.read().replace('service = '+str(configParser.get("SERVICES", "service")), 'service = '+str(self.SERVICES))
                with open(self.CONFIGFILE, "w") as file:
                    file.write(newText)
                self.logger.info("Service {} added successfully .".format(self.args["name"]))
            else:
                self.logger.warning("Service {} already added.".format(self.args["name"]))
        return True


    def service_rename(self, args=None):
        configParser = configparser.RawConfigParser()
        configParser.read(self.CONFIGFILE)
        try:
            self.SERVICES = configParser.get("SERVICES", "service")
            self.SERVICES = self.SERVICES.replace(" ", "")
            self.SERVICES = self.SERVICES.split(",")
        except Exception as e:
            self.SERVICES = []
            self.logger.warning("No Services are defined to Use. Kindly define the services to use.")
        
        if self.args["name"] in self.SERVICES:
            if self.args["newname"] not in self.SERVICES: 
                self.SERVICES.remove(self.args["name"])
                self.SERVICES.append(self.args["newname"])
                self.SERVICES = ",".join(self.SERVICES)
                with open(self.CONFIGFILE) as file:
                    newText = file.read().replace('service = '+str(configParser.get("SERVICES", "service")), 'service = '+str(self.SERVICES))
                with open(self.CONFIGFILE, "w") as file:
                    file.write(newText)
                self.logger.info("Service {} updated successfully.".format(self.args["name"]))
            else:
                self.logger.warning("Service {} already updated.".format(self.args["name"]))
        else:
            self.logger.error("Service {} is not in the list.".format(self.args["name"]))
        return True


    def service_remove(self, args=None):
        configParser = configparser.RawConfigParser()
        configParser.read(self.CONFIGFILE)
        try:
            self.SERVICES = configParser.get("SERVICES", "service")
            self.SERVICES = self.SERVICES.replace(" ", "")
            self.SERVICES = self.SERVICES.split(",")
        except Exception as e:
            self.SERVICES = []
            self.logger.warning("No Services are defined to Use. Kindly define the services to use.")
        
        if self.args["name"]:
            if self.args["name"] not in self.SERVICES: 
                self.SERVICES.remove(self.args["name"])
                self.SERVICES = ",".join(self.SERVICES)
                with open(self.CONFIGFILE) as file:
                    newText = file.read().replace('service = '+str(configParser.get("SERVICES", "service")), 'service = '+str(self.SERVICES))
                with open(self.CONFIGFILE, "w") as file:
                    file.write(newText)
                self.logger.info("Service {} removed successfully .".format(self.args["name"]))
            else:
                self.logger.warning("Service {} Not exists in the list.".format(self.args["name"]))
        return True


    def service_showall(self, args=None):
        configParser = configparser.RawConfigParser()
        configParser.read(self.CONFIGFILE)
        try:
            self.SERVICES = configParser.get("SERVICES", "service")
            self.SERVICES = self.SERVICES.replace(" ", "")
            self.SERVICES = self.SERVICES.split(",")
        except Exception as e:
            self.SERVICES = []
            self.logger.warning("No Services are defined to Use. Kindly define the services to use.")
        if not self.args["json"]:
            output = Helper.printlist(self, self.SERVICES)
            print(output)       
        else:
            Helper.printjson(self, self.SERVICES)
        return True
