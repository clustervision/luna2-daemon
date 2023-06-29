#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Plugin Class ::  Default BMC
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2023, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


class Plugin():
    """
    This is default class for BMC, for plugin operations.
    """

    def __init__(self):
        """
        config = segment that handles interface configuration in template
        """

    config = """
    modprobe ipmi_devintf
    modprobe ipmi_si
    modprobe ipmi_msghandler
    sleep 2
    if ls /dev/ipmi* 1> /dev/null 2>&1
    then
        RESETIPMI=0
        IPMITOOL="`ipmitool lan print`"
        CUR_IPSRC=`echo "${IPMITOOL}" | grep -e "^IP Address Source" | awk '{ print $5 }'`
        CUR_IPADDR=`echo "${IPMITOOL}" | grep -e "^IP Address.*: [0-9]" | awk '{ print $4 }'`
        CUR_NETMASK=`echo "${IPMITOOL}" | grep -e "^Subnet Mask" | awk '{ print $4 }'`
        CUR_DEFGW=`echo "${IPMITOOL}" | grep -e "^Default Gateway IP" | awk '{ print $5 }'`
        if [[ "${CUR_IPSRC}" != "Static" ]]
        then
            RESETIPMI=1
            ipmitool lan set $NETCHANNEL ipsrc static
        fi
        if [[ "${CUR_IPADDR}" != "${IPADDRESS}" ]]
        then
            RESETIPMI=1
            ipmitool lan set ${NETCHANNEL} ipaddr ${IPADDRESS}
        fi
        if [[ "${CUR_NETMASK}" != "${NETMASK}" ]]
        then
            RESETIPMI=1
            ipmitool lan set ${NETCHANNEL} netmask ${NETMASK}
        fi
        if [[ "${CUR_DEFGW}" != "0.0.0.0" ]]
        then
            RESETIPMI=1
            ipmitool lan set ${NETCHANNEL} defgw ipaddr 0.0.0.0
        fi
        case $UNMANAGED in
            delete)
                for userid in $(ipmitool user list 1|grep -oE '^[0-9]+\s{1,10}.[^ ]+'|grep -oE '^[0-9]+'); do
                    ipmitool user disable $userid
                done
                ;;
            disable)
                for userid in $(ipmitool user list 1|grep -oE '^[0-9]+\s{1,10}.[^ ]+'|grep -oE '^[0-9]+'); do
                    ipmitool user disable $userid
                done
                ;;
        esac
        ipmitool user set name ${USERID} ${USERNAME}
        ipmitool user set password ${USERID} ${PASSWORD}
        ipmitool channel setaccess ${MGMTCHANNEL} ${USERID} link=on ipmi=on callin=on privilege=4
        ipmitool user enable ${USERID}
        if [[ "${RESETIPMI}" == "1" ]]
        then
            ipmitool mc reset cold
        fi
    fi
    """
