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
# import requests
# from dotenv import load_dotenv
import configparser

# load_dotenv('config/.env', override=False)

# token = os.getenv('TOKEN')
# serverip = os.getenv('SERVERIP')
# serverport = os.getenv('RESTSERVERPORT')

# configParser = configparser.RawConfigParser()
# configParser.read('config/config.ini')
# SERVICEFILE = configParser.get("FILES", "service_file") 

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
    command = "gunicorn -w 4 -b 0.0.0.0:7050 --log-file ./log/gunicorn.log --log-level INFO --access-logfile ./log/gunicorn-access.log --error-logfile ./log/gunicorn-error.log 'luna:api' &"
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    pass
    ## systemctl start luna2-daemon

"""
Stop systemd service
"""
def stop():
    command = "lsof -i -P -n | grep LISTEN | grep 7050 | cut -d ' ' -f3"
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output = process.communicate()
    output = str(output).replace("', b'')", "")
    output = output.replace("b'", "")
    output = output.replace("(", "")
    output = output.split("\\n")
    output = [i for i in output if i]
    print(output)
    for x in output:
        command = "kill -9 {}".format(str(x))
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        output = process.communicate()
        print(output) 
    return output
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

"""
Run Shell Command 
"""
def runcommand(command):
    # process = subprocess.Popen(command, shell=True, stdin=None, stdout=None, stderr=None, close_fds=True)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    # logger.debug("Command Executed {}".format(command))
    # output = process.communicate()
    # process.wait()
    # logger.debug("Output Of Command {} ".format(str(output)))
    # return output

"""
Run Sanity Check on Everything from INI File, Bootstrap and Templates
"""
def sanitycheck():
    pass

"""
Navigation from the Start, Reload, and Restart; Check the Debug is True; Run gunicorn with worker and logs level from INI file
"""
def rundaemon():
    command = "gunicorn -w 4 -b 0.0.0.0:7050 --log-file ./log/gunicorn.log --log-level INFO --access-logfile ./log/gunicorn-access.log --error-logfile ./log/gunicorn-error.log 'luna:api' &"
    output = runcommand(command)
    return output
    # pass
    ## Extract IP, Port, Log-level, and Log-file from INI file. 
    ##
    ##
    ## gunicorn -w 4 -b 0.0.0.0:7050 --log-file ./log/gunicorn.log --log-level INFO --access-logfile ./log/gunicorn-access.log --error-logfile ./log/gunicorn-error.log 'luna:api' &


if __name__ == "__main__":
    banner()
    response = daemon()
    # response = lunacli()
    print(response)
