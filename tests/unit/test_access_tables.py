"""
The layout declares which tables access control governs (TRIX-2086): a table carries the
three columns and is governed, follows a governed parent by a named column, or is rootus
only by name. A table in none of the three is unclassified, and the next table added
would be exactly that.
"""
import common.database_layout as layout
from common.access import CHILDREN, GOVERNED, ROOTUS
from utils.dbstructure import DBStructure

COLUMNS = ('owners', 'usergroups', 'access')


def _columns(table):
    return [column['column'] for column in DBStructure().get_database_table_structure(table)]


def test_every_table_the_daemon_creates_is_classified_exactly_once():
    created = set(DBStructure().tables)
    classified = set(GOVERNED) | set(CHILDREN) | ROOTUS
    assert created - classified == set(), f'tables without a classification: {sorted(created - classified)}'
    assert classified - created == set(), f'classified tables the daemon does not create: {sorted(classified - created)}'
    overlap = (set(GOVERNED) & set(CHILDREN)) | (set(GOVERNED) & ROOTUS) | (set(CHILDREN) & ROOTUS)
    assert not overlap, f'tables in two classes: {sorted(overlap)}'


def test_every_governed_table_carries_the_three_columns_and_nothing_else_does():
    for table in GOVERNED:
        missing = [c for c in COLUMNS if c not in _columns(table)]
        assert not missing, f'{table} is governed but lacks {missing}'
    for table in list(CHILDREN) + sorted(ROOTUS):
        present = [c for c in COLUMNS if c in _columns(table)]
        assert not present, f'{table} carries {present} but is not governed: classify it'


def test_every_child_names_a_column_it_has_and_a_parent_that_is_governed():
    for table, (parent, column) in CHILDREN.items():
        assert column in _columns(table), f'{table}: parent column {column} does not exist'
        if parent == 'tableref':
            assert 'tableref' in _columns(table), f'{table}: a tableref child needs a tableref column'
        else:
            assert parent in GOVERNED, f'{table}: parent {parent} is not governed'


def test_default_modes_are_the_ones_the_design_states():
    from common.access import Access
    assert Access().mode_text(None, 'node') == 'rwxrwx---'
    assert Access().mode_text(None, 'osimage') == 'rwxrwxr--'
    assert Access().mode_text(None, 'network') == 'rw-r--r--'
    assert {t for t, m in GOVERNED.items() if m == '770'} == {'node', 'group', 'bmcsetup', 'redfishsetup', 'profile'}
    assert {t for t, m in GOVERNED.items() if m == '774'} == {'osimage', 'biosconfig', 'firmwarecatalog'}
    assert {t for t, m in GOVERNED.items() if m == '644'} == {'cluster', 'network', 'route', 'cloud', 'switch', 'rack', 'otherdevices'}
