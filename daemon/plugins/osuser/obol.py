import subprocess
import json
import sys
from typing import List, Dict, Optional, Tuple
from pydantic import BaseModel, Field

"""
Helper classes for the plugin
"""

class OSUserData(BaseModel, extra='forbid'):
    """
    This class will be used to represent OS users.
    """
    # username: str
    uid: Optional[int] = None
    gid: Optional[int] = None
    groupname: Optional[str] = None
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

class OSGroupData(BaseModel, extra='forbid'):
    """
    This class will be used to represent OS groups.
    """
    # groupname: str
    gid: Optional[int] = None
    users: Optional[List[str]] = None


# ----------------------------------------------------------------------------------------

class Plugin():
    """
    This class represents OS user plugin.
    It's the interface between Daemon API and obol to manage users and groups
    """

    def list_users(self):
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

        obol_output = json.loads(result.stdout.decode('utf-8'))
        users = { user['uid']: {'uid': user['uidNumber']} for user in obol_output}
        return True, users

    # ----------------------------------------------

    def get_user(self, username: str):
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
        
        obol_output = json.loads(result.stdout.decode('utf-8').strip())
        user = OSUserData(
                      uid=obol_output.get('uidNumber'),
                      gid=obol_output.get('gidNumber'),
                      homedir=obol_output.get('homeDirectory'),
                      shell=obol_output.get('loginShell'),
                      surname=obol_output.get('sn'),
                      givenname=obol_output.get('givenName'),
                      phone=obol_output.get('telephoneNumber'),
                      email=obol_output.get('mail'),
                      expire=obol_output.get('shadowExpire'),
                      last_change=obol_output.get('shadowLastChange'),
                      password=obol_output.get('userPassword'),
                      groups=obol_output.get('groups', [])
                      )
        return True, user.dict()

    # ----------------------------------------------

    def update_user(self, 
                    username: str, 
                    password: str = None,
                    surname: str = None,
                    givenname: str = None,
                    groupname: str = None,
                    uid: int = None,
                    gid: int = None,
                    email: str = None,
                    phone: str = None,
                    shell: str = None,
                    groups: List[str] = None,
                    expire: int = None,
                    homedir: str = None,
                    ):
        """
        This method will update a OS users.
        """
        user_exist, old_user = self.get_user(username)
        new_user = OSUserData(
            uid=uid,
            gid=gid,
            groups=groups,
            password=password,
            surname=surname,
            givenname=givenname,
            groupname=groupname,
            email=email,
            phone=phone,
            shell=shell,
            expire=expire,
            homedir=homedir
        )
        
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

        obol_flags = []
        for key, flag in flags_mapping.items():
            value = new_user.dict().get(key)
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

    # ----------------------------------------------

    def delete_user(self, username: str):
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


    # ----------------------------------------------

    def list_groups(self):
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

        obol_output = json.loads(result.stdout.decode('utf-8'))
        groups = { group['cn']: {'gid':['gidNumber']} for group in obol_output}
        return True, groups

    # ----------------------------------------------

    def get_group(self, groupname: str):
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

        obol_output = json.loads(result.stdout.decode('utf-8'))
        group = OSGroupData(
                        gid=obol_output['gidNumber'],
                        users=obol_output.get('users', [])
        )
        return True, group.dict()

    # ----------------------------------------------

    def update_group(self, 
                     groupname: str,
                     gid: str = None,
                     users: List[str] = None):
        """
        This method will update a OS groups.
        """
        group_exist, old_group = self.get_group(groupname)
        new_group = OSGroupData(
            gid=gid,
            users=users
        )

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
            value = new_group.dict().get(key)
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
        
        if group_exist:
            return True, f"[obol: group {groupname} updated]"
        else:
            return True, f"[obol: group {groupname} created]"

    # ----------------------------------------------

    def delete_group(self, groupname: str):
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

