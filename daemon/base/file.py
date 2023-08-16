#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This endpoint is serving files. The location is defined in the configuration file,
see luna2.ini
"""

__author__      = "Sumit Sharma"
__copyright__   = "Copyright 2022, Luna2 Project"
__license__     = "GPL"
__version__     = "2.0"
__maintainer__  = "Sumit Sharma"
__email__       = "sumit.sharma@clustervision.com"
__status__      = "Development"


from json import dumps
import re
import jwt
from flask import send_file
from common.constant import CONSTANT
from utils.log import Log
from utils.files import Files
from utils.database import Database


class File():
    """
    This class is responsible to provide files.
    """

    def __init__(self):
        """
        This constructor will initialize all required variables here.
        """
        self.logger = Log.get_logger()


    def get_files_list(self):
        """
        This method will provide the list of all available tar files under the files directory.
        """
        status=False
        filelist = Files().list_files()
        if filelist:
            self.logger.info(f'Available tars {CONSTANT["FILES"]["IMAGE_FILES"]} are {filelist}.')
            response = filelist
            status=True
        else:
            response = f'No tar file is present in {CONSTANT["FILES"]["IMAGE_FILES"]}.'
            self.logger.error(response)
            status=False
        return status, response


    def get_file(self, filename=None, request_headers=None, request_ip=None):
        """
        This method will provide the requested file.
        """
        # since some files are requested during early boot stage where no token
        # is available (think: PXE+kernel+ramdisk)
        # we do enforce authentication for specific files. .bz2 + .torrent are
        # most likely the images.
        # request_ip serves no other purpose other than just update the status table.... 
        auth_ext = [".gz", ".tar", ".bz", ".bz2", ".torrent"]
        response = "Internal error"
        status=False
        token, ext  =None, None
        needs_auth = False
        if filename:
            result = re.search(r"^.+(\..[^.]+)(\?|\&|;|#)?", filename)
            ext = result.group(1)
            self.logger.debug(f"filename [{filename}], ext = [{ext}]")
            if ext in auth_ext:
                self.logger.debug(f"We enforce authentication for file extension = [{ext}]")
                needs_auth=True

        if needs_auth:
            if 'x-access-tokens' in request_headers:
                token = request_headers['x-access-tokens']
            if not token:
                self.logger.error(f'A valid token is missing for request {filename}.')
                status=False
                return status, 'Authentication error: A valid token is missing'
            try:
                jwt.decode(token, CONSTANT['API']['SECRET_KEY'], algorithms=['HS256']) ## Decode
            except jwt.exceptions.DecodeError:
                self.logger.error('Token is invalid for request {filename}.')
                status=False
                return status, 'Authentication error: Token is invalid'
            except Exception as exp:
                self.logger.error(f'Token is invalid for request {filename}. {exp}')
                status=False
                return status, 'Authentication error: Token is invalid'
            self.logger.info(f"Valid authentication for extension [{ext}] - Go!")

        self.logger.debug(f'Request for file: {filename} from IP Address: {request_ip}')
        node_interface = Database().get_record_join(
            ['nodeinterface.nodeid as id'],
            ['ipaddress.tablerefid=nodeinterface.id'],
            ['tableref="nodeinterface"',f"ipaddress.ipaddress='{request_ip}'"]
        )
        if node_interface:
            row = [{"column": "status", "value": "installer.discovery"}]
            where = [{"column": "id", "value": node_interface[0]["id"]}]
            Database().update('node', row, where)
        filepath = Files().check_file(filename)
        if filepath:
            self.logger.info(f'Tar File Path is {filepath}.')
            status=True
            return status, send_file(filepath, as_attachment=True)
        else:
            self.logger.error(f'{filename} is not present in {CONSTANT["FILES"]["IMAGE_FILES"]}')
            status=False
            return status, f'Service unavailable: {filename} is not present in {CONSTANT["FILES"]["IMAGE_FILES"]}'
        return status, response

