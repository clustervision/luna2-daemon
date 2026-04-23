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
import os
import sys
from utils.log import Log
from utils.plugin_tree import build_plugin_tree


class PluginManager(object):
    """Resolve plugin classes using explicit import rules and caching."""

    _class_cache = {}
    _module_state = {}

    def __init__(self, logger=None):
        self.logger = Log.get_logger()

    def _resolve_plugin_class(self, module, class_name, module_name):
        requested = class_name or 'Plugin'
        plugin_class = getattr(module, requested, None)
        if plugin_class is not None:
            return plugin_class
        if requested != 'Plugin':
            plugin_class = getattr(module, 'Plugin', None)
            if plugin_class is not None:
                return plugin_class
        raise AttributeError(f'No compatible plugin class found in {module_name}')

    def find_plugins(self, startpath=None):
        """Build the plugin tree from a filesystem path."""
        return build_plugin_tree(startpath=startpath, logger=self.logger)

    def load_from_path(self, startpath=None, root=None, levelone=None, leveltwo=None, class_name='Plugin', reload=False):
        """Build the tree from disk and load the requested plugin class."""
        plugins = self.find_plugins(startpath=startpath)
        return self.load(
            plugins=plugins,
            root=root,
            levelone=levelone,
            leveltwo=leveltwo,
            class_name=class_name,
            reload=reload,
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

    def _module_file(self, module):
        return getattr(module, '__file__', None)

    def _fingerprint_path(self, module_file):
        if not module_file or not os.path.isfile(module_file):
            return None
        stat = os.stat(module_file)
        return (stat.st_mtime_ns, stat.st_size)

    def _remember_module_state(self, module_name, module):
        module_file = self._module_file(module)
        self._module_state[module_name] = self._fingerprint_path(module_file)

    def _module_changed_on_disk(self, module_name):
        module = sys.modules.get(module_name)
        if module is None:
            return False
        previous = self._module_state.get(module_name)
        current = self._fingerprint_path(self._module_file(module))
        if previous is None:
            self._module_state[module_name] = current
            return False
        return current != previous

    def invalidate(self, module_name=None, class_name=None):
        """Invalidate one cached plugin class or all cache entries."""
        if module_name is None:
            self._class_cache.clear()
            return

        if class_name is not None:
            self._class_cache.pop((module_name, class_name), None)
            return

        stale_keys = [key for key in self._class_cache if key[0] == module_name]
        for stale_key in stale_keys:
            self._class_cache.pop(stale_key, None)
        self._module_state.pop(module_name, None)

    def _import_plugin_module(self, module_name, reload=False):
        if reload and module_name in sys.modules:
            self.logger.debug(f'reloading {module_name}')
            module = importlib.reload(sys.modules[module_name])
            self._remember_module_state(module_name, module)
            return module
        self.logger.debug(f'loading {module_name}')
        module = importlib.import_module(module_name)
        self._remember_module_state(module_name, module)
        return module

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

    def _legacy_load_error(self, exp):
        exc_type, exc_obj, exc_tb = sys.exc_info()
        self.logger.error(f'Loading module caused a problem during selection: {exp}, {exc_type} in {exc_tb.tb_lineno}]')

    def load(self, plugins=None, root=None, levelone=None, leveltwo=None, class_name='Plugin', reload=False):
        """Return the requested plugin class or None on failure."""
        if not plugins:
            self.logger.error(f'Provided Plugins tree is empty or is missing root. plugins = [{plugins}], root = [{root}]')
            return None
        class_name = class_name or 'Plugin'
        root_module = (root or '').replace('/', '.')
        try:
            subtree = self._subtree(plugins, root)
        except Exception as exp:
            self.logger.error(f'Loading module caused a problem in roottree: {exp}')
            return None

        levelones = self._normalize_levelones(levelone)
        for one in levelones:
            for module_name in self._candidate_modules(subtree, root, one, leveltwo):
                cache_key = (module_name, class_name)
                candidate_reload = reload
                if not candidate_reload and cache_key in self._class_cache and self._module_changed_on_disk(module_name):
                    self.logger.debug(f'plugin changed on disk, invalidating {module_name}')
                    self.invalidate(module_name, class_name)
                    candidate_reload = True
                if candidate_reload:
                    self.invalidate(module_name, class_name)
                if not candidate_reload and cache_key in self._class_cache:
                    self.logger.debug(f'loading {module_name}.{class_name} from cache')
                    return self._class_cache[cache_key]
                try:
                    module = self._import_plugin_module(module_name, reload=candidate_reload)
                    plugin_class = self._resolve_plugin_class(module, class_name, module_name)
                    self._class_cache[cache_key] = plugin_class
                    return plugin_class
                except ModuleNotFoundError as exp:
                    if exp.name == module_name:
                        continue
                    self.logger.error(f'Loading module caused a nested import problem in {module_name}: {exp}')
                    continue
                except AttributeError as exp:
                    self.logger.error(f'Getattr caused a problem: {exp}')
                    continue
                except Exception as exp:
                    self._legacy_load_error(exp)
                    continue

        module_name = f'plugins.{root_module}.default'
        cache_key = (module_name, class_name)
        default_reload = reload
        if not default_reload and cache_key in self._class_cache and self._module_changed_on_disk(module_name):
            self.logger.info(f'plugin changed on disk, invalidating and reloading {module_name}')
            self.invalidate(module_name, class_name)
            default_reload = True
        if default_reload:
            self.invalidate(module_name, class_name)
        if not default_reload and cache_key in self._class_cache:
            self.logger.debug(f'loading {module_name}.{class_name} from cache')
            return self._class_cache[cache_key]
        try:
            module = self._import_plugin_module(module_name, reload=default_reload)
            plugin_class = self._resolve_plugin_class(module, class_name, module_name)
            self._class_cache[cache_key] = plugin_class
            return plugin_class
        except ModuleNotFoundError as exp:
            if exp.name == module_name:
                return None
            self.logger.error(f'Loading module caused a nested import problem in {module_name}: {exp}')
            return None
        except AttributeError as exp:
            self.logger.error(f'Getattr caused a problem: {exp}')
            return None
        except Exception as exp:
            self._legacy_load_error(exp)
            return None
