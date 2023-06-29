#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This file will place all the project directory and files to the correct place.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'


def install():
    """This method will initiate installation process of daemon"""
    print("install")


def update():
    """This method will update daemon"""
    print("update")


def upgrade():
    """This method will upgrade daemon to the latest version"""
    print("upgrade")


def validate_service():
    """This method will validate the systemd of daemon"""
    print("validate_service")


def validate_directory():
    """This method will validate the directory structure of daemon"""
    print("validate_directory")


def main():
    """This method will initiate the process of deployment."""
    print("Check Status and install")
