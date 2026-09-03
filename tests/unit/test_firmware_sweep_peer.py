"""The firmware sweep waits for a peer that can take writes before claiming anything."""


class _HA:
    def __init__(self, hastate, insync=True, overrule=False):
        self._hastate, self._insync, self._overrule = hastate, insync, overrule

    def get_hastate(self):
        return self._hastate

    def get_insync(self):
        return self._insync

    def get_overrule(self):
        return self._overrule


def test_a_sweep_waits_while_the_peer_cannot_take_the_claim():
    """
    Each claim is journaled and waits five seconds before refusing. With the
    peer away, N pending requests cost 5N seconds and N warnings per sweep,
    every five seconds, until it returns. The sweep asks once instead.
    """
    from utils.firmware_push import FirmwarePush
    push = FirmwarePush.__new__(FirmwarePush)
    assert push.peer_takes_writes(_HA(hastate=False)) is True
    assert push.peer_takes_writes(_HA(hastate=True, insync=True)) is True
    assert push.peer_takes_writes(_HA(hastate=True, insync=False, overrule=True)) is True
    assert push.peer_takes_writes(_HA(hastate=True, insync=False)) is False
