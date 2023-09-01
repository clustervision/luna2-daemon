from obol import Plugin
from interface import OSUserPluginInterface, OSUser, OSGroup

# Test
if __name__ == '__main__':
    plugin = Plugin()
    methods = ['list_users', 'update_user', 'get_user', 'delete_user', 'list_groups', 'update_group', 'get_group', 'delete_group']
    arguments = [ [], ['testuser', OSUser(username='testuser')],  ['testuser'], ['testuser'], [], ['testgroup', OSGroup(groupname='testgroup')], ['testgroup'], ['testgroup']]
    for method, args in zip(methods, arguments):
        try:
            print(f"Testing {method}")
            res = getattr(plugin, method)(*args)
            print("[OK]", *res)
        except NotImplementedError:
            print(f"[ERR] {method} not implemented")
        except Exception as e:
            print(f"[ERR] {method} failed with {e}")
        finally:
            print()