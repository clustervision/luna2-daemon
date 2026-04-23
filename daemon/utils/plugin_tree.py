# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>

"""
Shared helpers to build Luna plugin/template trees from filesystem paths.
"""

import os


def build_plugin_tree(startpath=None, logger=None):
    """Build the nested plugin tree structure used by plugin/template managers."""

    def log_debug(message):
        if logger:
            logger.debug(message)

    def set_leaf(tree=None, branches=None, leaf=None):
        if len(branches) == 1:
            tree[branches[0]] = leaf
            return
        if branches[0] not in tree.keys():
            tree[branches[0]] = {}
        set_leaf(tree[branches[0]], branches[1:], leaf)

    tree = {}
    for root, dirs, files in os.walk(startpath):
        branches = [os.path.basename(startpath)]
        if root != startpath:
            branches.extend(os.path.relpath(root, startpath).split(os.sep))
        set_leaf(tree, branches, dict([(d, {}) for d in dirs] + [(f, None) for f in files]))
    log_debug(f"PLUGIN TREE {startpath}: {tree}")
    return tree
