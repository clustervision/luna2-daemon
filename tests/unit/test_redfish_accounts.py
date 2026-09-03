"""
TRIX-2001: the accounts a redfishsetup describes exist on the BMC, with their roles.

The in-band install step creates only the bmcsetup user, over ipmitool, and can
set no Redfish role. This reconciles out of band, on the install event that
already queues the inventory collection, with the one credential a fresh BMC
has - and reads the board back afterwards, because what the board holds is the
answer, not what the writes returned.
"""
from configparser import RawConfigParser

import pytest

from utils.database import Database
from utils.helper import Helper


ROOT = '/redfish/v1/'
SERVICE = '/redfish/v1/AccountService'
ACCOUNTS = '/redfish/v1/AccountService/Accounts'


class FakeBoard():
    """An AccountService with numbered slots, some empty, and a memory of writes."""

    def __init__(self, accounts=None, post_ok=True, applies=True):
        self.slots = {}
        for number, entry in enumerate(accounts or [], start=1):
            self.slots[f'{ACCOUNTS}/{number}'] = dict(
                {'Id': str(number), '@odata.etag': f'W/"{number}"', 'UserName': '',
                 'RoleId': 'ReadOnly', 'Enabled': False}, **entry)
        self.post_ok = post_ok
        self.applies = applies
        self.posted = []
        self.patched = []

    def service_root(self):
        return True, {'AccountService': {'@odata.id': SERVICE}}

    def get(self, path=None, cache=False):
        if path == ROOT:
            return self.service_root()
        if path == SERVICE:
            return True, {'Accounts': {'@odata.id': ACCOUNTS}}
        if path == ACCOUNTS:
            return True, {'Members': [{'@odata.id': p} for p in self.slots]}
        if path in self.slots:
            return True, dict(self.slots[path])
        return False, f'no such resource {path}'

    def post(self, path=None, payload=None):
        self.posted.append((path, payload))
        if not self.post_ok:
            return False, 'POST not allowed'
        number = len(self.slots) + 1
        new = f'{ACCOUNTS}/{number}'
        if self.applies:
            self.slots[new] = dict({'Id': str(number), '@odata.etag': 'W/"n"'}, **payload)
        return True, {}

    def patch(self, path=None, payload=None, etag=None):
        self.patched.append((path, payload))
        if path not in self.slots:
            return False, 'no such account'
        if self.applies:
            self.slots[path].update(payload)
        return True, {}


def wanted_with(accounts=None, policy='skip'):
    return {'device': '10.0.0.9', 'groupname': 'compute',
            'bootstrap': {'username': 'admin', 'password': 'bmcpw'},
            'scheme': 'https', 'port': None, 'verify': False,
            'accounts': accounts or [{'username': 'rfadmin', 'password': 'rfpw',
                                      'role': 'Administrator'}],
            'policy': policy}


@pytest.fixture
def plugins_dir(monkeypatch):
    """The repo's own plugin tree, so the real search path resolves plugins/redfish/default.py."""
    import os
    import sys
    constant = sys.modules['common.constant'].CONSTANT
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    monkeypatch.setitem(constant['PLUGINS'], 'PLUGINS_DIRECTORY',
                        os.path.join(repo, 'daemon', 'plugins'))


@pytest.fixture
def reconciler(monkeypatch, plugins_dir):
    """A RedfishAccounts bound to a fake board, with the database answered by hand."""
    from utils.redfish_accounts import RedfishAccounts
    state = {'board': None, 'wanted': None, 'passwords_ok': True}

    def make(board, wanted=None, passwords_ok=True):
        state.update(board=board, wanted=wanted or wanted_with(), passwords_ok=passwords_ok)
        monkeypatch.setattr(RedfishAccounts, 'desired',
                            lambda self, nodename=None: (True, state['wanted']))
        monkeypatch.setattr(RedfishAccounts, 'client',
                            lambda self, wanted=None, username=None, password=None: state['board'])
        monkeypatch.setattr(RedfishAccounts, 'password_works',
                            lambda self, wanted=None, username=None, password=None:
                            state['passwords_ok'])
        return RedfishAccounts(), board
    return make


# --- creating ---------------------------------------------------------------

def test_a_missing_account_is_created_with_its_role(reconciler):
    accounts, board = reconciler(FakeBoard([{'UserName': 'admin', 'RoleId': 'Administrator',
                                             'Enabled': True}]))
    status, message = accounts.reconcile(nodename='node001')
    assert status is True, message
    assert board.posted == [(ACCOUNTS, {'UserName': 'rfadmin', 'Password': 'rfpw',
                                        'RoleId': 'Administrator', 'Enabled': True})]
    assert 'rfadmin: created as Administrator' in message


def test_a_board_that_refuses_post_gets_its_first_empty_slot_patched(reconciler):
    """iDRAC and older MegaRAC: the slots exist from the factory, empty."""
    accounts, board = reconciler(FakeBoard([
        {'UserName': 'admin', 'RoleId': 'Administrator', 'Enabled': True},
        {}, {}], post_ok=False))
    status, message = accounts.reconcile(nodename='node001')
    assert status is True, message
    assert len(board.posted) == 1
    assert board.patched[0][0] == f'{ACCOUNTS}/2'
    assert board.patched[0][1]['UserName'] == 'rfadmin'
    assert board.slots[f'{ACCOUNTS}/3']['UserName'] == ''


def test_no_empty_slot_and_no_post_is_a_named_failure(reconciler):
    accounts, _ = reconciler(FakeBoard([{'UserName': 'admin', 'RoleId': 'Administrator',
                                         'Enabled': True}], post_ok=False))
    status, message = accounts.reconcile(nodename='node001')
    assert status is False
    assert 'no empty account slot' in message


# --- correcting ---------------------------------------------------------------

def test_a_wrong_role_and_a_disabled_state_are_corrected(reconciler):
    accounts, board = reconciler(FakeBoard([
        {'UserName': 'admin', 'RoleId': 'Administrator', 'Enabled': True},
        {'UserName': 'rfadmin', 'RoleId': 'Operator', 'Enabled': False}]))
    status, message = accounts.reconcile(nodename='node001')
    assert status is True, message
    assert board.posted == []
    assert board.patched == [(f'{ACCOUNTS}/2', {'RoleId': 'Administrator', 'Enabled': True})]


def test_a_password_the_board_no_longer_accepts_is_set_again(reconciler):
    """Luna's record is the desired state. Converging is said out loud, never silent."""
    accounts, board = reconciler(FakeBoard([
        {'UserName': 'admin', 'RoleId': 'Administrator', 'Enabled': True},
        {'UserName': 'rfadmin', 'RoleId': 'Administrator', 'Enabled': True}]),
        passwords_ok=False)
    status, message = accounts.reconcile(nodename='node001')
    assert status is True, message
    assert board.patched == [(f'{ACCOUNTS}/2', {'Password': 'rfpw'})]
    assert 'rfadmin: password' in message


def test_an_account_as_configured_is_left_alone(reconciler):
    accounts, board = reconciler(FakeBoard([
        {'UserName': 'admin', 'RoleId': 'Administrator', 'Enabled': True},
        {'UserName': 'rfadmin', 'RoleId': 'Administrator', 'Enabled': True}]))
    status, message = accounts.reconcile(nodename='node001')
    assert status is True
    assert board.posted == [] and board.patched == []
    assert message == 'rfadmin: as configured'


# --- the read-back --------------------------------------------------------------

def test_a_write_the_board_accepted_but_did_not_apply_is_a_failure(reconciler):
    accounts, _ = reconciler(FakeBoard([{'UserName': 'admin', 'RoleId': 'Administrator',
                                         'Enabled': True}], applies=False))
    status, message = accounts.reconcile(nodename='node001')
    assert status is False
    assert 'not on the board after writing it' in message


# --- the unmanaged-users policy, on Redfish accounts too ------------------------

def test_disable_policy_disables_what_neither_bmcsetup_nor_redfishsetup_names(reconciler):
    accounts, board = reconciler(FakeBoard([
        {'UserName': 'admin', 'RoleId': 'Administrator', 'Enabled': True},
        {'UserName': 'rfadmin', 'RoleId': 'Administrator', 'Enabled': True},
        {'UserName': 'vendor', 'RoleId': 'Administrator', 'Enabled': True},
        {'UserName': 'old', 'RoleId': 'ReadOnly', 'Enabled': False}]),
        wanted=wanted_with(policy='disable'))
    status, _ = accounts.reconcile(nodename='node001')
    assert status is True
    assert board.patched == [(f'{ACCOUNTS}/3', {'Enabled': False})]


def test_skip_policy_touches_nothing_it_does_not_name(reconciler):
    accounts, board = reconciler(FakeBoard([
        {'UserName': 'admin', 'RoleId': 'Administrator', 'Enabled': True},
        {'UserName': 'rfadmin', 'RoleId': 'Administrator', 'Enabled': True},
        {'UserName': 'vendor', 'RoleId': 'Administrator', 'Enabled': True}]))
    accounts.reconcile(nodename='node001')
    assert board.patched == []


# --- what the node wants, from the database -------------------------------------

@pytest.fixture
def cluster(sqlite_db):
    Database().insert('group', Helper().make_rows({'name': 'compute', 'id': 1, 'bmcsetupid': 1,
                                                    'redfishsetupid': 1, 'setupredfish': 1}))
    Database().insert('bmcsetup', Helper().make_rows({'id': 1, 'name': 'default-bmcsetup',
                                                       'username': 'admin', 'password': 'bmcpw'}))
    Database().insert('redfishsetup', Helper().make_rows({'id': 1, 'name': 'default-redfishsetup',
                                                           'scheme': 'https'}))
    Database().insert('redfishaccount', Helper().make_rows({
        'id': 1, 'redfishsetupid': 1, 'name': 'default', 'username': 'rfadmin',
        'password': 'rfpw', 'role': 'Administrator'}))
    for num, name in enumerate(('node001', 'node002'), start=1):
        Database().insert('node', Helper().make_rows({'name': name, 'id': num, 'groupid': 1}))
        Database().insert('nodeinterface', Helper().make_rows({'id': num, 'nodeid': num,
                                                                'interface': 'BMC'}))
        Database().insert('ipaddress', Helper().make_rows({
            'id': num, 'tableref': 'nodeinterface', 'tablerefid': num,
            'ipaddress': f'10.0.0.{num}'}))
    return Database()


def test_the_group_flag_and_profile_are_inherited(cluster):
    from utils.redfish_accounts import RedfishAccounts
    assert RedfishAccounts().wanted('node001') is True
    status, wanted = RedfishAccounts().desired('node001')
    assert status is True, wanted
    assert wanted['device'] == '10.0.0.1'
    assert wanted['bootstrap'] == {'username': 'admin', 'password': 'bmcpw'}
    assert wanted['accounts'] == [{'username': 'rfadmin', 'password': 'rfpw',
                                   'role': 'Administrator'}]
    assert wanted['policy'] == 'skip'


def test_setupredfish_off_on_the_node_refuses_even_with_the_group_on(cluster):
    from utils.redfish_accounts import RedfishAccounts
    Database().update('node', Helper().make_rows({'setupredfish': 0}),
                      [{'column': 'name', 'value': 'node002'}])
    assert RedfishAccounts().wanted('node002') is False
    status, reason = RedfishAccounts().desired('node002')
    assert status is False and 'setupredfish off' in reason


# --- the install event queues it, ahead of the collection -----------------------

def queued(task):
    return [row['param'] for row in Database().get_record(table='queue') or []
            if row['task'] == task]


def test_the_setupbmc_event_queues_provisioning_before_the_collection(cluster):
    from base.monitor import Monitor
    Monitor().redfish_on_setupbmc(nodename='node001', state='install.setupbmc')
    rows = [row for row in Database().get_record(table='queue') or []
            if row['param'] == 'node001']
    assert [row['task'] for row in rows] == ['provision_redfish_accounts',
                                             'collect_redfish_inventory']


def test_a_node_with_the_flag_off_queues_only_the_collection(cluster):
    from base.monitor import Monitor
    Database().update('node', Helper().make_rows({'setupredfish': 0}),
                      [{'column': 'name', 'value': 'node002'}])
    Monitor().redfish_on_setupbmc(nodename='node002', state='install.setupbmc')
    assert 'node002' not in queued('provision_redfish_accounts')
    assert 'node002' in queued('collect_redfish_inventory')


def test_the_drain_settles_both_in_one_sweep(cluster, monkeypatch):
    """A node is provisioned before it is collected: the collection logs in as
    the account being created."""
    from base.monitor import Monitor
    from utils.bios_push import BiosPush
    from utils.queue import Queue
    from utils import redfish_accounts
    Monitor().redfish_on_setupbmc(nodename='node001', state='install.setupbmc')
    # the tasks are five minutes out; pull them into the selectable window,
    # which is created within the last hour and not in the future
    from datetime import datetime, timedelta
    recent = (datetime.utcnow() - timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')
    Database().update('queue', Helper().make_rows({'created': recent}),
                      [{'column': 'param', 'value': 'node001'}])
    seen = {}
    monkeypatch.setattr(redfish_accounts.RedfishAccounts, 'settle',
                        lambda self, provision=None, collect=None, request_id=None:
                        seen.update(provision=provision, collect=collect) or 'rid')
    assert BiosPush().collect_queued_inventory() is True
    assert seen == {'provision': ['node001'], 'collect': ['node001']}
    assert not Queue().next_task_in_queue('redfish', status='queued')


# --- the default profile at bootstrap -------------------------------------------

def parser_with(section=None):
    parser = RawConfigParser()
    parser.add_section('BMCSETUP')
    if section is not None:
        parser.add_section('REDFISHSETUP')
        for key, value in section.items():
            parser.set('REDFISHSETUP', key, value)
    return parser


def test_the_section_makes_a_profile_with_one_account():
    from common.bootstrap import default_redfishsetup
    setup, account = default_redfishsetup(parser_with(
        {'NAME': 'default-redfishsetup', 'USERNAME': 'rfadmin', 'PASSWORD': 'x',
         'ROLE': 'Administrator'}))
    assert {row['column']: row['value'] for row in setup} == {
        'name': 'default-redfishsetup', 'scheme': 'https', 'verify': '0'}
    assert {row['column']: row['value'] for row in account} == {
        'redfishsetupid': '1', 'name': 'default', 'username': 'rfadmin',
        'password': 'x', 'role': 'Administrator'}


def test_an_older_bootstrap_without_the_section_still_starts():
    from common.bootstrap import default_redfishsetup
    assert default_redfishsetup(parser_with()) == (None, None)


def test_a_section_without_a_password_makes_no_profile():
    from common.bootstrap import default_redfishsetup
    assert default_redfishsetup(parser_with({'USERNAME': 'rfadmin'})) == (None, None)


# --- on demand ------------------------------------------------------------------

def test_a_group_is_expanded_at_the_edge(cluster, monkeypatch):
    from utils import redfish_accounts
    seen = {}
    monkeypatch.setattr(redfish_accounts.RedfishAccounts, 'settle',
                        lambda self, provision=None, collect=None, request_id=None:
                        seen.update(provision=provision) or 'rid')
    status, response = redfish_accounts.RedfishAccounts().bulk_provision(
        {'config': {'node': {'group': 'compute'}}})
    assert status is True
    assert sorted(seen['provision']) == ['node001', 'node002']
    assert response['config']['node']['accounts']['queued'] == 2


def test_a_group_nobody_has_is_named(cluster):
    from utils.redfish_accounts import RedfishAccounts
    status, message = RedfishAccounts().bulk_provision({'config': {'node': {'group': 'gpu'}}})
    assert status is False and 'not available' in message
