"""
The harness refuses every connect that leaves the box (TRIX-2132): a sweep a test starts
in a background pool would otherwise sit on a black-holed BMC address and hold the
interpreter open after the counts line. Loopback stays open for the emulator tests.
"""
import socket
import pytest


def test_a_connect_off_the_box_is_refused_at_once_and_recorded(request):
    reached = request.config.network_reached
    before = len(reached)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(ConnectionRefusedError, match='test reached the network'):
            sock.connect(('10.255.255.1', 443))
    assert reached[before:] and 'test_no_network' in reached[-1][1]
    del reached[before:]


def test_loopback_is_not_the_network():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        with pytest.raises((ConnectionRefusedError, socket.timeout, OSError)) as exp:
            sock.connect(('127.0.0.1', 9))
        assert 'test reached the network' not in str(exp.value)
