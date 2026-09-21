#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
"""
Refresh the classic installer golden from the template.

Run this ONLY after an intended change to daemon/templates/templ_install.cfg, in the same
commit as that change, then read the diff of the golden before committing. Every osimage
that has not been rebuilt executes this file, so a line moved here changes nodes nobody has
touched: an unexplained difference is a regression, not a file to refresh.

    python tests/regression/regen_classic_installer.py
"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, '..', '..', 'daemon', 'templates', 'templ_install.cfg')
GOLDEN = os.path.join(HERE, 'golden', 'templ_install.cfg')

if __name__ == '__main__':
    shutil.copyfile(TEMPLATE, GOLDEN)
    print('wrote', os.path.relpath(GOLDEN, os.getcwd()))
