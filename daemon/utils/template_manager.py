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
Template manager helpers for Luna dynamic template lookup.
"""

import sys
from utils.log import Log
from utils.plugin_tree import build_plugin_tree


class TemplateManager(object):
    """Resolve template paths using the legacy Helper.template_find rules."""

    def __init__(self, logger=None):
        self.logger = Log.get_logger()

    def find_templates(self, startpath=None):
        """Build the template tree from a filesystem path."""
        return build_plugin_tree(startpath=startpath, logger=self.logger)

    def find_from_path(self, startpath=None, root=None, levelone=None, leveltwo=None):
        """Build the tree from disk and resolve the requested template path."""
        plugins = self.find_templates(startpath=startpath)
        return self.find(
            plugins=plugins,
            root=root,
            levelone=levelone,
            leveltwo=leveltwo,
        )

    def _normalize_levelones(self, levelone):
        if isinstance(levelone, str):
            return [levelone]
        return levelone or []

    def _root_steps(self, root):
        return root.split('/') if root else []

    def _subtree(self, plugins, root):
        subtree = plugins
        for treestep in self._root_steps(root):
            if treestep in subtree:
                subtree = subtree[treestep]
        return subtree

    def find(self, plugins=None, root=None, levelone=None, leveltwo=None):
        """Return the template path or None on failure."""
        self.logger.debug(f"Finding template in plugins.{root}.{levelone}.{leveltwo} / {plugins}")
        if not plugins:
            self.logger.error(f"Provided Plugins tree is empty or is missing root. plugins = [{plugins}], root = [{root}]")
            return None
        try:
            subtree = self._subtree(plugins, root)
            self.logger.debug(f"myplugin = [{subtree}]")
        except Exception as exp:
            self.logger.error(f"Loading template caused a problem in roottree: {exp}")
            return None
        levelones = self._normalize_levelones(levelone)
        try:
            for one in levelones:
                if leveltwo and one + leveltwo + '.templ' in subtree:
                    self.logger.debug(f"found plugins.{root}.{one}{leveltwo}")
                    return root + '/' + one + leveltwo + '.templ'
                elif one in subtree.keys():
                    if leveltwo and leveltwo in subtree[one]:
                        template = leveltwo.rsplit('.', 1)
                        self.logger.debug(f"found plugins.{root}.{one}.{template[0]}")
                        return root + '/' + one + '/' + template[0] + '.templ'
                    elif 'default.templ' in subtree[one]:
                        self.logger.debug(f"found plugins.{root}.{one}.default")
                        return root + '/' + one + '/default.templ'
                elif one + '.templ' in subtree:
                    self.logger.debug(f"found plugins.{root}.{one}")
                    return root + '/' + one + '.templ'
            return None
        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self.logger.error(f"Loading template caused a problem during selection: {exp}, {exc_type} in {exc_tb.tb_lineno}]")
            return None
