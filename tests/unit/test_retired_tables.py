"""
The roles table is retired: no layout, not created, not backed up. An upgraded cluster keeps
its empty copy and a fresh install never has one, so a backup written while the table still
existed must restore on both.
"""


def test_backup_carrying_the_retired_roles_table_restores_on_a_fresh_install(tmp_path):
    """
    import_config rolls the whole restore back when one table import fails. A backup from
    before the change carries a roles entry (sequence and structure, never a row, since nothing
    ever wrote one), and on a fresh install there is no roles table to clear. The import must
    still answer with a true status.
    """
    import common.constant as constant
    from utils import database
    from utils.database import Database
    from utils.tables import Tables

    constant.CONSTANT['DATABASE']['DATABASE'] = str(tmp_path / 'fresh.db')
    database.local_thread.connection = None
    Database().create('cluster', [{"column": "id", "datatype": "INTEGER", "key": "PRIMARY"}])
    old_entry = [{'SQLITE_SEQUENCE': 1},
                 {'STRUCTURE': [{"column": "id", "datatype": "INTEGER", "key": "PRIMARY", "keyadd": "AUTOINCREMENT"},
                                {"column": "name", "datatype": "VARCHAR", "length": "50"},
                                {"column": "modules", "datatype": "VARCHAR", "length": "200"}]}]

    assert Tables().import_table('roles', old_entry, emptyok=True, fixtable=False) is True


def test_roles_is_in_no_table_list():
    import common.database_layout as layout
    from utils.dbstructure import DBStructure
    from utils.tables import Tables

    assert not hasattr(layout, 'DATABASE_LAYOUT_roles')
    assert 'roles' not in DBStructure().tables
    assert 'roles' not in Tables().tables
    assert DBStructure().get_database_table_structure('roles') is None
