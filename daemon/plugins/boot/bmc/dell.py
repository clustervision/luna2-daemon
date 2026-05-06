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
Plugin Class :: Dell BMC

At boot/install time, prefer racadm for Dell/iDRAC systems when it is
available, and fall back to the generic ipmitool flow otherwise.

The only Dell/iDRAC-specific behavior asserted from retrieved internal
knowledge is that IPMI-over-LAN must be enabled on iDRAC for IPMI access to
work properly and that users intended for IPMI access must have sufficient
privileges. This plugin therefore explicitly enables iDRAC IPMI-over-LAN in
its racadm path before falling back to generic LAN/user programming.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


class Plugin():
    """Dell-specific boot-time BMC plugin."""

    def __init__(self):
        """
        config = segment that handles interface configuration in template
        """

    config = """
    modprobe ipmi_devintf
    modprobe ipmi_si
    modprobe ipmi_msghandler
    sleep 2

    if command -v racadm >/dev/null 2>&1
    then
        if racadm getniccfg >/dev/null 2>&1 || racadm get iDRAC.NIC.Enable >/dev/null 2>&1
        then
            RESETIDRAC=0
            RACADM_SET_MAX_ATTEMPTS=10
            RACADM_SET_RETRY_SLEEP=1
            DELL_BMC_RACADM_READY=1

            if [[ "$VLANID" == "" ]]
            then
                VLANID='Disabled'
            fi

            get_expected_value() {
                case "$1" in
                    ipaddr)
                        echo "${IPADDRESS}"
                        ;;
                    netmask)
                        echo "${NETMASK}"
                        ;;
                    defgw)
                        echo "${GATEWAY}"
                        ;;
                    vlan_enable)
                        if [[ "$VLANID" == 'Disabled' ]]; then echo 'Disabled'; else echo 'Enabled'; fi
                        ;;
                    vlan_id)
                        if [[ "$VLANID" == 'Disabled' ]]; then echo 'Disabled'; else echo "${VLANID}"; fi
                        ;;
                    ipsrc)
                        echo 'Static'
                        ;;
                esac
            }

            refresh_racadm_state() {
                RAC_NIC_RAW="$(racadm getniccfg 2>/dev/null)"
                RAC_IPADDR="$(echo "${RAC_NIC_RAW}" | awk '/IP Address/{print $4; exit}')"
                RAC_NETMASK="$(echo "${RAC_NIC_RAW}" | awk '/Subnet Mask/{print $4; exit}')"
                RAC_DEFGW="$(echo "${RAC_NIC_RAW}" | awk '/Gateway/{print $3; exit}')"
                RAC_IPSRC="$(echo "${RAC_NIC_RAW}" | awk '/DHCP Enabled/{if ($4=="No") print "Static"; else print "DHCP"; exit}')"
                RAC_VLAN_ENABLE="$(racadm get iDRAC.NIC.VLanEnable 2>/dev/null | awk -F'=' '/iDRAC.NIC.VLanEnable/{gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2; exit}')"
                RAC_VLAN_ID="$(racadm get iDRAC.NIC.VLanID 2>/dev/null | awk -F'=' '/iDRAC.NIC.VLanID/{gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2; exit}')"
                if [[ "${RAC_VLAN_ENABLE}" == "Disabled" || "${RAC_VLAN_ENABLE}" == "0" || "${RAC_VLAN_ENABLE}" == "Off" ]]
                then
                    RAC_VLAN_ID='Disabled'
                fi
            }

            get_current_value() {
                case "$1" in
                    ipaddr)
                        echo "${RAC_IPADDR}"
                        ;;
                    netmask)
                        echo "${RAC_NETMASK}"
                        ;;
                    defgw)
                        echo "${RAC_DEFGW}"
                        ;;
                    vlan_enable)
                        if [[ "${RAC_VLAN_ENABLE}" == "Enabled" || "${RAC_VLAN_ENABLE}" == "1" || "${RAC_VLAN_ENABLE}" == "On" ]]; then echo 'Enabled'; else echo 'Disabled'; fi
                        ;;
                    vlan_id)
                        echo "${RAC_VLAN_ID}"
                        ;;
                    ipsrc)
                        echo "${RAC_IPSRC}"
                        ;;
                esac
            }

            run_racadm_command() {
                case "$1" in
                    ipsrc)
                        racadm setniccfg -s ${IPADDRESS} ${NETMASK} ${GATEWAY}
                        ;;
                    ipaddr)
                        racadm setniccfg -s ${IPADDRESS} ${NETMASK} ${GATEWAY}
                        ;;
                    netmask)
                        racadm setniccfg -s ${IPADDRESS} ${NETMASK} ${GATEWAY}
                        ;;
                    defgw)
                        racadm setniccfg -s ${IPADDRESS} ${NETMASK} ${GATEWAY}
                        ;;
                    vlan_enable)
                        if [[ "$VLANID" == 'Disabled' ]]; then
                            racadm set iDRAC.NIC.VLanEnable Disabled
                        else
                            racadm set iDRAC.NIC.VLanEnable Enabled
                        fi
                        ;;
                    vlan_id)
                        if [[ "$VLANID" == 'Disabled' ]]; then
                            racadm set iDRAC.NIC.VLanEnable Disabled
                        else
                            racadm set iDRAC.NIC.VLanID ${VLANID}
                        fi
                        ;;
                esac
            }

            ensure_racadm_value() {
                local FIELD="$1"
                local EXPECTED="$(get_expected_value "${FIELD}")"
                local ATTEMPT=1
                local CURRENT_VALUE=""
                local COMMAND_RC=0
                refresh_racadm_state
                CURRENT_VALUE="$(get_current_value "${FIELD}")"
                if [[ "${CURRENT_VALUE}" == "${EXPECTED}" ]]
                then
                    echo "Luna2: Dell BMC ${FIELD} already set to ${CURRENT_VALUE} through racadm"
                    return 0
                fi
                RESETIDRAC=1
                while [[ "${ATTEMPT}" -le "${RACADM_SET_MAX_ATTEMPTS}" ]]
                do
                    echo "Luna2: Dell racadm apply ${FIELD} attempt ${ATTEMPT}/${RACADM_SET_MAX_ATTEMPTS}"
                    run_racadm_command "${FIELD}"
                    COMMAND_RC=$?
                    sleep "${RACADM_SET_RETRY_SLEEP}"
                    refresh_racadm_state
                    CURRENT_VALUE="$(get_current_value "${FIELD}")"
                    if [[ "${CURRENT_VALUE}" == "${EXPECTED}" ]]
                    then
                        echo "Luna2: Dell BMC ${FIELD} now set to ${CURRENT_VALUE} through racadm"
                        return 0
                    fi
                    if [[ "${COMMAND_RC}" -ne 0 ]]
                    then
                        echo "Luna2: Dell racadm command for ${FIELD} returned ${COMMAND_RC}" >&2
                    fi
                    echo "Luna2: Dell BMC ${FIELD} currently '${CURRENT_VALUE}', waiting for '${EXPECTED}'" >&2
                    ATTEMPT=$((ATTEMPT+1))
                done
                echo "Luna2: Dell racadm failed to set ${FIELD} to ${EXPECTED}" >&2
                return 1
            }

            echo "Luna2: Dell racadm detected, configuring iDRAC"
            racadm set iDRAC.IPMILan.Enable 1 >/dev/null 2>&1 || true
            racadm set iDRAC.NIC.Enable 1 >/dev/null 2>&1 || true

            ensure_racadm_value ipsrc || DELL_BMC_RACADM_READY=0
            if [[ "${DELL_BMC_RACADM_READY}" == "1" ]]; then ensure_racadm_value ipaddr || DELL_BMC_RACADM_READY=0; fi
            if [[ "${DELL_BMC_RACADM_READY}" == "1" ]]; then ensure_racadm_value netmask || DELL_BMC_RACADM_READY=0; fi
            if [[ "${DELL_BMC_RACADM_READY}" == "1" ]]; then ensure_racadm_value defgw || DELL_BMC_RACADM_READY=0; fi
            if [[ "${DELL_BMC_RACADM_READY}" == "1" ]]; then ensure_racadm_value vlan_enable || DELL_BMC_RACADM_READY=0; fi
            if [[ "${DELL_BMC_RACADM_READY}" == "1" && "$VLANID" != 'Disabled' ]]; then ensure_racadm_value vlan_id || DELL_BMC_RACADM_READY=0; fi

            if [[ "${DELL_BMC_RACADM_READY}" == "1" ]]
            then
                echo "Luna2: Dell racadm configuring BMC user id ${USERID} name ${USERNAME}"
                racadm set iDRAC.Users.${USERID}.UserName ${USERNAME} >/dev/null 2>&1 || DELL_BMC_RACADM_READY=0
                racadm set iDRAC.Users.${USERID}.Password ${PASSWORD} >/dev/null 2>&1 || DELL_BMC_RACADM_READY=0
                racadm set iDRAC.Users.${USERID}.Enable 1 >/dev/null 2>&1 || DELL_BMC_RACADM_READY=0
                racadm set iDRAC.Users.${USERID}.IpmiLanPrivilege 4 >/dev/null 2>&1 || true
                racadm set iDRAC.Users.${USERID}.Privilege 511 >/dev/null 2>&1 || true
            fi

            case $UNMANAGED in
                disable)
                    echo "Luna2: Dell racadm path requested disable unmanaged users; leaving explicit cleanup to ipmitool fallback-compatible flow"
                    ;;
                delete)
                    echo "Luna2: Dell racadm path requested delete unmanaged users; deletion not implemented in racadm path"
                    ;;
            esac

            if [[ "${DELL_BMC_RACADM_READY}" == "1" && "${RESETIDRAC}" == "1" ]]
            then
                echo "Luna2: Dell racadm applying iDRAC reset"
                racadm racreset >/dev/null 2>&1 || true
            fi
        else
            DELL_BMC_RACADM_READY=0
        fi
    else
        DELL_BMC_RACADM_READY=0
    fi

    if [[ "${DELL_BMC_RACADM_READY}" != "1" ]]
    then
        echo "Luna2: falling back to generic ipmitool BMC configuration"
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
                            if [ "$VLANID" == 'Disabled' ]; then
                                ipmitool lan set ${NETCHANNEL} vlan id off
                            else
                                ipmitool lan set ${NETCHANNEL} vlan id ${VLANID}
                            fi
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
                VLANID='Disabled'
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
    fi
    """
