"""
Finding a free address (TRIX-2163). The ping that is meant to prove an address is
unused must be given the address itself, and the caller's list of taken addresses is
read, never written to.
"""
import pytest


@pytest.fixture
def helper_with_ping(monkeypatch):
    """A Helper whose ping is recorded rather than run. answers lists the addresses
    that reply, so everything else reads as free (exit code 1)."""
    from utils.helper import Helper
    helper = Helper()
    seen = []

    def fake(command, return_exit_code=False, timeout_sec=7200):
        target = command.split()[-1]
        seen.append(target)
        return ('', 0 if target in fake.answers else 1)

    fake.answers = set()
    monkeypatch.setattr(helper, 'runcommand', fake)
    return helper, seen, fake


def test_the_ping_is_given_an_address_and_not_a_generator(helper_with_ping):
    helper, seen, _ = helper_with_ping

    result = helper.get_available_ip('10.141.0.0', '16', ['10.141.0.1'], ping=True)

    assert result == '10.141.0.2'
    assert seen == ['10.141.0.2'], f'pinged {seen}'
    assert all('generator' not in target for target in seen)


def test_an_address_that_answers_is_skipped(helper_with_ping):
    helper, seen, fake = helper_with_ping
    fake.answers = {'10.141.0.1', '10.141.0.2'}

    result = helper.get_available_ip('10.141.0.0', '16', [], ping=True)

    assert result == '10.141.0.3'
    assert seen == ['10.141.0.1', '10.141.0.2', '10.141.0.3']


def test_the_callers_taken_list_is_not_written_to(helper_with_ping):
    helper, _, fake = helper_with_ping
    fake.answers = {'10.141.0.1', '10.141.0.2', '10.141.0.3', '10.141.0.4', '10.141.0.5'}
    taken = ['10.141.0.250']
    before = list(taken)

    helper.get_available_ip('10.141.0.0', '16', taken, ping=True)

    assert taken == before


def test_every_candidate_answering_still_yields_the_first_free_address(helper_with_ping):
    helper, _, fake = helper_with_ping
    fake.answers = {f'10.141.0.{n}' for n in range(1, 40)}

    result = helper.get_available_ip('10.141.0.0', '16', [], ping=True)

    assert result == '10.141.0.1'


def test_without_ping_the_first_free_address_comes_back(helper_with_ping):
    helper, seen, _ = helper_with_ping

    result = helper.get_available_ip('10.141.0.0', '16', ['10.141.0.1', '10.141.0.2'], ping=False)

    assert result == '10.141.0.3'
    assert seen == []
