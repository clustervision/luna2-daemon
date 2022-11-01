#!/usr/bin/env python3

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

"""
This Is a Template Class.
It will help to validate the templates.
It will responsible to create the tmp dir for templates
"""
import os
import json
import subprocess
from utils.log import *
from utils.helper import Helper


class Templates(object):


    """
    Constructor - As of now, nothing have to initialize.
    """
    def __init__(self):
        self.logger = Log.get_logger()


    """
    Input - command, which need to be executed
    Process - Via subprocess, execute the command and wait to receive the complete output.
    Output - Detailed result.
    """
    def validate(self):
        if CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]:
            TEMPLATEDIR = CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]
        if TEMPLATEDIR:
            dirstatus = self.checkdir(TEMPLATEDIR)
        if CONSTANT["TEMPLATES"]["TEMPLATELIST"]:
            TEMPLATELIST = CONSTANT["TEMPLATES"]["TEMPLATELIST"]
        if TEMPLATELIST:
            tempdirstatus = self.checkdir(TEMPLATELIST)
        if tempdirstatus:
            file = open(TEMPLATELIST)
            data = json.load(file)
            file.close()
            if data:
                if 'files' in data.keys():
                    Helper().runcommand(f'rm -rf /var/tmp/luna2')
                    Helper().runcommand(f'mkdir /var/tmp/luna2')
                    for templatefiles in data['files']:
                        tempdirstatus = self.checkdir(TEMPLATELIST)
                        if tempdirstatus:
                            Helper().runcommand(f'cp {CONSTANT["TEMPLATES"]["TEMPLATES_DIR"]}/{templatefiles} /var/tmp/luna2/')


    """
    Input - Directory
    Output - Directory Existence, Readability and Writable
    """
    def checkdir(self, directory=None):
        if os.path.exists(directory):
            if os.access(directory, os.R_OK):
                if os.access(directory, os.W_OK):
                    return True
                else:
                    print('Directory {} Is Writable.'.format(directory))
            else:
                print('Directory {} Is Not readable.'.format(directory))
        else:
            print('Directory {} Is Not exists.'.format(directory))
        return False


    def checkfile(filename=None):
        ConfigFilePath = Path(filename)
        if ConfigFilePath.is_file():
            if os.access(filename, os.R_OK):
                return True
            else:
                print('File {} Is Not readable.'.format(filename))
        else:
            print('File {} Is Abesnt.'.format(filename))
        return False

    def checkwritable(filename=None):
        write = False
        try:
            file = open(filename, 'a')
            if file.writable():
                write = True
        except Exception as e:
            print('File {} is Not Writable.'.format(filename))
        return write


        #  check_dir_read = checkdir(TEMPLATES_DIR)
        # if check_dir_read is not True:
        #     print('TEMPLATES_DIR Directory: {} Is Not Readable.'.format(TEMPLATES_DIR))
        #     sys.exit(0)

        # check_dir_write = checkdir(TEMPLATES_DIR)
        # if check_dir_write is not True:
        #     print('TEMPLATES_DIR Directory: {} Is Not Writable.'.format(TEMPLATES_DIR))
        #     sys.exit(0)

        # check_boot_ipxe_read = checkfile(TEMPLATES_DIR+'/boot_ipxe.cfg')
        # if check_boot_ipxe_read is not True:
        #     print('Boot PXE File: {} Is Not Readable.'.format(TEMPLATES_DIR+'/boot_ipxe.cfg'))
        #     sys.exit(0)

        # check_boot_ipxe_write = checkwritable(TEMPLATES_DIR+'/boot_ipxe.cfg')
        # if check_boot_ipxe_write is not True:
        #     print('Boot PXE File: {} Is Not Writable.'.format(TEMPLATES_DIR+'/boot_ipxe.cfg'))
        #     sys.exit(0)

        # if check_boot_ipxe_read and check_boot_ipxe_write:
        #     with open(TEMPLATES_DIR+'/boot_ipxe.cfg', 'r') as bootfile:
        #         bootfile = bootfile.readlines()


        print(CONSTANT["TEMPLATES"]["TEMPLATES_DIR"])