"""
What a boot/bmc plugin actually tells the BMC.

The plugins are bash, spliced into the installer and run on the node, and the
only way to know what they do is to run them. Real hardware is rarely to hand,
so this runs each plugin's config under bash with a fake ipmitool and a fake
racadm on PATH: both keep the BMC's LAN state in a file, answer the reads from
it, apply the writes to it, and log every call. The assertions are about the
log - what was set and what was left alone - so the retry loops, the
already-set short cuts and the vendor detection all run for real.

The fakes answer in the shape the plugins parse, which is written from the
tools' documented output rather than a capture. That is the one thing this
cannot prove: if a BMC prints a field differently, the parse is still wrong
and this stays green. A captured `ipmitool lan print` and `racadm getniccfg`
replayed here would close that.
"""

import os
import stat
import subprocess

import pytest

from test_bmc_vendor_plugins import plugin, shipped

IPMITOOL = r'''#!/bin/bash
echo "ipmitool $*" >> "$SIM_LOG"
. "$SIM_STATE"
case "$1 $2" in
  "lan print")
    src="Static Address"; [ "$IPSRC" == "DHCP" ] && src="DHCP Address"
    printf 'IP Address Source       : %s\n' "$src"
    printf 'IP Address              : %s\n' "$IPADDR"
    printf 'Subnet Mask             : %s\n' "$NETMASK"
    printf 'Default Gateway IP      : %s\n' "$DEFGW"
    printf '802.1q VLAN ID          : %s\n' "$VLAN"
    ;;
  "lan set")
    case "$4" in
      ipsrc)   [ "$5" == "dhcp" ] && v=DHCP || v=Static; sed -i "s/^IPSRC=.*/IPSRC=$v/" "$SIM_STATE";;
      ipaddr)  sed -i "s/^IPADDR=.*/IPADDR=$5/" "$SIM_STATE";;
      netmask) sed -i "s/^NETMASK=.*/NETMASK=$5/" "$SIM_STATE";;
      defgw)   sed -i "s/^DEFGW=.*/DEFGW=$6/" "$SIM_STATE";;
      vlan)    [ "$6" == "off" ] && v=Disabled || v=$6; sed -i "s/^VLAN=.*/VLAN=$v/" "$SIM_STATE";;
    esac
    ;;
esac
exit 0
'''

RACADM = r'''#!/bin/bash
echo "racadm $*" >> "$SIM_LOG"
. "$SIM_STATE"
case "$1" in
  getniccfg)
    printf 'IPv4 settings:\nNIC Enabled       = 1\n'
    printf 'DHCP Enabled      = %s\n' "$RAC_DHCP"
    printf 'IP Address        = %s\n' "$RAC_IPADDR"
    printf 'Subnet Mask       = %s\n' "$RAC_NETMASK"
    printf 'Gateway           = %s\n' "$RAC_DEFGW"
    ;;
  setniccfg)
    if [ "$2" == "-d" ]; then
      sed -i "s/^RAC_DHCP=.*/RAC_DHCP=Yes/" "$SIM_STATE"
    else
      sed -i -e "s/^RAC_DHCP=.*/RAC_DHCP=No/" -e "s/^RAC_IPADDR=.*/RAC_IPADDR=$3/" \
             -e "s/^RAC_NETMASK=.*/RAC_NETMASK=$4/" -e "s/^RAC_DEFGW=.*/RAC_DEFGW=$5/" "$SIM_STATE"
    fi
    ;;
  get) case "$2" in *VLanEnable) echo "$2=Disabled";; *) echo "$2=1";; esac;;
esac
exit 0
'''

# the BMC before the plugin runs: static, on an address that is not the one Luna wants
STATE = ('IPSRC=Static\nIPADDR=10.0.0.9\nNETMASK=255.0.0.0\nDEFGW=10.0.0.1\nVLAN=Disabled\n'
         'RAC_DHCP=No\nRAC_IPADDR=10.0.0.9\nRAC_NETMASK=255.0.0.0\nRAC_DEFGW=10.0.0.1\n')

WANTED = {'IPADDRESS': '10.148.0.1', 'NETMASK': '255.255.0.0', 'GATEWAY': '10.148.0.254'}


def _fake(path, body):
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)


def run_plugin(tmp_path, name, dhcp, racadm):
    """Run one plugin's config against the fakes; return (rc, calls that changed something)."""
    bins = tmp_path / 'bin'
    bins.mkdir()
    _fake(bins / 'ipmitool', IPMITOOL)
    if racadm:
        _fake(bins / 'racadm', RACADM)
    state, log = tmp_path / 'state', tmp_path / 'log'
    state.write_text(STATE)
    log.write_text('')
    variables = ' '.join(f'{key}="{value}"' for key, value in WANTED.items())
    script = (
        'function config_bmc {\n' + plugin(name).config + '\n}\n'
        # what the installer sets before calling config_bmc
        f'NETCHANNEL=1 MGMTCHANNEL=1 USERID=2 USERNAME=admin PASSWORD=x UNMANAGED="" VLANID="" {variables}\n'
        f'DHCP="{dhcp}"\n'
        # the node has an IPMI device and no time to waste
        'modprobe() { :; }; sleep() { :; }; ls() { echo /dev/ipmi0; }\n'
        'config_bmc; echo "rc=$?" >> "$SIM_LOG"\n'
    )
    env = dict(os.environ, PATH=f'{bins}:{os.environ["PATH"]}', SIM_STATE=str(state), SIM_LOG=str(log))
    subprocess.run(['bash', '-c', script], env=env, check=False, capture_output=True, timeout=60)
    lines = log.read_text().splitlines()
    rc = int([line for line in lines if line.startswith('rc=')][-1][3:])
    writes = [line for line in lines
              if line.startswith(('ipmitool lan set', 'racadm setniccfg'))]
    return rc, writes


def _sets_an_address(call):
    return (call.startswith('ipmitool lan set') and call.split()[4] in ('ipaddr', 'netmask', 'defgw')) \
        or call.startswith('racadm setniccfg -s')


def _asks_for_dhcp(call):
    return call.endswith('ipsrc dhcp') or call == 'racadm setniccfg -d'


CASES = [(name, False) for name in shipped()] + [('dell', True)]


@pytest.mark.parametrize('name,racadm', CASES)
def test_dhcp_asks_the_bmc_for_dhcp_and_leaves_the_address_to_the_server(tmp_path, name, racadm):
    """
    Under DHCP the address, netmask and gateway are the server's to hand out.
    A plugin that sets them anyway fights the lease, and one that never asks for
    DHCP at all leaves the BMC static with the row's address - which looks fine
    until the reservation moves and the BMC does not follow.
    """
    rc, writes = run_plugin(tmp_path, name, True, racadm)
    assert rc == 0, writes
    assert any(_asks_for_dhcp(call) for call in writes), f'{name} never asked for DHCP: {writes}'
    assert not any(_sets_an_address(call) for call in writes), f'{name} set an address under DHCP: {writes}'


@pytest.mark.parametrize('name,racadm', CASES)
def test_static_sets_the_address_and_never_asks_for_dhcp(tmp_path, name, racadm):
    """The historic behaviour, pinned: static means the row's address lands on the BMC."""
    rc, writes = run_plugin(tmp_path, name, False, racadm)
    assert rc == 0, writes
    assert not any(_asks_for_dhcp(call) for call in writes), f'{name} asked for DHCP when static: {writes}'
    for field, value in WANTED.items():
        assert any(_sets_an_address(call) and value in call for call in writes), \
            f'{name} never set {field}={value}: {writes}'
