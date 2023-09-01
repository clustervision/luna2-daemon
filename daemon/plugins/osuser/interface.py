from abc import ABC as AbstractBaseClass
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class OSUser(AbstractBaseClass):
    """
    This class will be used to represent OS users.
    """
    username: str
    password: Optional[str] = field(default=None, repr=False)
    group: Optional[str] = field(default=None, repr=False)
    groups: Optional[List[str]] = field(default=None, repr=False)
    uid: Optional[int] = field(default=None, repr=False)
    gid: Optional[int] = field(default=None, repr=False)
    surname: Optional[str] = field(default=None, repr=False)
    givenname: Optional[str] = field(default=None, repr=False)
    email: Optional[str] = field(default=None, repr=False)
    phone: Optional[str] = field(default=None, repr=False)
    shell: Optional[str] = field(default=None, repr=False)
    homedir: Optional[str] = field(default=None, repr=False)
    expire: Optional[int] = field(default=None, repr=False)
    last_change: Optional[int] = field(default=None, repr=False)

    def to_json(self):
        """
        This method will convert the object to json.
        """
        return {
            'username': self.username,
            'password': self.password,
            'group': self.group,
            'groups': self.groups,
            'uid': self.uid,
            'gid': self.gid,
            'surname': self.surname,
            'givenname': self.givenname,
            'email': self.email,
            'phone': self.phone,
            'shell': self.shell,
            'homedir': self.homedir,
            'expire': self.expire,
            'last_change': self.last_change
        }

@dataclass
class OSGroup(object):
    """
    This class will be used to represent OS groups.
    """
    groupname: str
    gid: Optional[int] = field(default=None, repr=False)
    users: Optional[List[str]] = field(default=None, repr=False)

    def to_json(self):
        """
        This method will convert the object to json.
        """
        return {
            'groupname': self.groupname,
            'gid': self.gid,
            'users': self.users
        }

class OSUserPluginInterface(AbstractBaseClass):
    """
    This class will be used to represent OS user plugins.
    """

    def list_users(self) -> (bool, List[OSUser] | str):
        """
        This method will list all OS users.
        """
        raise NotImplementedError

    def get_user(self, username: str) -> (bool, OSUser | str):
        """
        This method will list all OS users.
        """
        raise NotImplementedError

    def update_user(self, username: str, user: OSUser) -> (bool, str):
        """
        This method will update a OS users.
        """
        raise NotImplementedError

    def delete_user(self, username: str) -> (bool, str):
        """
        This method will delete a OS users.
        """
        raise NotImplementedError

    def list_groups(self) -> (bool, List[OSGroup] | str):
        """
        This method will list all OS user groups.
        """
        raise NotImplementedError

    def get_group(self, groupname: str) -> (bool, OSGroup | str):
        """
        This method will list all OS groups.
        """
        raise NotImplementedError

    def update_group(self, groupname: str, group: OSGroup) -> (bool, str):
        """
        This method will update a OS groups.
        """
        raise NotImplementedError

    def delete_group(self, groupname: str) -> (bool, str):
        """
        This method will delete a OS groups.
        """
        raise NotImplementedError
