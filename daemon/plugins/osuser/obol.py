import subprocess
import json
from typing import List, Tuple
from plugins.osuser.interface import (
    OSUserPluginInterface,
    OSUserData,
    OSUserUpdateData,
    OSGroupData
)


class Plugin(OSUserPluginInterface):
    """
    This class will be used to represent OS user plugins.
    """
    osuserdata = OSUserData
    osuserupdatedata = OSUserUpdateData
    osgroupdata = OSGroupData

    def list_users(self) -> (bool, List[Tuple[str, OSUserData]] | str):
        """
        This method will list all OS users.
        """
        obol_cmd = ['obol', 'user', 'list']
        result = subprocess.run(
            obol_cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        if result.returncode != 0:
            return False, f"[obol: {result}]"

        usernames = result.stdout.decode('utf-8').strip().split('\n')
        users = [ (username, OSUserData()) for username in usernames]
        return True, users

    def get_user(self, username: str) -> (bool, Tuple[str, OSUserData]  | str):
        """
        This method will list all OS users.
        """
        obol_cmd = ['obol', 'user', 'show', username]
        result = subprocess.run(
            obol_cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        if result.returncode != 0:
            return False, f"[obol: {result}]"
        if result.stdout.decode('utf-8') == '':
            return False, f"[cmd: {obol_cmd}][obol: user {username} not found]"
        
        result_json = json.loads(result.stdout.decode('utf-8').strip())
        user = OSUserData(
                      gid=result_json['gidNumber'],
                      homedir=result_json['homeDirectory'],
                      shell=result_json['loginShell'],
                      surname=result_json['sn'],
                      uid=result_json['uidNumber'],
                      expire=result_json['shadowExpire'],
                      last_change=result_json['shadowLastChange'],
                      password=result_json.get('userPassword')
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
            if user_exist and (key in ['groupname', 'gid', 'groups']):
                raise KeyError(f'cannot update {key}')
            if user_exist and (value == old_user.dict().get(key)):
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
        if result.stdout.decode('utf-8') != '':
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
        if result.stdout.decode('utf-8') != '':
            return False, f"[cmd: {obol_cmd}][obol: {result.stdout.decode('utf-8')}]"
        
        return True, f"[obol: user {username} deleted]"


    def list_groups(self) -> (bool, List[Tuple[str, OSGroupData]]  | str):
        """
        This method will list all OS user groups.
        """
        obol_cmd = ['obol', 'group', 'list']
        result = subprocess.run(
            obol_cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        if result.returncode != 0:
            return False, f"[cmd: {obol_cmd}][obol: {result.stderr.decode('utf-8')}]"

        lines = result.stdout.decode('utf-8').strip().split('\n')
        group_items = [line.split(' ') for line in lines]
        groups = [(groupname, OSGroupData(gid=gid)) for gid, groupname in group_items]
        return True, groups

    def get_group(self, groupname: str) -> (bool, Tuple[str, OSGroupData] | str):
        """
        This method will list all OS groups.
        """
        obol_cmd = ['obol', 'group', 'show', groupname]
        result = subprocess.run(
            obol_cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        
        if result.returncode != 0:
            return False, f"[obol: {result}]"
        if result.stdout.decode('utf-8') == '':
            return False, f"[cmd: {obol_cmd}][obol: group {groupname} not found]"

        result_json = json.loads(result.stdout.decode('utf-8').strip())
        group = OSGroupData(
                        gid=int(result_json['gidNumber']))
        return True, group

    def update_group(self, groupname: str, group: OSGroupData) -> (bool, str):
        """
        This method will update a OS groups.
        """
        group_exist, old_group = self.get_group(groupname)
        if group_exist:
            if group.gid is not None and group.gid != old_group.gid:
                raise KeyError('cannot update gid')
        else:
            # Create group
            flags_mapping = {
                'gid': '--gid'
            }
            flags_formatting = {
                'gid' : lambda gid: str(gid),
            }
            obol_flags = []
            for key, flag in flags_mapping.items():
                value = group.dict().get(key)
                if value is not None:
                    obol_flags += [flag, flags_formatting.get(key, lambda x: x)(value)]
            obol_cmd = ['obol', 'group', 'add', groupname, *obol_flags]
            result = subprocess.run(
                obol_cmd,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)

            if result.returncode != 0:
                return False, f"[obol: {result}]"
            if result.stdout.decode('utf-8') != '':
                return False, f"[obol: {result}]"
        
        old_users = (old_group.users if group_exist else None) or []
        new_users = group.users or []

        users_to_add = [user for user in new_users if user not in old_users]
        users_to_remove = [user for user in old_users if user not in new_users]

        # Add users to group
        if len(users_to_add) > 0:
            obol_cmd = ['obol', 'group', 'addusers', groupname, *users_to_add]
            result = subprocess.run(
                obol_cmd,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            
            if result.returncode != 0:
                return False, f"[obol: {result}]"
            if result.stdout.decode('utf-8') != '':
                return False, f"[obol: {result}]"
        
        # Remove users from group
        if len(users_to_remove) > 0:
            obol_cmd = ['obol', 'group', 'delusers', groupname, *users_to_remove]
            result = subprocess.run(
                obol_cmd,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            
            if result.returncode != 0:
                return False, f"[obol: {result}]"
            if result.stdout.decode('utf-8') != '':
                return False, f"[obol: {result}]"
        
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
        if result.stdout.decode('utf-8') != '':
            return False, f"[cmd: {obol_cmd}][obol: {result.stdout.decode('utf-8')}]"

        return True, f"[obol: group {groupname} deleted]"
