# This code is part of the TrinityX software suite
# Copyright (C) 2023  ClusterVision Solutions b.v.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>

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
    uidNumber: Optional[int] = None
    gidNumber: Optional[int] = None
    memberOf: Optional[List[str]] = None
    userPassword: Optional[str] = None
    cn: Optional[str] = None
    sn: Optional[str] = None
    givenName: Optional[str] = None
    mail: Optional[str] = None
    telephoneNumber: Optional[str] = None
    loginShell: Optional[str] = None
    homeDirectory: Optional[str] = None
    shadowExpire: Optional[int] = None

class OSGroupData(BaseModel, extra='forbid'):
    """
    This class will be used to represent OS groups.
    """
    # groupname: str
    gidNumber: Optional[int] = None
    member: Optional[List[str]] = None


# ----------------------------------------------------------------------------------------

class Plugin():
    """
    This class represents OS user plugin.
    It's the interface between Daemon API and obol to manage users and groups
    All functions are expected to return: Bool, (Str|Dict)
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

        if not obol_output:
            return False, "No users available"

        # users = { user['uid']: user for user in obol_output}
        return True, obol_output

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

        if not obol_output:
            return False, f"No user {username} available"

        return True, obol_output

    # ----------------------------------------------

    def update_user(self,
                    uid: str,
                    userPassword: str = None,
                    sn: str = None,
                    cn: str = None,
                    givenName: str = None,
                    groupname: str = None,
                    uidNumber: int = None,
                    gidNumber: int = None,
                    mail: str = None,
                    telephoneNumber: str = None,
                    loginShell: str = None,
                    memberOf: List[str] = None,
                    shadowExpire: int = None,
                    homeDirectory: str = None,
                    ):
        """
        This method will update a OS users.
        """
        user_exist, old_user = self.get_user(uid)
        new_user = OSUserData(
            uidNumber=uidNumber,
            gidNumber=gidNumber,
            memberOf=memberOf,
            userPassword=userPassword,
            sn=sn,
            givenName=givenName,
            mail=mail,
            telephoneNumber=telephoneNumber,
            loginShell=loginShell,
            shadowExpire=shadowExpire,
            homeDirectory=homeDirectory
        )

        flags_mapping = {
            'userPassword': '--password',
            'sn': '--sn',
            'cn': '--cn',
            'givenName': '--givenName',
            'uidNumber': '--uid',
            'gidNumber': '--gid',
            'mail': '--mail',
            'telephoneNumber': '--phone',
            'loginShell': '--shell',
            'memberOf': '--groups',
            'shadowExpire': '--expire',
            'homeDirectory': '--home'
        }
        flags_formatting = {
            'uidNumber' : lambda uidNumber: str(uidNumber),
            'gidNumber' : lambda gidNumber: str(gidNumber),
            'shadowExpire': lambda shadowExpire: str(shadowExpire),
            'memberOf': lambda memberOf: ",".join(memberOf)
        }

        obol_flags = []
        for key, flag in flags_mapping.items():
            value = new_user.dict().get(key)
            if value is None:
                continue
            obol_flags += [flag, flags_formatting.get(key, lambda x: x)(value)]

        if user_exist:
            obol_cmd = ['obol', 'user', 'modify', uid, *obol_flags]
        else:
            obol_cmd = ['obol', 'user', 'add', uid, *obol_flags]

        result = subprocess.run(
            obol_cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        if result.returncode != 0:
            return False, f"[obol: {result}]"

        if user_exist:
            return True, f"[obol: user {uid} updated]"
        else:
            return True, f"[obol: user {uid} created]"

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

        obol_output = json.loads(result.stdout.decode('utf-8'))\

        if not obol_output:
            return False, "No groups available"

        # groups = { group['cn']: group for group in obol_output}
        return True, obol_output

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

        if not obol_output:
            return False, f"No group {groupname} available"

        return True, obol_output

    # ----------------------------------------------

    def update_group(self,
                     cn: str,
                     gidNumber: str = None,
                     member: List[str] = None):
        """
        This method will update a OS groups.
        """
        group_exist, old_group = self.get_group(cn)
        new_group = OSGroupData(
            gidNumber=gidNumber,
            member=member
        )

        # Create group
        flags_mapping = {
            'gidNumber': '--gid',
            'member': '--users'
        }
        flags_formatting = {
            'gidNumber' : lambda gidNumber: str(gidNumber),
            'member': lambda member: ','.join(member)
        }
        obol_flags = []
        for key, flag in flags_mapping.items():
            value = new_group.dict().get(key)
            if value is not None:
                obol_flags += [flag, flags_formatting.get(key, lambda x: x)(value)]

        if group_exist:
            obol_cmd = ['obol', 'group', 'modify', cn, *obol_flags]
        else:
            obol_cmd = ['obol', 'group', 'add', cn, *obol_flags]

        result = subprocess.run(
            obol_cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        if result.returncode != 0:
            return False, f"[obol: {result}]"

        if group_exist:
            return True, f"[obol: group {cn} updated]"
        else:
            return True, f"[obol: group {cn} created]"

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



if __name__ == '__main__':
    plugin = Plugin()
    # from pprint import pprint
    # pprint(plugin.list_users())
    # pprint(plugin.get_user('test'))
    # pprint(plugin.list_groups())
    # pprint(plugin.get_group('test'))