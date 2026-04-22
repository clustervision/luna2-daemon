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
import sys


class PluginManager(object):
    """Resolve plugin classes using explicit import rules and caching."""

    _class_cache = {}
    _module_state = {}

    def __init__(self, logger=None):
        self.logger = logger

    def _log_debug(self, message):
        if self.logger:
            self.logger.debug(message)

    def _log_error(self, message):
        if self.logger:
            self.logger.error(message)

    def _legacy_metadata(self, plugin_class, module_name):
        plugin_name = getattr(plugin_class, 'PLUGIN_NAME', None)
        plugin_kind = getattr(plugin_class, 'PLUGIN_KIND', None)
        plugin_api_version = getattr(plugin_class, 'PLUGIN_API_VERSION', None)

        if plugin_name and plugin_kind and plugin_api_version is not None:
            return plugin_class

        module_parts = module_name.split('.')[1:]
        inferred_name = module_parts[-1] if module_parts else 'default'
        inferred_kind = '/'.join(module_parts[:-1]) if len(module_parts) > 1 else ''

        if not plugin_name:
            setattr(plugin_class, 'PLUGIN_NAME', inferred_name)
        if not plugin_kind:
            setattr(plugin_class, 'PLUGIN_KIND', inferred_kind)
        if plugin_api_version is None:
            setattr(plugin_class, 'PLUGIN_API_VERSION', 1)

        self._log_debug(f'legacy plugin format detected for {module_name}')
        return plugin_class

    def _resolve_plugin_class(self, module, class_name, module_name):
        for candidate in [class_name, 'Plugin', 'plugin', 'Handler']:
            plugin_class = getattr(module, candidate, None)
            if plugin_class is not None:
                return self._legacy_metadata(plugin_class, module_name)
        raise AttributeError(f'No compatible plugin class found in {module_name}')

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
            self._log_debug(f'reloading {module_name}')
            module = importlib.reload(sys.modules[module_name])
            self._remember_module_state(module_name, module)
            return module
        self._log_debug(f'loading {module_name}')
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

    def load(self, plugins=None, root=None, levelone=None, leveltwo=None, class_name='Plugin', reload=False):
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
                if not reload and cache_key in self._class_cache and self._module_changed_on_disk(module_name):
                    self._log_debug(f'plugin changed on disk, invalidating {module_name}')
                    self.invalidate(module_name, class_name)
                    reload = True
                if reload:
                    self.invalidate(module_name, class_name)
                if not reload and cache_key in self._class_cache:
                    self._log_debug(f'loading {module_name}.{class_name} from cache')
                    return self._class_cache[cache_key]
                try:
                    module = self._import_plugin_module(module_name, reload=reload)
                    plugin_class = self._resolve_plugin_class(module, class_name, module_name)
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
        if not reload and cache_key in self._class_cache and self._module_changed_on_disk(module_name):
            self._log_debug(f'plugin changed on disk, invalidating {module_name}')
            self.invalidate(module_name, class_name)
            reload = True
        if reload:
            self.invalidate(module_name, class_name)
        if not reload and cache_key in self._class_cache:
            self._log_debug(f'loading {module_name}.{class_name} from cache')
            return self._class_cache[cache_key]
        try:
            module = self._import_plugin_module(module_name, reload=reload)
            plugin_class = self._resolve_plugin_class(module, class_name, module_name)
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
