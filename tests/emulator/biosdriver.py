"""FakeDriver plus a BIOS attribute store.

sushy-tools' FakeDriver implements no BIOS at all (only the libvirt driver does,
and libvirt is not available here). This adds the three calls the emulator's BIOS
routes need, and nothing else: every byte of Redfish protocol - the routes, the
@Redfish.Settings annotation, the settings object pointer, the JSON shapes, the
auth and the error bodies - still comes from sushy-tools.

What is NOT modelled, by sushy-tools rather than by this file: staging. Its BIOS
PATCH route writes into the same store its BIOS GET route reads, so a write takes
effect immediately and no reset is needed. That is the one property our own fake
BMC exists to model, and it is why this emulator complements that fake instead of
replacing it.
"""
from sushy_tools.emulator.resources.systems import fakedriver

DEFAULTS = {
    'BootMode': 'Uefi',
    'ProcVirtualization': 'Enabled',
    'SriovGlobalEnable': 'Disabled',
    'QuietBoot': 'Enabled',
}


class BiosFakeDriver(fakedriver.FakeDriver):

    _bios = {}

    def get_bios(self, identity):
        return self._bios.setdefault(identity, dict(DEFAULTS))

    def set_bios(self, identity, attributes):
        self._bios.setdefault(identity, dict(DEFAULTS)).update(attributes or {})

    def reset_bios(self, identity):
        self._bios[identity] = dict(DEFAULTS)
