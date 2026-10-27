"""
What a deletion leaves behind (TRIX-2163). A usergroup that is removed must stop being
listed on the objects that named it, and the last owner of a row must hand it to someone
who exists: an admin of a usergroup listed on the row, or rootus, which is NULL.
"""
from test_access_organisation import db, world, client, _body, TABLES  # noqa: F401 - fixtures


def _row(db, table, name):
    return db.get_record(table=table, where=f"name = '{name}'")[0]


def test_removing_a_usergroup_clears_it_from_every_governed_row(world, db):
    from base.usergroup import UserGroup
    assert str(world.intel) in _row(db, 'node', 'node001')['usergroups']
    assert str(world.intel) in _row(db, 'group', 'compute-intel')['usergroups']

    status, _ = UserGroup().delete_usergroup('intel')

    assert status is True
    assert _row(db, 'node', 'node001')['usergroups'] in (None, '')
    assert _row(db, 'group', 'compute-intel')['usergroups'] in (None, '')
    # a usergroup that was not deleted keeps its listing
    assert _row(db, 'node', 'node002')['usergroups'] == str(world.amd)


def test_removing_a_usergroup_leaves_the_other_listings_alone(world, db):
    from base.usergroup import UserGroup
    from utils.helper import Helper
    both = f"{world.intel},{world.amd}"
    db.update('node', Helper().make_rows({'usergroups': both}), [{'column': 'name', 'value': 'node001'}])

    UserGroup().delete_usergroup('intel')

    assert _row(db, 'node', 'node001')['usergroups'] == str(world.amd)


def test_the_last_owner_leaving_hands_the_row_to_an_admin_of_a_listed_usergroup(world, db):
    from base.user import User
    from utils.helper import Helper
    # node001 is listed to intel, whose admin is ivan; alice is its only owner
    db.update('node', Helper().make_rows({'owners': str(world.ids['alice'])}),
              [{'column': 'name', 'value': 'node001'}])

    status, _ = User().delete_user('alice')

    assert status is True
    assert _row(db, 'node', 'node001')['owners'] == str(world.ids['ivan'])


def test_the_last_owner_leaving_with_no_usergroup_hands_the_row_to_rootus(world, db):
    from base.user import User
    from utils.helper import Helper
    # rocky9 is listed to no usergroup, so there is no admin to inherit it
    db.update('osimage', Helper().make_rows({'owners': str(world.ids['alice'])}),
              [{'column': 'name', 'value': 'rocky9'}])

    User().delete_user('alice')

    assert _row(db, 'osimage', 'rocky9')['owners'] in (None, '')


def test_an_owner_leaving_beside_others_only_removes_itself(world, db):
    from base.user import User
    from utils.helper import Helper
    pair = f"{world.ids['alice']},{world.ids['carol']}"
    db.update('node', Helper().make_rows({'owners': pair}), [{'column': 'name', 'value': 'node001'}])

    User().delete_user('alice')

    assert _row(db, 'node', 'node001')['owners'] == str(world.ids['carol'])
