from abc import ABC as AbstractBaseClass
from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class OSUserData(BaseModel, extra='forbid'):
    """
    This class will be used to represent OS users.
    """
    # username: str
    uid: Optional[int] = None

    groupname: Optional[str] = None
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
    groupname: str = Field(exclude=True)
    groups: List[str] = Field(exclude=True)
    last_change: int = Field(exclude=True)

class OSGroupData(BaseModel, extra='forbid'):
    """
    This class will be used to represent OS groups.
    """
    # groupname: str
    gid: Optional[int] = None
    users: Optional[List[str]] = None



class OSUserPluginInterface(AbstractBaseClass):
    """
    This class will be used to represent OS user plugins.
    """

    def list_users(self) -> (bool, List[Dict[str, OSUserData]] | str):
        """
        This method will list all OS users.
        """
        raise NotImplementedError

    def get_user(self, username: str) -> (bool, Dict[str, OSUserData]  | str):
        """
        This method will list all OS users.
        """
        raise NotImplementedError

    def update_user(self, username: str, user: OSUserUpdateData) -> (bool, str):
        """
        This method will update a OS users.
        """
        raise NotImplementedError

    def delete_user(self, username: str) -> (bool, str):
        """
        This method will delete a OS users.
        """
        raise NotImplementedError

    def list_groups(self) -> (bool, List[Dict[str, OSGroupData]]  | str):
        """
        This method will list all OS user groups.
        """
        raise NotImplementedError

    def get_group(self, groupname: str) -> (bool, Dict[str, OSGroupData] | str):
        """
        This method will list all OS groups.
        """
        raise NotImplementedError

    def update_group(self, groupname: str, group: OSGroupData) -> (bool, str):
        """
        This method will update a OS groups.
        """
        raise NotImplementedError

    def delete_group(self, groupname: str) -> (bool, str):
        """
        This method will delete a OS groups.
        """
        raise NotImplementedError
