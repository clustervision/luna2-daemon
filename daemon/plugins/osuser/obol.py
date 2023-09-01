import subprocess
import json
from typing import List
from plugins.osuser.interface import OSUserPluginInterface, OSUser, OSGroup



# @dataclass
# class OSUser(AbstractBaseClass):
#     """
#     This class will be used to represent OS users.
#     """
    # username: str
    # password: Optional[str] = field(default=None, repr=False)
    # group: Optional[str] = field(default=None, repr=False)
    # groups: Optional[List[str]] = field(default=None, repr=False)
    # uid: Optional[int] = field(default=None, repr=False)
    # gid: Optional[int] = field(default=None, repr=False)
    # surname: Optional[str] = field(default=None, repr=False)
    # givenname: Optional[str] = field(default=None, repr=False)
    # email: Optional[str] = field(default=None, repr=False)
    # phone: Optional[str] = field(default=None, repr=False)
    # shell: Optional[str] = field(default=None, repr=False)
    # homedir: Optional[str] = field(default=None, repr=False)
    # expire: Optional[int] = field(default=None, repr=False)
    # last_change: Optional[int] = field(default=None, repr=False)

#     def to_json(self):
#         """
#         This method will convert the object to json.
#         """
#         return {
#             'username': self.username,
#             'password': self.password,
#             'group': self.group,
#             'groups': self.groups,
#             'uid': self.uid,
#             'gid': self.gid,
#             'surname': self.surname,
#             'givenname': self.givenname,
#             'email': self.email,
#             'phone': self.phone,
#             'shell': self.shell,
#             'homedir': self.homedir
#         }

# @dataclass
# class OSGroup(object):
#     """
#     This class will be used to represent OS groups.
#     """
#     groupname: str = field(default=None, repr=False)
#     gid: Optional[int] = field(default=None, repr=False)
#     users: Optional[List[str]] = field(default=None, repr=False)

#     def to_json(self):
#         """
#         This method will convert the object to json.
#         """
#         return {
#             'groupname': self.groupname,
#             'gid': self.gid,
#             'users': self.users
#         }

class Plugin(OSUserPluginInterface):
    """
    This class will be used to represent OS user plugins.
    """
    osuser = OSUser
    osgroup = OSGroup

    def list_users(self) -> (bool, List[OSUser]):
        """
        This method will list all OS users.
        """
        result = subprocess.run(['obol', 'user', 'list'], check=True, capture_output=True).stdout
        usernames = result.decode('utf-8').strip().split('\n')
        users = [OSUser(username=username) for username in usernames]
        return True, users

    def get_user(self, username: str) -> (bool, OSUser):
        """
        This method will list all OS users.
        """
        result = subprocess.run(['obol', 'user', 'show', username], check=True, capture_output=True).stdout.decode('utf-8')
        result_json = json.loads(result)
        # sample output 
        # {
        #     "cn": "diegoo",
        #     "gidNumber": "1070",
        #     "homeDirectory": "/trinity/home/diegoo",
        #     "loginShell": "/bin/bash",
        #     "shadowExpire": "-1",
        #     "shadowLastChange": "19599",
        #     "shadowMax": "99999",
        #     "shadowMin": "0",
        #     "shadowWarning": "7",
        #     "sn": "diegoo",
        #     "uid": "diegoo",
        #     "uidNumber": "1070",
        #     "userPassword": "{SSHA}ac/F3HYdD+6sdNSxa4gE5E0QFYEXJzIL"
        # }
        user = OSUser(username=result_json['cn'],
                      gid=result_json['gidNumber'],
                      homedir=result_json['homeDirectory'],
                      shell=result_json['loginShell'],
                      surname=result_json['sn'],
                      uid=result_json['uidNumber'],
                      expire=result_json['shadowExpire'],
                      last_change=result_json['shadowLastChange'],
                      )
        return True, user

    def update_user(self, username: str, user: OSUser) -> (bool, str):
        """
        This method will update a OS users.
        """
        if username != user.username:
            return False, "username mismatch"
        
        _, users = self.list_users()
        usernames = [user.username for user in users]
        if username not in usernames:
            result = subprocess.run(['obol', 'user', 'add', username], check=True, capture_output=True).stdout.decode('utf-8')
            return True, result
        else:
            result = subprocess.run(['obol', 'user', 'modify', username], check=True, capture_output=True).stdout.decode('utf-8')
            return True, result

    def delete_user(self, username: str) -> bool:
        """
        This method will delete a OS users.
        """
        result = subprocess.run(['obol', 'user', 'delete', username], check=True, capture_output=True).stdout.decode('utf-8')
        return True, result

    def list_groups(self) -> (bool, List[OSGroup]):
        """
        This method will list all OS user groups.
        """
        result = subprocess.run(['obol', 'group', 'list'], check=True, capture_output=True).stdout
        lines = result.decode('utf-8').strip().split('\n')
        group_items = [line.split(' ') for line in lines]
        groups = [OSGroup(groupname=groupname, gid=gid) for gid, groupname in group_items]
        return True, groups

    def get_group(self, groupname: str) -> (bool, OSGroup):
        """
        This method will list all OS groups.
        """
        result = subprocess.run(['obol', 'group', 'show', groupname], check=True, capture_output=True).stdout.decode('utf-8')
        result_json = json.loads(result)
        # sample output
        # {
        #     "cn": "admins",
        #     "gidNumber": "150"
        # }
        group = OSGroup(groupname=result_json['cn'],
                        gid=int(result_json['gidNumber']))
        return True, group

    def update_group(self, groupname: str, group: OSGroup) -> bool:
        """
        This method will update a OS groups.
        """
        if groupname != group.groupname:
            return False, "groupname mismatch"
        
        _, groups = self.list_groups()
        groupnames = [group.groupname for group in groups]
        if groupname not in groupnames:
            result = subprocess.run(['obol', 'group', 'add', groupname], check=True, capture_output=True).stdout.decode('utf-8')
            return True, result
        else:
            result = subprocess.run(['obol', 'group', 'modify', groupname], check=True, capture_output=True).stdout.decode('utf-8')
            return True, result

    def delete_group(self, groupname: str) -> bool:
        """
        This method will delete a OS groups.
        """
        result = subprocess.run(['obol', 'group', 'delete', groupname], check=True, capture_output=True).stdout.decode('utf-8')
        return True, result
