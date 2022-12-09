#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This Is a Helper Class, which help the project to provide the common Methods.

"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

import os
import sys
import pwd
import subprocess
import shutil
import queue
from jinja2 import Environment
from utils.log import Log
import json
import ipaddress
from utils.database import Database
from netaddr import IPNetwork
from cryptography.fernet import Fernet
from common.constant import CONSTANT, LUNAKEY

class Helper(object):
    """
    All kind of helper methods.
    """

    def __init__(self):
        """
        Constructor - As of now, nothing have to initialize.
        """
        self.logger = Log.get_logger()
        self.packing = queue.Queue()


    def runcommand(self, command):
        """
        Input - command, which need to be executed
        Process - Via subprocess, execute the command and wait to receive the complete output.
        Output - Detailed result.
        """
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        self.logger.debug(f'Command Executed {command}')
        output = process.communicate()
        process.wait()
        self.logger.debug(f'Output Of Command {output}')
        return output


    def stop(self, message=None):
        """
        Input - Error Message (String)
        Output - Stop The Daemon With Error Message .
        """
        self.logger.error(f'Daemon Stopped Because: {message}')
        sys.exit(-1)
        return False


    def checkpathstate(self, path=None):
        """
        Input - Directory
        Output - Directory if exists, readable or writable
        """
        pathtype = self.checkpathtype(path)
        if pathtype == 'File' or pathtype == 'Directory':
            if os.access(path, os.R_OK):
                if os.access(path, os.W_OK):
                    return True
                else:
                    print(f'{pathtype} {path} is writable.')
            else:
                print(f'{pathtype} {path} is not readable.')
        else:
            print(f'{pathtype} {path} is not exists.')
        return False


    def checkpathtype(self, path=None):
        """
        Input - Path of File or Directory
        Output - File or directory or Not Exists
        """
        pathstatus = self.checkpath(path)
        if pathstatus:
            if os.path.isdir(path):
                response = 'File'
            elif os.path.isfile(path):
                response = 'Directory'
            else:
                response = 'socket or FIFO or device'
        else:
            response = 'Not exists'
        return response


    def checkpath(self, path=None):
        """
        Input - Path of File or Directory
        Output - True or False Is exists or not
        """
        if os.path.exists(path):
            response = True
        else:
            response = None
        return response


    def checkjinja(self, template=None):
        """
        Input - Path of Template
        Output - True or False For Errors
        """
        check = False
        env = Environment()
        try:
            with open(template, encoding='utf-8') as template:
                env.parse(template.read())
            check = True
        except Exception as exp:
            print(f'{template} Have Errors.')
            print(exp)
        return check


    def check_json(self, request=None):
        """
        Input - JSON
        Output - True or False For Errors
        Usecase - switchcolumn = Database().get_columns('switch')
        """
        try:
            json.loads(request)
        except Exception as e:
            return False
        return True


    def checkin_list(self, list1=None, list2=None):
        """
        Input - TWO LISTS
        Output - True or False For Errors
        """
        CHECK = True
        for ITEM in list1:
            if ITEM not in list2:
                CHECK = False
        return CHECK


    def check_ip(self, ipaddr=None):
        """
        Add blacklist filter;
        https://clustervision.atlassian.net/wiki/spaces/TRIX/pages/52461574/2022-11-11+Development+meeting
        """
        IP = ''
        try:
            ip = IPNetwork(ipaddr)
            IP = ip.ip
            # IP = ipaddress.ip_address(net)
        except Exception as e:
            return None
        return str(IP)


    def get_network(self, ipaddr=None, subnet=None):
        """
        Input - IP Address + Subnet
        Output - Network such as 10.141.0.0/16
        """
        if subnet:
            net = ipaddress.ip_network(ipaddr+'/'+subnet, strict=False)
        else:
            net = ipaddress.ip_network(ipaddr, strict=False)
        return str(net)


    def get_network_details(self, ipaddr=None):
        """
        Input - IP Address such as 10.141.0.0/16
        Output - Network and Subnet such as 10.141.0.0 and 255.255.0.0
        """
        RESPONSE = {}
        try:
            net = ipaddress.ip_network(ipaddr, strict=False)
            RESPONSE['network'] = str(net)
            RESPONSE['subnet'] = str(net.netmask)
        except Exception as e:
            return None
        return RESPONSE


    def get_subnet(self, ipaddr=None):
        """
        Input - IP Address
        Output - Subnet
        """
        net = ipaddress.ip_network(ipaddr, strict=False)
        return net.netmask


    def check_ip_range(self, ipaddr=None, network=None):
        """
        Check If IP is in range or not
        """
        RESPONSE = False
        try:
            CHECKIP = self.check_ip(ipaddr)
            if CHECKIP:
                if ipaddress.ip_address(ipaddr) in list(ipaddress.ip_network(network).hosts()):
                    RESPONSE = True
                else:
                    RESPONSE = False
            else:
                RESPONSE = False
        except Exception as e:
            RESPONSE = False
        return RESPONSE


    def check_ip_exist(self, DATA=None):
        """
        check if IP is valid or not
        check if IP address is in database or not True false
        """
        if 'ipaddress' in DATA:
            CHECKIP = self.check_ip(DATA['ipaddress'])
            if not CHECKIP:
                return None
            IPRECORD = Database().get_record(None, 'ipaddress', ' WHERE `ipaddress` = "{}";'.format(DATA['ipaddress']))
            if IPRECORD:
                return None
            else:
                SUBNET = self.get_subnet(DATA['ipaddress'])
                row = [
                        {"column": 'ipaddress', "value": DATA['ipaddress']},
                        {"column": 'network', "value": DATA['network']},
                        {"column": 'subnet', "value": SUBNET}
                        ]
                result = Database().insert('ipaddress', row)
                SUBNETRECORD = Database().get_record(None, 'ipaddress', ' WHERE `ipaddress` = "{}";'.format(DATA['ipaddress']))
                DATA['ipaddress'] = SUBNETRECORD[0]['id']
        return DATA

    def make_rows(self, data=None):
        """
        Input - IP Address
        Output - Subnet
        """
        row = []
        for KEY, VALUE in data.items():
            row.append({"column": KEY, "value": VALUE})
        return row


    def bool_revert(self, variable=None):
        """
        Input - string
        Output - Boolean
        """
        if type(variable) == bool:
            if variable == True:
                variable = '1'
            elif variable == False:
                variable = '0'
        elif type(variable) == str  or type(variable) == int:
            if variable == '1' or variable == 1:
                variable = True
            elif variable == '0' or variable == 0:
                variable = False
        else:
            variable = None
        return variable

    def encrypt_string(self, string=None):
        """
        Input - string
        Output - Encrypt String
        """
        KEY = bytes(LUNAKEY, 'utf-8')
        FERNETOBJ = Fernet(KEY)
        RESPONSE = FERNETOBJ.encrypt(string.encode()).decode()
        return RESPONSE


    def decrypt_string(self, string=None):
        """
        Input - string
        Output - Decrypt Encoded String
        """
        KEY = bytes(LUNAKEY, 'utf-8')
        FERNETOBJ = Fernet(KEY)
        RESPONSE = FERNETOBJ.decrypt(string).decode()
        return RESPONSE


    def pack(self, image=None):
        if {"packing": image} in self.packing.queue:
            self.logger.warning(f'Image {image} packing is ongoing, request is in Queue.')
            response = f'Image {image} packing is ongoing, request is in Queue.'
        else:
            self.packing.put({"packing": image})
            response = self.packimage(image)
            self.logger.info(response)
        return response


    def packimage(self, image=None):
        """
        Input - OS Image Name (string)
        Output - Success/Failure (Boolean)
        """
        def mount(source, target, fs):
            subprocess.Popen(['/usr/bin/mount', '-t', fs, source, target])

        def umount(source):
            subprocess.Popen(['/usr/bin/umount', source])

        def prepare_mounts(path):
            mount('devtmpfs', path + '/dev', 'devtmpfs')
            mount('proc', path + '/proc', 'proc')
            mount('sysfs', path + '/sys', 'sysfs')

        def cleanup_mounts(path):
            umount(path + '/dev')
            umount(path + '/proc')
            umount(path + '/sys')

        IMAGE = Database().get_record(None, 'osimage', f' WHERE name = "{image}"')
        if IMAGE:
            PATHTMP = '/tmp'
            IMAGENAME = IMAGE[0]['name']
            IMAGEPATH = IMAGE[0]['path']
            DRACUTMODULES = IMAGE[0]['dracutmodules']
            KERNELMODULES = IMAGE[0]['kernelmodules']
            KERNELVERSION = IMAGE[0]['kernelversion']
            OSKERNELVERSION = self.runcommand('uname -r')
            OSKERNELVERSION = str(OSKERNELVERSION[0])
            OSKERNELVERSION = OSKERNELVERSION.replace("b'", '')
            OSKERNELVERSION = OSKERNELVERSION.replace("\\n'", '')

            if OSKERNELVERSION != KERNELVERSION:
                self.logger.error(f'OS Kernel Version {OSKERNELVERSION} is not matching with the image kernel version {KERNELVERSION}.')
                return False

            KERNELFILE = image+'-vmlinuz-'+KERNELVERSION
            INTRDFILE = image+'-initramfs-'+KERNELVERSION

            PATH = IMAGEPATH
            CLUSTER = Database().get_record(None, 'cluster', None)
            if CLUSTER:
                USER = CLUSTER[0]['user']
            else:
                USER = 'luna'
            PATHTOSTORE = CONSTANT['FILES']['TARBALL']
            USERID = pwd.getpwnam(USER).pw_uid
            GROUPID = pwd.getpwnam(USER).pw_gid

            if not os.path.exists(PATHTOSTORE):
                os.makedirs(PATHTOSTORE)
                os.chown(PATHTOSTORE, USERID, GROUPID)

            MODULESADD, MODULESREMOVE, DRIVERSADD, DRIVERSREMOVE = [], [], [], []

            if DRACUTMODULES:
                for i in DRACUTMODULES.split(','):
                    if i[0] != '-':
                        MODULESADD.extend(['--add', i])
                    else:
                        MODULESREMOVE.extend(['--omit', i[1:]])
            if KERNELMODULES:
                for i in KERNELMODULES.split(','):
                    if i[0] != '-':
                        DRIVERSADD.extend(['--add-drivers', i])
                    else:
                        DRIVERSREMOVE.extend(['--omit-drivers', i[1:]])

            prepare_mounts(IMAGEPATH)
            REALROOT = os.open("/", os.O_RDONLY)
            os.chroot(IMAGEPATH)
            CHROOTPATH = os.open("/", os.O_DIRECTORY)
            os.fchdir(CHROOTPATH)
            DRACUTSUCCEED = True
            CREATE = None

            try:
                DRACUTPROCESS = subprocess.check_output(['/usr/sbin/dracut', '--kver', KERNELVERSION, '--list-modules'], universal_newlines=True)
                self.logger.info(f'DRACUTPROCESS ==> {DRACUTPROCESS}.')
                DRACUTCMDPROCESS = (['/usr/sbin/dracut', '--force', '--kver', KERNELVERSION] + MODULESADD + MODULESREMOVE + DRIVERSADD + DRIVERSREMOVE + [PATHTMP + '/' + INTRDFILE])
                CREATE = subprocess.check_output(DRACUTCMDPROCESS, timeout=CONSTANT['FILES']['MAXPACKAGINGTIME'], universal_newlines=True)
                self.logger.info(f'CREATE ==> {CREATE}.')
            except Exception as exp:
                self.logger.error(f'Exception ==> {exp}.')
                DRACUTSUCCEED = False

            ################### OLD CODE ########################
            # # ## Nested, time count ; should be 10 minutes
            # try:
            #     DRACUTPROCESS = subprocess.Popen(['/usr/sbin/dracut', '--kver', KERNELVERSION, '--list-modules'], stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            #     LUNAEXISTS = False
            #     while DRACUTPROCESS.poll() is None:
            #         ### Remove, only check only if process is running
            #         line = DRACUTPROCESS.stdout.readline()
            #         if line.strip() == 'luna':
            #             LUNAEXISTS = True
            #             break
            #         ### Remove, only check only if process is running
            #     # if not LUNAEXISTS:
            #     #     self.logger.error(f'No luna dracut module in OS Image {IMAGENAME}.')
            #     #     raise RuntimeError(f'No luna dracut module in OS Image {IMAGENAME}.')

            #     DRACUTCMDPROCESS = (['/usr/sbin/dracut', '--force', '--kver', KERNELVERSION] + MODULESADD + MODULESREMOVE + DRIVERSADD + DRIVERSREMOVE + [PATHTMP + '/' + INTRDFILE])
            #     CREATE = subprocess.Popen(DRACUTCMDPROCESS, stdout=subprocess.PIPE)
            #     while CREATE.poll() is None:
            #         line = CREATE.stdout.readline()
            # except Exception as exp:
            #     print(exp)
            #     DRACUTSUCCEED = False
            # #  ## Nested, time count ; should be 10 minutes

            # if CREATE and CREATE.returncode:
            #     DRACUTSUCCEED = False

            # if not CREATE:
            #     DRACUTSUCCEED = False
            ################### OLD CODE ########################

            os.fchdir(REALROOT)
            os.chroot(".")
            os.close(REALROOT)
            os.close(CHROOTPATH)
            cleanup_mounts(IMAGEPATH)

            if not DRACUTSUCCEED:
                self.logger.error(f'Error while building initrd for OS Image {IMAGENAME}.')
                return False

            INTRDPATH = IMAGEPATH + PATHTMP + '/' + INTRDFILE
            KERNELPATH = IMAGEPATH + '/boot/vmlinuz-' + KERNELVERSION

            if not os.path.isfile(KERNELPATH):
                self.logger.error(f'Unable to find kernel in {KERNELPATH}.')
                return False

            if not os.path.isfile(INTRDPATH):
                self.logger.error(f'Unable to find initrd in {INTRDPATH}.')
                return False

            # copy initrd file to inherit perms from parent folder
            shutil.copy(INTRDPATH, PATHTOSTORE + '/' + INTRDFILE)
            os.remove(INTRDPATH)
            shutil.copy(KERNELPATH, PATHTOSTORE + '/' + KERNELFILE)
            os.chown(PATHTOSTORE + '/' + INTRDFILE, USERID, GROUPID)
            os.chmod(PATHTOSTORE + '/' + INTRDFILE, int('0644'))
            os.chown(PATHTOSTORE + '/' + KERNELFILE, USERID, GROUPID)
            os.chmod(PATHTOSTORE + '/' + KERNELFILE, int('0644'))
            self.packing.get() ## Get the Last same Element from Queue
            self.packing.empty() ## Deque the same element from the Queue
        return True
