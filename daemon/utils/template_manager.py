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


class TemplateManager(object):
    """Resolve template paths using the legacy Helper.template_find rules."""

    def __init__(self, logger=None):
        self.logger = logger

    def _log_debug(self, message):
        if self.logger:
            self.logger.debug(message)

    def _log_error(self, message):
        if self.logger:
            self.logger.error(message)

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
        self._log_debug(f"Finding template in plugins.{root}.{levelone}.{leveltwo} / {plugins}")
        if not plugins:
            self._log_error(f"Provided Plugins tree is empty or is missing root. plugins = [{plugins}], root = [{root}]")
            return None
        try:
            subtree = self._subtree(plugins, root)
            self._log_debug(f"myplugin = [{subtree}]")
        except Exception as exp:
            self._log_error(f"Loading template caused a problem in roottree: {exp}")
            return None
        levelones = self._normalize_levelones(levelone)
        try:
            for one in levelones:
                if leveltwo and one + leveltwo + '.templ' in subtree:
                    self._log_debug(f"found plugins.{root}.{one}{leveltwo}")
                    return root + '/' + one + leveltwo + '.templ'
                elif one in subtree.keys():
                    if leveltwo and leveltwo in subtree[one]:
                        template = leveltwo.rsplit('.', 1)
                        self._log_debug(f"found plugins.{root}.{one}.{template[0]}")
                        return root + '/' + one + '/' + template[0] + '.templ'
                    elif 'default.templ' in subtree[one]:
                        self._log_debug(f"found plugins.{root}.{one}.default")
                        return root + '/' + one + '/default.templ'
                elif one + '.templ' in subtree:
                    self._log_debug(f"found plugins.{root}.{one}")
                    return root + '/' + one + '.templ'
            return None
        except Exception as exp:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            self._log_error(f"Loading template caused a problem during selection: {exp}, {exc_type} in {exc_tb.tb_lineno}]")
            return None
