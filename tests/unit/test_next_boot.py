"""
TRIX-1370: boot a node once into BIOS setup, over Redfish, or say why not.

The one rule under test is that the reset is never sent unless the override is
confirmed on the board. The IPMI boot flags were found unreliable on real
hardware, so there is no ipmitool fallback: every step that cannot be confirmed
refuses, per node, with the reason - because a reset without the override is an
ordinary reboot that reads as success.
"""
import pytest


SYSTEM_PATH = '/redfish/v1/Systems/Self'
RESET_TARGET = '/redfish/v1/Systems/Self/Actions/ComputerSystem.Reset'


class FakeClient():
    """A ComputerSystem with a Boot object, a reset action and a memory of writes."""

    def __init__(self, boot=None, power_state='On', patch_ok=True, applies=True,
                 post_ok=True):
        self.boot = boot
        self.power_state = power_state
        self.patch_ok = patch_ok
        self.applies = applies
        self.post_ok = post_ok
        self.patched = []
        self.posted = []

    def data(self):
        data = {'PowerState': self.power_state,
                'Actions': {'#ComputerSystem.Reset': {
                    'target': RESET_TARGET,
                    'ResetType@Redfish.AllowableValues': ['On', 'ForceRestart', 'ForceOff']}}}
        if self.boot is not None:
            data['Boot'] = dict(self.boot)
        data['@odata.etag'] = 'W/"etag-1"'
        return data

    def system(self):
        return True, SYSTEM_PATH, self.data()

    def get(self, path=None, cache=False):
        return True, self.data()

    def patch(self, path=None, payload=None, etag=None):
        self.patched.append((path, payload))
        self.etag_seen = etag
        if not self.patch_ok:
            return False, 'PATCH not allowed on this resource'
        if self.applies:
            self.boot.update(payload.get('Boot', {}))
        return True, {}

    def post(self, path=None, payload=None):
        self.posted.append((path, payload))
        if not self.post_ok:
            return False, 'reset refused'
        return True, {}


def advertising(*targets):
    return {'BootSourceOverrideEnabled': 'Disabled', 'BootSourceOverrideTarget': 'None',
            'BootSourceOverrideMode': 'Legacy',
            'BootSourceOverrideTarget@Redfish.AllowableValues': list(targets)}


@pytest.fixture
def plugin(monkeypatch):
    from plugins.control.redfish import Plugin
    holder = {}

    def make(fake):
        holder['fake'] = fake
        monkeypatch.setattr(Plugin, 'client', lambda self, **kwargs: holder['fake'])
        return Plugin(), fake
    return make


# --- the happy path ---------------------------------------------------------

def test_the_override_is_armed_once_and_then_the_node_is_reset(plugin):
    control, fake = plugin(FakeClient(boot=advertising('None', 'Pxe', 'BiosSetup')))
    status, message = control.boot_bios(device='bmc', username='u', password='p')
    assert status is True, message
    assert fake.patched == [(SYSTEM_PATH, {'Boot': {'BootSourceOverrideEnabled': 'Once',
                                                     'BootSourceOverrideTarget': 'BiosSetup'}})]
    assert fake.posted == [(RESET_TARGET, {'ResetType': 'ForceRestart'})]
    assert 'reset sent' in message
    # the resource was just read; its ETag rides along so patch() need not read again
    assert fake.etag_seen == 'W/"etag-1"'


def test_a_node_that_is_off_is_powered_on_instead_of_reset(plugin):
    """A reset on a powered-off system is refused by most boards; powering it on
    boots it into the override just the same."""
    control, fake = plugin(FakeClient(boot=advertising('BiosSetup'), power_state='Off'))
    status, message = control.boot_bios(device='bmc', username='u', password='p')
    assert status is True, message
    assert fake.posted == [(RESET_TARGET, {'ResetType': 'On'})]
    assert 'on sent' in message


def test_a_board_that_publishes_no_allowable_list_is_tried(plugin):
    boot = advertising()
    del boot['BootSourceOverrideTarget@Redfish.AllowableValues']
    control, fake = plugin(FakeClient(boot=boot))
    status, _ = control.boot_bios(device='bmc', username='u', password='p')
    assert status is True
    assert len(fake.patched) == 1 and len(fake.posted) == 1


# --- the refusals, none of which send a reset --------------------------------

def test_a_target_the_board_does_not_offer_is_refused_before_anything_is_written(plugin):
    control, fake = plugin(FakeClient(boot=advertising('None', 'Pxe', 'Hdd')))
    status, message = control.boot_bios(device='bmc', username='u', password='p')
    assert status is False
    assert 'Pxe' in message and 'Hdd' in message
    assert fake.patched == [] and fake.posted == []


def test_a_system_without_a_boot_object_is_refused(plugin):
    control, fake = plugin(FakeClient(boot=None))
    status, message = control.boot_bios(device='bmc', username='u', password='p')
    assert status is False
    assert 'no boot override' in message
    assert fake.patched == [] and fake.posted == []


def test_a_refused_write_sends_no_reset(plugin):
    control, fake = plugin(FakeClient(boot=advertising('BiosSetup'), patch_ok=False))
    status, message = control.boot_bios(device='bmc', username='u', password='p')
    assert status is False
    assert 'override refused' in message and 'PATCH not allowed' in message
    assert fake.posted == []


def test_a_write_the_board_accepted_but_did_not_apply_sends_no_reset(plugin):
    """
    The third fate: 200 to the PATCH and nothing changed. Only the read-back
    tells it apart from a board that did what it was asked, and it is the case
    that would otherwise reboot the node normally and report BIOS setup.
    """
    control, fake = plugin(FakeClient(boot=advertising('BiosSetup'), applies=False))
    status, message = control.boot_bios(device='bmc', username='u', password='p')
    assert status is False
    assert 'not applied by the board' in message
    assert len(fake.patched) == 1 and fake.posted == []


def test_a_refused_reset_says_the_override_is_still_armed(plugin):
    control, fake = plugin(FakeClient(boot=advertising('BiosSetup'), post_ok=False))
    status, message = control.boot_bios(device='bmc', username='u', password='p')
    assert status is False
    assert 'override armed' in message and 'reset refused' in message


def test_an_unknown_target_is_refused_without_touching_the_board(plugin):
    control, fake = plugin(FakeClient(boot=advertising('BiosSetup')))
    status, message = control.redfish_next_boot('floppy', 'bmc', 'u', 'p')
    assert status is False and 'unknown boot target' in message
    assert fake.patched == [] and fake.posted == []


# --- reading the override back ---------------------------------------------

def test_status_reports_the_three_override_fields(plugin):
    control, _ = plugin(FakeClient(boot=advertising('BiosSetup')))
    status, message = control.boot_status(device='bmc', username='u', password='p')
    assert status is True
    assert message == 'target=None, enabled=Disabled, mode=Legacy'


def test_status_on_a_system_without_a_boot_object_says_so(plugin):
    control, _ = plugin(FakeClient(boot=None))
    status, message = control.boot_status(device='bmc', username='u', password='p')
    assert status is False and 'no boot override' in message


# --- clearing it, the way out of a board that keeps re-entering setup --------

def test_clear_disarms_the_override_and_sends_no_reset(plugin):
    """
    An AMI MegaRAC keeps BiosSetup/Once armed while the node sits in the setup
    screen, so every reset lands there again. Clearing is the way out without a
    console, and it must not itself reset the node.
    """
    boot = advertising('BiosSetup')
    boot.update({'BootSourceOverrideEnabled': 'Once', 'BootSourceOverrideTarget': 'BiosSetup'})
    control, fake = plugin(FakeClient(boot=boot))
    status, message = control.boot_clear(device='bmc', username='u', password='p')
    assert status is True, message
    assert fake.patched == [(SYSTEM_PATH, {'Boot': {'BootSourceOverrideEnabled': 'Disabled',
                                                     'BootSourceOverrideTarget': 'None'}})]
    assert fake.posted == []
    assert 'cleared' in message


def test_a_clear_the_board_did_not_apply_is_reported(plugin):
    boot = advertising('BiosSetup')
    boot.update({'BootSourceOverrideEnabled': 'Once', 'BootSourceOverrideTarget': 'BiosSetup'})
    control, fake = plugin(FakeClient(boot=boot, applies=False))
    status, message = control.boot_clear(device='bmc', username='u', password='p')
    assert status is False and 'not applied' in message


# --- no Redfish, no boot target --------------------------------------------

def test_the_ipmitool_plugin_refuses_rather_than_tries():
    from plugins.control.default import Plugin
    for method in ('boot_bios', 'boot_status', 'boot_clear'):
        status, message = getattr(Plugin(), method)(device='bmc', username='u', password='p')
        assert status is False
        assert 'need Redfish' in message


def test_a_site_plugin_without_the_method_is_answered_not_raised():
    """The boot methods joined the contract late; a plugin written against the
    nine-method contract is told so per node instead of raising in a thread."""
    from utils.control import Control as NodeControl

    class Legacy():
        pass

    status, message = NodeControl().boot_call(Legacy, 'boot_bios', 'bmc', 'u', 'p')
    assert status is False
    assert 'does not implement boot_bios' in message


def test_the_dispatcher_calls_the_method_with_the_credentials():
    from utils.control import Control as NodeControl
    seen = {}

    class Modern():
        def boot_status(self, device=None, username=None, password=None):
            seen.update(device=device, username=username, password=password)
            return True, 'ok'

    status, _ = NodeControl().boot_call(Modern, 'boot_status', 'bmc', 'u', 'p')
    assert status is True
    assert seen == {'device': 'bmc', 'username': 'u', 'password': 'p'}
