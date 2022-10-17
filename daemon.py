#!/usr/bin/python

"""
EXTRA TIME ACTIVITY
Strategy Of this file is required, Because...
1. None of the Microservice Application supports Boilerplate Arguments on Prodcution. TODO Point 6
2. Will provide easy access to manage the application.
TODO :: Responsible for
1. Start/Stop/Restart/Reload of Luna 2 Daemon Rest API
2. Sanity Checks before Starting the application
3. Bootstrapping Of Application
4. Run Application on Production Mode via gunicorn or any other WSGI
5. CLI Utility to make changes on RunTime.
6. Support Argument Parser for --ini and --debug and others(In Future use)
7. Setup the Application and related files and directories.
8. Create, enable and start the Systemd service for luna2 daemon
"""

import sys
import os
from colorama import init
init(strip=not sys.stdout.isatty())
from termcolor import cprint
import pyfiglet
from argparse import ArgumentParser
import subprocess
import logging
from configparser import RawConfigParser
from pathlib import Path

CurrentDir = os.path.dirname(os.path.realpath(__file__))
UTILSDIR = Path(CurrentDir)
BASE_DIR = str(UTILSDIR.parent)
configParser = RawConfigParser()
ConfigFile = "/trinity/local/luna/config/luna.ini"

global CONSTANT

CONSTANT = {
    "CONNECTION": { "SERVERIP": None, "SERVERPORT": None },
    "LOGGER": { "LEVEL": None, "LOGFILE": None },
    "API": { "USERNAME": None, "PASSWORD": None, "EXPIRY": None },
    "DATABASE": { "DRIVER": None, "DATABASE": None, "DBUSER": None, "DBPASSWORD": None, "HOST": None, "PORT": None },
    "FILES": { "TARBALL": None },
    "SERVICES": { "DHCP": None, "DNS": None, "CONTROL": None, "COOLDOWN": None, "COMMAND": None },
    "TEMPLATES": { "TEMPLATES_DIR": None }
}


def banner():
    MainBanner = "ClusterVision  "
    banner = pyfiglet.figlet_format(MainBanner, font="standard", justify="center")
    cprint(banner, 'blue', 'on_grey', attrs=['bold'])
    BannerDef = "Luna 2.0 Daemon"
    banner = pyfiglet.figlet_format(BannerDef, font="digital", justify="center")
    cprint(banner, 'green', 'on_grey', attrs=['bold'])


def daemon():
    parser = ArgumentParser(prog='luna2-daemon', description='Manage Luna2 Daemon')
    subparsers = parser.add_subparsers(dest="command", help='See Details by --help')
    parserSetup = subparsers.add_parser('setup', help='Setup Application')
    parserCleanup = subparsers.add_parser('cleanup', help='Setup Application')
    parserStart = subparsers.add_parser('start', help='Run Application')
    parserStop = subparsers.add_parser('stop', help='Stop Application')
    parserReload = subparsers.add_parser('reload', help='Reload Configurations')
    parserRestart = subparsers.add_parser('restart', help='Restart Application')
    parserStatus = subparsers.add_parser('status', help='Status Of Application')
    # parser.add_argument("-d", "--debug", action="store_true", help='Run Application on Debug Mode.')
    parser.add_argument("-d", "--debug", action="store_true", help='Run Application on Debug Mode.')
    parser.add_argument("-i", "--ini", default="/trinity/local/luna/config/luna.ini", help='Overright the Default Configuration.')
    args = vars(parser.parse_args())
    override = None
    if args["ini"]:
        override = args["ini"]
    if args["command"] == "start":
        updateconfig(args)
        start()
    if args["command"] == "stop":
        stop()
    return args

"""
Initial Setup - Systemd Servce, Cron Job, Database
"""
def setup():
    pass
    ## Copy Cron Job
    ## Create Systemd Service
    ##

"""
Truncate The Complete Application, Need Username & Password from Default INI File
"""
def cleanup():
    pass

"""
Start systemd service
"""
def start():
    processes = check_run()
    if processes:
        print("luna2-daemon Is Already Running.")
    else:
        command = "gunicorn -w 4 -b {}:{} --log-file ./log/gunicorn.log --log-level {} --access-logfile ./log/gunicorn-access.log --error-logfile ./log/gunicorn-error.log 'luna:api' &".format(SERVERIP, SERVERPORT, LEVEL)
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        print("luna2-daemon Is Started Now.")
    return True

    pass
    ## systemctl start luna2-daemon

"""
Stop systemd service
"""
def check_run():
    command = "lsof -i -P -n | grep LISTEN | grep 7050 | cut -d ' ' -f3"
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output = process.communicate()
    output = str(output).replace("', b'')", "")
    output = output.replace("b'", "")
    output = output.replace("(", "")
    output = output.split("\\n")
    output = [i for i in output if i]
    return output

"""
Stop systemd service
"""
def stop():
    processes = check_run()
    if processes:
        for x in processes:
            command = "kill -9 {}".format(str(x))
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            processes = process.communicate()
        print("luna2-daemon Is Stopped Now.")
    else:
        print("luna2-daemon Is Already Stopped.")
    ## systemctl stop luna2-daemon

"""
Reload systemd service
"""
def reload():
    pass
    ## systemctl reload luna2-daemon

"""
Restart systemd service
"""
def restart():
    pass
    ## systemctl restart luna2-daemon

"""
Get Status from systemd service
"""
def status():
    pass
    ## systemctl status luna2-daemon


def checksection():
    for item in list(CONSTANT.keys()):
        if item not in configParser.sections():
            print("ERROR :: Section {} Is Missing, Kindly Check The File {}.".format(item, filename))
            sys.exit(0)


def checkoption(each_section):
    for item in list(CONSTANT[each_section].keys()):
        if item.lower() not in list(dict(configParser.items(each_section)).keys()):
            print("ERROR :: Section {} Don't Have Option {}, Kindly Check The File {}.".format(each_section, each_key.upper(), filename))
            sys.exit(0)

def getconfig(filename=None):
    configParser.read(filename)
    checksection()
    for each_section in configParser.sections():
        for (each_key, each_val) in configParser.items(each_section):
            globals()[each_key.upper()] = each_val
            if each_section in list(CONSTANT.keys()):
                checkoption(each_section)
                CONSTANT[each_section][each_key.upper()] = each_val
            else:
                CONSTANT[each_section] = {}
                CONSTANT[each_section][each_key.upper()] = each_val


def updateconfig(args):
    file_check = checkfile(ConfigFile)
    if file_check:
        getconfig(ConfigFile)
    else:
        sys.exit(0)

    if args["ini"]:
        file_check_override = checkfile(args["ini"])
        if file_check_override:
            getconfig(args["ini"])

    # if EXPIRY:
    #     EXPIRY = int(EXPIRY.replace("h", ""))
    #     EXPIRY = EXPIRY*60*60
    # else:
    #     EXPIRY = 24*60*60
    # sys.exit(0)

    # if COOLDOWN:
    #     COOLDOWN = int(COOLDOWN.replace("s", ""))
    # else:
    #     COOLDOWN = 2

    if args["debug"]:
        LEVEL = "debug"

"""
Input - Filename
Output - Check File Existence And Readability
"""
def checkfile(filename=None):
    ConfigFilePath = Path(filename)
    if ConfigFilePath.is_file():
        if os.access(filename, os.R_OK):
            return True
        else:
            print("File {} Is Not readable.".format(filename))
    else:
        print("File {} Is Abesnt.".format(filename))
    return False


if __name__ == "__main__":
    banner()
    response = daemon()
    # response = lunacli()
    print(response)
