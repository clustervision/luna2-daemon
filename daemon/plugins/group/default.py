#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Plugin Class ::  Default group plugin. is being called during group create/update
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import os
import pwd
import sys
from utils.log import Log
from utils.helper import Helper


class Plugin():
    """
    Class for running custom scripts during group create/update actions
    """

    def __init__(self):
        """
        two defined methods are mandatory:
        - postcreate
        - postupdate
        """
        self.logger = Log.get_logger()

    # ---------------------------------------------------------------------------

    def postcreate(self, name=None):
        return True, "Nothing done"

    # ---------------------------------------------------------------------------

    def postupdate(self, name=None):
        return True, "Nothing done"

    # ---------------------------------------------------------------------------

