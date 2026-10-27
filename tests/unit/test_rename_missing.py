"""
TRIX-2250: renaming an object that does not exist must say so. Four entities let a rename
request of a missing name fall into their create path, which then failed on a column or
field check with an answer about something else.
"""
import pytest

from utils.database import Database


@pytest.fixture
def db(tmp_path):
    import common.constant as constant
    from utils import database
    from utils.dbstructure import DBStructure
    original = constant.CONSTANT['DATABASE']['DATABASE']
    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'unit.db')
    database.local_thread.connection = None
    for table in ['switch', 'switchinterface', 'otherdevices', 'network', 'ipaddress', 'firmwarecatalog']:
        Database().create(table, DBStructure().get_database_table_structure(table))
    yield Database()
    constant.CONSTANT['DATABASE']['DATABASE'] = original
    database.local_thread.connection = None


def _rename(entity, key, newkey):
    if entity == 'switch':
        from base.switch import Switch
        return Switch().update_switch('qa-nosuch', {'config': {key: {'qa-nosuch': {newkey: 'qa-new'}}}})
    if entity == 'otherdev':
        from base.otherdev import OtherDev
        return OtherDev().update_otherdev('qa-nosuch', {'config': {key: {'qa-nosuch': {newkey: 'qa-new'}}}})
    if entity == 'network':
        from base.network import Network
        return Network().update_network('qa-nosuch', {'config': {key: {'qa-nosuch': {newkey: 'qa-new'}}}})
    if entity == 'firmwarecatalog':
        from base.firmware import Firmware
        return Firmware().update_firmware('qa-nosuch', {'config': {key: {'qa-nosuch': {newkey: 'qa-new'}}}})


@pytest.mark.parametrize('entity, key, newkey', [
    ('switch', 'switch', 'newswitchname'),
    ('otherdev', 'otherdev', 'newotherdevname'),
    ('network', 'network', 'newnetname'),
    ('firmwarecatalog', 'firmwarecatalog', 'newfirmwarename'),
])
def test_renaming_a_missing_object_says_it_is_missing(db, entity, key, newkey):
    status, message = _rename(entity, key, newkey)
    assert status is False
    assert 'qa-nosuch not present in database for rename' in message, message
    assert 'Columns are incorrect' not in message and 'needs' not in message and 'CIDR' not in message
