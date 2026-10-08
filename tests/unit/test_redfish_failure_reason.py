"""
TRIX-2242: a control call that cannot reach the BMC answers with the reason, never with
nothing. The Redfish helper hands back (status, reason, data) on failure; a method that
returns the empty data slot sends null to the CLI, which then has no status to print.
"""
import importlib.util
import os

import pytest

PLUGIN = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                      'daemon', 'plugins', 'control', 'redfish.py')
REASON = 'bmc01: no answer within 10s'


class DeadBoard():
    """A Redfish client whose every lookup fails the way an unreachable BMC does."""
    def system(self):
        return False, REASON, None

    def manager(self):
        return False, REASON, None

    def chassis(self):
        return False, REASON, None


@pytest.fixture
def plugin(monkeypatch):
    spec = importlib.util.spec_from_file_location('control_redfish_plugin', PLUGIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.Plugin, 'client', lambda self, **_kwargs: DeadBoard())
    return module.Plugin()


def _boot_methods(plugin):
    return sorted(name for name in dir(plugin) if name.startswith('boot_') and callable(getattr(plugin, name)))


def test_the_boot_methods_exist(plugin):
    assert {'boot_bios', 'boot_status', 'boot_clear'} <= set(_boot_methods(plugin))


def test_every_boot_method_names_the_reason_when_the_bmc_is_unreachable(plugin):
    for name in _boot_methods(plugin):
        status, message = getattr(plugin, name)(device='bmc01', username='u', password='p')
        assert status is False, name
        assert message == REASON, f'{name} answered {message!r} instead of the reason'


def test_the_log_service_lookup_names_the_reason_too(plugin):
    status, message = plugin.log_service_paths(redfish=DeadBoard())
    assert status is False and message == REASON
