#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

"""
Plugin Class ::  Default BMC
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
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
        IPMI_SET_MAX_ATTEMPTS=10
        IPMI_SET_RETRY_SLEEP=1

        refresh_ipmi_state() {
            IPMITOOL="$(ipmitool lan print ${NETCHANNEL} 2>/dev/null)"
            CUR_IPSRC="$(echo "${IPMITOOL}" | grep -e "^IP Address Source" | awk '{ print $5 }')"
            CUR_IPADDR="$(echo "${IPMITOOL}" | grep -e "^IP Address.*: [0-9]" | awk '{ print $4 }')"
            CUR_NETMASK="$(echo "${IPMITOOL}" | grep -e "^Subnet Mask" | awk '{ print $4 }')"
            CUR_DEFGW="$(echo "${IPMITOOL}" | grep -e "^Default Gateway IP" | awk '{ print $5 }')"
            CUR_VLANID="$(echo "${IPMITOOL}" | grep -e "^802.1q VLAN ID" | awk '{ print $5 }')"
        }

        get_current_ipmi_value() {
            case "$1" in
                ipsrc)
                    echo "${CUR_IPSRC}"
                    ;;
                ipaddr)
                    echo "${CUR_IPADDR}"
                    ;;
                netmask)
                    echo "${CUR_NETMASK}"
                    ;;
                defgw)
                    echo "${CUR_DEFGW}"
                    ;;
                vlan)
                    echo "${CUR_VLANID}"
                    ;;
            esac
        }

        get_expected_ipmi_value() {
            case "$1" in
                ipsrc)
                    echo "Static"
                    ;;
                ipaddr)
                    echo "${IPADDRESS}"
                    ;;
                netmask)
                    echo "${NETMASK}"
                    ;;
                defgw)
                    echo "${GATEWAY}"
                    ;;
                vlan)
                    echo "${VLANID}"
                    ;;
            esac
        }

        run_ipmi_command() {
            local FIELD="$1"
            local RUN_INDEX=1
            local RUN_COUNT=1
            local COMMAND_RC=0
            case "${FIELD}" in
                ipaddr)
                    RUN_COUNT=2
                    ;;
            esac
            while [[ "${RUN_INDEX}" -le "${RUN_COUNT}" ]]
            do
                case "${FIELD}" in
                    ipsrc)
                        ipmitool lan set ${NETCHANNEL} ipsrc static
                        ;;
                    ipaddr)
                        ipmitool lan set ${NETCHANNEL} ipaddr ${IPADDRESS}
                        ;;
                    netmask)
                        ipmitool lan set ${NETCHANNEL} netmask ${NETMASK}
                        ;;
                    defgw)
                        ipmitool lan set ${NETCHANNEL} defgw ipaddr ${GATEWAY}
                        ;;
                    vlan)
                        ipmitool lan set ${NETCHANNEL} vlan id ${VLANID}
                        ;;
                esac
                COMMAND_RC=$?
                if [[ "${COMMAND_RC}" -ne 0 ]]
                then
                    return ${COMMAND_RC}
                fi
                RUN_INDEX=$((RUN_INDEX+1))
            done
            return 0
        }

        set_ipmi_value() {
            local FIELD="$1"
            local EXPECTED="$(get_expected_ipmi_value "${FIELD}")"
            local ATTEMPT=1
            local CURRENT_VALUE=""
            local COMMAND_RC=0
            echo "Luna2: configuring BMC ${FIELD} to ${EXPECTED}"
            while [[ "${ATTEMPT}" -le "${IPMI_SET_MAX_ATTEMPTS}" ]]
            do
                echo "Luna2: applying ${FIELD} attempt ${ATTEMPT}/${IPMI_SET_MAX_ATTEMPTS}"
                run_ipmi_command "${FIELD}"
                COMMAND_RC=$?
                sleep "${IPMI_SET_RETRY_SLEEP}"
                refresh_ipmi_state
                CURRENT_VALUE="$(get_current_ipmi_value "${FIELD}")"
                if [[ "${CURRENT_VALUE}" == "${EXPECTED}" ]]
                then
                    echo "Luna2: BMC ${FIELD} now set to ${CURRENT_VALUE}"
                    return 0
                fi
                echo "Luna2: BMC ${FIELD} currently '${CURRENT_VALUE}', waiting for '${EXPECTED}'"
                if [[ "${COMMAND_RC}" -ne 0 ]]
                then
                    echo "Luna2: ipmitool command for ${FIELD} returned ${COMMAND_RC} on attempt ${ATTEMPT}/${IPMI_SET_MAX_ATTEMPTS}" >&2
                fi
                ATTEMPT=$((ATTEMPT+1))
            done
            echo "Luna2: failed to set IPMI ${FIELD} to ${EXPECTED} after ${IPMI_SET_MAX_ATTEMPTS} attempts; current value is ${CURRENT_VALUE}" >&2
            return 1
        }

        ensure_ipmi_value() {
            local FIELD="$1"
            local EXPECTED="$(get_expected_ipmi_value "${FIELD}")"
            local CURRENT_VALUE="$(get_current_ipmi_value "${FIELD}")"
            if [[ "${CURRENT_VALUE}" == "${EXPECTED}" ]]
            then
                echo "Luna2: BMC ${FIELD} already set to ${CURRENT_VALUE}"
                return 0
            fi
            RESETIPMI=1
            set_ipmi_value "${FIELD}"
        }

        if [[ "$VLANID" == "" ]]
        then
            VLANID='off'
        fi

        echo "Luna2: starting BMC configuration on net channel ${NETCHANNEL}"
        refresh_ipmi_state

        ensure_ipmi_value ipsrc || return 1
        ensure_ipmi_value ipaddr || return 1
        ensure_ipmi_value netmask || return 1
        ensure_ipmi_value defgw || return 1
        ensure_ipmi_value vlan || return 1

        case $UNMANAGED in
            disable)
                echo "Luna2: disabling unmanaged BMC users mode=${UNMANAGED}"
                for userid in $(ipmitool user list 1|grep -oE '^[0-9]+\s{1,10}.[^ ]+'|grep -oE '^[0-9]+'); do
                    ipmitool user disable $userid
                done
                ;;
            delete)
                echo "Luna2: disabling unmanaged BMC users mode=${UNMANAGED}. deletion pending feature"
                for userid in $(ipmitool user list 1|grep -oE '^[0-9]+\s{1,10}.[^ ]+'|grep -oE '^[0-9]+'); do
                    ipmitool user disable $userid
                done
                ;;
        esac
        echo "Luna2: configuring BMC user id ${USERID} name ${USERNAME} on management channel ${MGMTCHANNEL}"
        ipmitool user set name ${USERID} ${USERNAME}
        echo "Luna2: setting BMC password for user id ${USERID} (value hidden)"
        ipmitool user set password ${USERID} ${PASSWORD}
        echo "Luna2: enabling BMC channel access for user id ${USERID} on management channel ${MGMTCHANNEL}"
        ipmitool channel setaccess ${MGMTCHANNEL} ${USERID} link=on ipmi=on callin=on privilege=4
        echo "Luna2: enabling BMC user id ${USERID}"
        ipmitool user enable ${USERID}
        if [[ "${RESETIPMI}" == "1" ]]
        then
            echo "Luna2: issuing BMC cold reset"
            ipmitool mc reset cold
        fi
    else
        echo "Luna2: BMC not ready or not available - skipping config"
    fi
    """
