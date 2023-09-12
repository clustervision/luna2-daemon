import subprocess
import json
import sys
from typing import List, Dict, Optional, Tuple
from pydantic import BaseModel, Field



class OSUserData(BaseModel, extra='forbid'):
    """
    This class will be used to represent OS users.
    """
    # username: str
    uid: Optional[int] = None
    gid: Optional[int] = None
    groups: Optional[List[str]] = None
    password: Optional[str] = None
    surname: Optional[str] = None
    givenname: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    shell: Optional[str] = None
    homedir: Optional[str] = None
    expire: Optional[int] = None
    last_change: Optional[int] = None

class OSUserUpdateData(OSUserData, extra='forbid'):
    """
    This class will be used to represent update for OS users.
    """
    groupname: Optional[str] = None
    last_change: int = Field(exclude=True)

class OSGroupData(BaseModel, extra='forbid'):
    """
    This class will be used to represent OS groups.
    """
    # groupname: str
    gid: Optional[int] = None
    users: Optional[List[str]] = None




class Plugin():
    """
    This class will be used to represent OS user plugins.
    """
    osuserdata = OSUserData
    osuserupdatedata = OSUserUpdateData
    osgroupdata = OSGroupData

    def list_users(self) -> (bool, Tuple[str, OSUserData] | str):
        """
        This method will list all OS users.
        """
        obol_cmd = ['obol', '-J', 'user', 'list']
        result = subprocess.run(
            obol_cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        if result.returncode != 0:
            return False, f"[obol: {result}]"

        _users = json.loads(result.stdout.decode('utf-8'))
        users = { user['uid']: OSUserData(uid=user['uidNumber']) for user in _users}
        return True, users

    def get_user(self, username: str) -> (bool, Tuple[str, OSUserData]  | str):
        """
        This method will list all OS users.
        """
        obol_cmd = ['obol', '-J', 'user', 'show', username]
        result = subprocess.run(
            obol_cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        if result.returncode != 0:
            return False, f"[obol: {result}]"
        
        result_json = json.loads(result.stdout.decode('utf-8').strip())
        user = OSUserData(
                      uid=result_json.get('uidNumber'),
                      gid=result_json.get('gidNumber'),
                      homedir=result_json.get('homeDirectory'),
                      shell=result_json.get('loginShell'),
                      surname=result_json.get('sn'),
                      givenname=result_json.get('givenName'),
                      phone=result_json.get('telephoneNumber'),
                      email=result_json.get('mail'),
                      expire=result_json.get('shadowExpire'),
                      last_change=result_json.get('shadowLastChange'),
                      password=result_json.get('userPassword'),
                      groups=result_json.get('groups', [])
                      )
        return True, user

    def update_user(self, username: str, user: OSUserUpdateData) -> (bool, str):
        """
        This method will update a OS users.
        """
        flags_mapping = {
            'password': '--password',
            'surname': '--sn',
            'givenname': '--givenName',
            'groupname': '--group',
            'uid': '--uid',
            'gid': '--gid',
            'email': '--mail',
            'phone': '--phone',
            'shell': '--shell',
            'groups': '--groups',
            'expire': '--expire',
            'homedir': '--home'
        }
        flags_formatting = {
            'uid' : lambda uid: str(uid),
            'gid' : lambda gid: str(gid),
            'expire': lambda expire: str(expire),
            'groups': lambda groups: ",".join(groups)
        }
        
        user_exist, old_user = self.get_user(username)

        obol_flags = []
        for key, flag in flags_mapping.items():
            value = user.dict().get(key)
            if value is None:
                continue
            obol_flags += [flag, flags_formatting.get(key, lambda x: x)(value)]

        if user_exist:
            obol_cmd = ['obol', 'user', 'modify', username, *obol_flags]
        else:
            obol_cmd = ['obol', 'user', 'add', username, *obol_flags]

        result = subprocess.run(
            obol_cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        if result.returncode != 0:
            return False, f"[obol: {result}]"

        if user_exist:
            return True, f"[obol: user {username} updated]"
        else:
            return True, f"[obol: user {username} created]"

    def delete_user(self, username: str) -> (bool, str):
        """
        This method will delete a OS users.
        """
        obol_cmd = ['obol', 'user', 'delete', username]
        result = subprocess.run(
            obol_cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        
        if result.returncode != 0:
            return False, f"[obol: {result}]"
        
        return True, f"[obol: user {username} deleted]"


    def list_groups(self) -> (bool, Tuple[str, OSGroupData]  | str):
        """
        This method will list all OS user groups.
        """
        obol_cmd = ['obol', '-J', 'group', 'list']
        result = subprocess.run(
            obol_cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        if result.returncode != 0:
            return False, f"[cmd: {obol_cmd}][obol: {result.stderr.decode('utf-8')}]"

        _groups = json.loads(result.stdout.decode('utf-8'))
        groups = { group['cn']: OSGroupData(gid=group['gidNumber']) for group in _groups}
        return True, groups

    def get_group(self, groupname: str) -> (bool, Tuple[str, OSGroupData] | str):
        """
        This method will list all OS groups.
        """
        obol_cmd = ['obol', '-J', 'group', 'show', groupname]
        result = subprocess.run(
            obol_cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        
        if result.returncode != 0:
            return False, f"[obol: {result}]"

        result_json = json.loads(result.stdout.decode('utf-8'))
        group = OSGroupData(
                        gid=result_json['gidNumber'],
                        users=result_json.get('users', [])
        )
        return True, group

    def update_group(self, groupname: str, group: OSGroupData) -> (bool, str):
        """
        This method will update a OS groups.
        """
        group_exist, old_group = self.get_group(groupname)
        print(group)
        sys.stdout.flush()
        # Create group
        flags_mapping = {
            'gid': '--gid',
            'users': '--users'
        }
        flags_formatting = {
            'gid' : lambda gid: str(gid),
            'users': lambda users: ','.join(users)
        }
        obol_flags = []
        for key, flag in flags_mapping.items():
            value = group.dict().get(key)
            if value is not None:
                obol_flags += [flag, flags_formatting.get(key, lambda x: x)(value)]

        if group_exist:
            obol_cmd = ['obol', 'group', 'modify', groupname, *obol_flags]
        else:
            obol_cmd = ['obol', 'group', 'add', groupname, *obol_flags]

        result = subprocess.run(
            obol_cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        if result.returncode != 0:
            return False, f"[obol: {result}]"
        
        # old_users = (old_group.users if group_exist else None) or []
        # new_users = group.users or []

        # users_to_add = [user for user in new_users if user not in old_users]
        # users_to_remove = [user for user in old_users if user not in new_users]

        # # Add users to group
        # if len(users_to_add) > 0:
        #     obol_cmd = ['obol', 'group', 'addusers', groupname, *users_to_add]
        #     result = subprocess.run(
        #         obol_cmd,
        #         check=False,
        #         stdout=subprocess.PIPE,
        #         stderr=subprocess.PIPE)
            
        #     if result.returncode != 0:
        #         return False, f"[obol: {result}]"
        #     if result.stdout.decode('utf-8') != '':
        #         return False, f"[obol: {result}]"
        
        # # Remove users from group
        # if len(users_to_remove) > 0:
        #     obol_cmd = ['obol', 'group', 'delusers', groupname, *users_to_remove]
        #     result = subprocess.run(
        #         obol_cmd,
        #         check=False,
        #         stdout=subprocess.PIPE,
        #         stderr=subprocess.PIPE)
            
        #     if result.returncode != 0:
        #         return False, f"[obol: {result}]"
        
        if group_exist:
            return True, f"[obol: group {groupname} updated]"
        else:
            return True, f"[obol: group {groupname} created]"

    def delete_group(self, groupname: str) -> (bool, str):
        """
        This method will delete a OS groups.
        """
        obol_cmd = ['obol', 'group', 'delete', groupname]

        result = subprocess.run(
            obol_cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        if result.returncode != 0:
            return False, f"[obol: {result}]"

        return True, f"[obol: group {groupname} deleted]"
