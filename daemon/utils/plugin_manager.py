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
Plugin manager helpers for Luna dynamic plugin loading.
"""

import importlib


class PluginManager(object):
    """Resolve plugin classes using explicit import rules and caching."""

    _class_cache = {}

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
            else:
                raise KeyError(f"Missing plugin tree step: {treestep}")
        return subtree

    def _candidate_modules(self, subtree, root, levelone, leveltwo):
        root_module = root.replace('/', '.')
        seen = set()

        def emit(module_name):
            if module_name not in seen:
                seen.add(module_name)
                return module_name
            return None

        if leveltwo and f'{levelone}{leveltwo}.py' in subtree:
            module_name = emit(f'plugins.{root_module}.{levelone}{leveltwo}')
            if module_name:
                yield module_name
        if levelone in subtree:
            if leveltwo and leveltwo in subtree[levelone]:
                plugin = leveltwo.rsplit('.', 1)
                module_name = emit(f'plugins.{root_module}.{levelone}.{plugin[0]}')
                if module_name:
                    yield module_name
            if 'default.py' in subtree[levelone]:
                module_name = emit(f'plugins.{root_module}.{levelone}.default')
                if module_name:
                    yield module_name
        if f'{levelone}.py' in subtree:
            module_name = emit(f'plugins.{root_module}.{levelone}')
            if module_name:
                yield module_name
        module_name = emit(f'plugins.{root_module}.default')
        if module_name:
            yield module_name

    def load(self, plugins=None, root=None, levelone=None, leveltwo=None, class_name='Plugin'):
        """Return the requested plugin class or None on failure."""
        if not plugins:
            self._log_error(f'Provided plugins tree is empty. root=[{root}]')
            return None
        class_name = class_name or 'Plugin'
        root_module = root.replace('/', '.')
        try:
            subtree = self._subtree(plugins, root)
        except Exception as exp:
            self._log_error(f'Loading module caused a problem in roottree: {exp}')
            return None

        levelones = self._normalize_levelones(levelone)
        for one in levelones:
            for module_name in self._candidate_modules(subtree, root, one, leveltwo):
                cache_key = (module_name, class_name)
                if cache_key in self._class_cache:
                    self._log_debug(f'loading {module_name}.{class_name} from cache')
                    return self._class_cache[cache_key]
                try:
                    self._log_debug(f'loading {module_name}.{class_name}')
                    module = importlib.import_module(module_name)
                    plugin_class = getattr(module, class_name)
                    self._class_cache[cache_key] = plugin_class
                    return plugin_class
                except ModuleNotFoundError as exp:
                    if exp.name == module_name:
                        continue
                    self._log_error(f'Loading module caused a nested import problem in {module_name}: {exp}')
                    return None
                except AttributeError as exp:
                    self._log_error(f'Plugin class missing in {module_name}: {exp}')
                    return None
                except Exception as exp:
                    self._log_error(f'Loading module caused a problem during selection: {exp}')
                    return None

        module_name = f'plugins.{root_module}.default'
        cache_key = (module_name, class_name)
        if cache_key in self._class_cache:
            self._log_debug(f'loading {module_name}.{class_name} from cache')
            return self._class_cache[cache_key]
        try:
            self._log_debug(f'loading {module_name}.{class_name}')
            module = importlib.import_module(module_name)
            plugin_class = getattr(module, class_name)
            self._class_cache[cache_key] = plugin_class
            return plugin_class
        except ModuleNotFoundError as exp:
            if exp.name == module_name:
                return None
            self._log_error(f'Loading module caused a nested import problem in {module_name}: {exp}')
            return None
        except AttributeError as exp:
            self._log_error(f'Plugin class missing in {module_name}: {exp}')
            return None
        except Exception as exp:
            self._log_error(f'Loading module caused a problem during selection: {exp}')
            return None
