#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This code is part of the TrinityX software suite
# Copyright (C) 2025  ClusterVision Solutions b.v.
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
Client/daemon compatibility across versions.

A cluster is upgraded in pieces: the controller moves first, the osimages follow
whenever someone rebuilds them. So all four combinations are live in the field, and
three of them mix versions:

  old client + old daemon   the baseline
  old client + NEW daemon   an osimage nobody has rebuilt yet, booting off a 2.2
                            controller. Must install exactly as it did before.
  NEW client + old daemon   a rebuilt osimage booting off a controller still on 2.1.
                            Must install; the lpart tooling simply goes unused.
  NEW client + NEW daemon   the target.

The node's whole coupling to the daemon is two calls -- a token from /tpm/<node>, then
/boot/install/<node>, whose body it executes. So compatibility comes down to what that
rendered script contains, and these tests pin the properties that keep it safe:

  * the classic installer never mentions the install-model variables, so a 2.2 daemon
    passing three extra render variables cannot change a byte of what an old client
    receives;
  * an unset or 'legacy' install_mode keeps the classic installer, so an osimage that
    predates lpart is never handed an installer it cannot run;
  * when someone does point a pre-lpart osimage at the lpart installer, it fails loudly
    up front rather than part-way through partitioning a disk.
"""

import difflib
import os
import re
import shutil
import subprocess

import pytest

DAEMON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'daemon'
)
TEMPLATES = os.path.join(DAEMON, 'templates')
CLASSIC = os.path.join(TEMPLATES, 'templ_install.cfg')
LPART = os.path.join(TEMPLATES, 'templ_install_lpart.cfg')
BOOT = os.path.join(DAEMON, 'base', 'boot.py')

INSTALL_MODEL_VARS = ['LUNA_INSTALL_MODE', 'LUNA_DISKLAYOUT_B64', 'LUNA_OSIMAGE_FILTER_B64']


def _read(path):
    with open(path, encoding='utf-8') as handle:
        return handle.read()


# One render context, so a test that wants a particular branch overrides rather than
# keeping its own copy -- two copies drift and each test then proves something slightly
# different from what it says it proves.
RENDER_CONTEXT = dict(
    LUNA_CONTROLLER='10.0.0.1', LUNA_BEACON='10.0.0.1', LUNA_API_PORT='7050',
    LUNA_API_PROTOCOL='https', VERIFY_CERTIFICATE='False', WEBSERVER_PORT='7060',
    WEBSERVER_PROTOCOL='http', LUNA_LOGHOST='10.0.0.1', NODE_HOSTNAME='n1',
    NODE_NAME='n1', LUNA_GROUP='compute', LUNA_OSIMAGE='img',
    LUNA_DISTRIBUTION='redhat', LUNA_OSRELEASE='9', LUNA_SYSTEMROOT='sysroot',
    LUNA_IMAGEFILE='f.tar.bz2', LUNA_FILE='f.tar.bz2', LUNA_SELINUX_ENABLED='0',
    LUNA_SETUPBMC=False, LUNA_HOLD_SECONDS=0, LUNA_HOLD_REASON='', LUNA_BMC={}, LUNA_ROLES='', LUNA_SCRIPTS='',
    LUNA_UNMANAGED_BMC_USERS='', LUNA_INTERFACES={}, LUNA_PRESCRIPT='',
    LUNA_PARTSCRIPT='', LUNA_POSTSCRIPT='', PROVISION_METHOD='torrent',
    PROVISION_FALLBACK='http', PROVISION_INTERFACE='BOOTIF',
)


def _render(path, **overrides):
    """Render a template the way the daemon does, including its b64decode filter."""
    from base64 import b64decode

    from jinja2 import Environment

    def _b64decode(value):
        try:
            decoded = b64decode(value)
        except Exception:                                   # noqa: BLE001 - mirrors the daemon
            return value
        try:
            return decoded.decode('ascii')
        except Exception:                                   # noqa: BLE001
            return decoded.decode('utf-8', 'replace')

    env = Environment()                                     # noqa: S701 - not HTML
    env.filters['b64decode'] = _b64decode
    return env.from_string(_read(path)).render(**dict(RENDER_CONTEXT, **overrides))


@pytest.mark.parametrize('variable', INSTALL_MODEL_VARS)
def test_classic_installer_never_mentions_the_install_model(variable):
    """
    OLD CLIENT + NEW DAEMON.

    The 2.2 boot route passes three extra variables to every install render. That is
    only harmless while the classic template never references them -- the moment one
    appears here, an osimage nobody has rebuilt starts receiving a different script
    from the same daemon.
    """
    assert variable not in _read(CLASSIC), (
        f'{variable} appears in the classic installer. An osimage that predates the '
        f'install-model would then get a different script from a 2.2 daemon than it '
        f'got from a 2.1 one, which is the compatibility guarantee this work rests on.'
    )


def test_classic_render_is_unaffected_by_the_extra_variables():
    """
    OLD CLIENT + NEW DAEMON, proven by rendering rather than by reading.

    Render the real classic template with the 2.1 variable set and with the 2.2 set,
    through the daemon's own b64decode filter, and require identical bytes.
    """
    old = _render(CLASSIC)
    # what a 2.2 daemon adds, including for a node someone has given lpart values
    new = _render(CLASSIC, LUNA_INSTALL_MODE='full', LUNA_DISKLAYOUT_B64='eyJ2IjoyfQ==',
                  LUNA_OSIMAGE_FILTER_B64='e30=')

    assert old == new, (
        'the classic installer renders differently once the install-model variables are '
        'supplied, so a 2.2 daemon would hand an un-rebuilt osimage a script it has '
        'never seen.'
    )


def test_unset_install_mode_keeps_the_classic_installer():
    """
    OLD CLIENT + NEW DAEMON: nothing may opt a node in by omission.

    The switch must require a value that is set AND not 'legacy'. A bare
    `!= 'legacy'` test would route every node that never heard of the field, because
    the cascade default resolves rather than staying empty.
    """
    source = _read(BOOT)
    match = re.search(r'^\s*if not method and (.+?):\s*$', source, re.M)
    assert match, 'the lpart selection condition is not where this test expects it'
    condition = match.group(1)
    assert "data.get('install_mode')" in condition, (
        'the selection does not require install_mode to be set; an unset field must '
        'never select the lpart installer'
    )
    assert "!= 'legacy'" in condition, 'the selection no longer excludes legacy'


def test_lpart_installer_falls_back_when_the_osimage_cannot_run_it():
    """
    NEW DAEMON + OLD CLIENT, when someone opts a node in anyway.

    An osimage built before lpart has no lpart-node-installer. The installer decides
    this itself -- whether lpart is runnable is a property of the initramfs the node
    booted, which the daemon cannot see into -- reports it, and installs the classic
    way rather than looping on an error.

    The report is the part that matters: the node ends up with the layout partscript
    produced, NOT the lpart layout that was asked for, so the run must say so.
    """
    lpart = _read(LPART)
    assert 'command -v lpart-node-installer' in lpart, (
        'the lpart installer does not check that the osimage can actually run lpart'
    )
    guard = lpart.split('command -v lpart-node-installer')[1].split('LPART_FALLBACK=1')[0]
    assert 'install.lpart_unavailable' in guard, (
        'the fallback does not report a distinct status, so a node silently installed '
        'with the wrong disk layout looks identical to one that got what it asked for'
    )
    # The human-readable warning is echoed, not pushed through update_status: that field
    # is the node's *state* and the next step overwrites it, so a sentence does not belong
    # there. The echo lands on the install console and in the node's install log.
    echoed = '\n'.join(line for line in guard.splitlines() if line.strip().startswith('echo'))
    for phrase in ('FALLING BACK', 'NOT the', 'requested lpart layout',
                   'install_mode=legacy', 'lpart-node-installer'):
        assert phrase in echoed, f'the install output does not state: {phrase}'
    # ...and the state stays short, because a state is not a message
    states = re.findall(r'update_status "([^"]+)"', guard)
    assert states == ['install.lpart_unavailable'], (
        f'expected exactly one short state, got {states}. update_status sets the node '
        f'state and is overwritten by the next step; it is not a place for prose.'
    )
    assert 'lpart_phase' in lpart.split('command -v lpart-node-installer')[0][-500:], (
        'the capability check should sit inside lpart_phase, so every phase is covered'
    )


def test_lpart_is_never_reachable_without_the_daemon_choosing_it():
    """
    NEW CLIENT + OLD DAEMON.

    A 2.1 daemon renders the classic installer, which must contain no route into the
    lpart tooling -- otherwise a rebuilt osimage on an old controller could start a
    partitioning run nothing wrote inputs for.
    """
    classic = _read(CLASSIC)
    for token in ('lpart-node-installer', 'lpart_phase', 'lpart-phase'):
        assert token not in classic, (
            f'the classic installer references {token}. On a 2.1 controller that is the '
            f'only script a rebuilt osimage gets, and lpart would run with no '
            f'provisioning inputs written.'
        )

# The classic installer's shape, blessed against `development` as of the 2.2 merge.
# This is the compatibility guarantee expressed at the level that actually matters:
# not "the file is byte-identical" -- which the first legitimate fix breaks -- but
# "an old client is handed the same functions, called in the same order".
CLASSIC_FUNCTIONS = {
    'bmcsetup',
    'hold_for_daemon',
    'change_net',
    'cleanup',
    'collect_mac_n_name_net',
    'config_bmc',
    'config_dns',
    'config_dns_ipv6',
    'config_gateway',
    'config_gateway_ipv6',
    'config_hostname',
    'config_interface',
    'config_interface_ipv6',
    'config_network_init',
    'customscript',
    'download_image',
    'dynamic_ip_check',
    'fix_capabilities',
    'get_encapsulated_content',
    'get_interface_by_mac',
    'get_json_segment',
    # TRIX-1209: exact-key token extraction for the owner/mode attributes; the loose
    # matcher above it false-hits base64 content that happens to contain a key name
    'get_json_exact',
    # TRIX-1968: profiles - files plus a service action, applied at install time
    'node_profiles',
    'lunainit',
    'node_roles',
    'node_scripts',
    'node_secrets',
    'partscript',
    'postboot',
    'postscript',
    'prescript',
    'restore_selinux_context',
    'unpack_imagefile',
    'update_inventory',
    'update_node_ip',
    'update_status',
}
CLASSIC_FLOW = [
    'lunainit', 'dynamic_ip_check', 'node_scripts', 'prescript', 'bmcsetup',
    # TRIX-2035: right after setupbmc the node holds the LUNA_HOLD_SECONDS the
    # daemon rendered, so a reset from a scheduled restore or BIOS push lands in
    # the hold, not mid-install. Zero, and no wait, when nothing is scheduled
    'hold_for_daemon',
    # TRIX-143: hardware discovery moved up from the end of the install, deliberately.
    # update_system_info was removed beside it: it ran dmidecode a second time to POST
    # a vendor and an assettag that update_inventory already sends as manufacturer and
    # serial. The daemon now derives the node's two columns from the snapshot, so they
    # also refresh on an out-of-band collection instead of only at install.
    # Everything it reads is available in the installer environment, so waiting for the
    # image gains nothing - and loses the inventory for every node whose install fails
    # after this point, which is the node somebody most needs the facts for. Before
    # partscript, so the disks are recorded as found rather than as repartitioned; and
    # before download_image, so a discovery boot can be acted on without first paying
    # for an image nobody has decided on yet
    'update_inventory',
    'partscript', 'download_image', 'unpack_imagefile', 'collect_mac_n_name_net',
    'change_net', 'node_secrets', 'postscript', 'node_roles',
    # TRIX-1968: profiles apply after roles; the call renders only for a node with
    # profiles assigned, so an unassigned node keeps its installer byte-identical
    'node_profiles',
    'postboot',
    'fix_capabilities', 'restore_selinux_context',
    'cleanup', 'update_status',
]


def _functions(path):
    """The template's own functions, name -> the comment above it plus its body.

    The leading comment counts as part of the function. It carries the *why*, it is
    what a reader reaches for first, and it is the half that goes missing when a
    function is copied between these two files -- a body-only comparison called the
    copy identical while the explanation above it had been left behind.
    """
    out, name, body, pending = {}, None, [], []
    for line in _read(path).splitlines():
        match = re.match(r'^function ([a-z_][a-z0-9_]*)\s*\{', line)
        if match:
            name, body = match.group(1), list(pending)
            pending = []
            continue
        if name is None:
            pending = pending + [line] if line.startswith('#') else []
            continue
        if line == '}':
            out[name] = '\n'.join(body)
            name = None
        else:
            body.append(line)
    return out


def _classic_functions():
    return set(_functions(CLASSIC))


def _flow(path):
    """Calls to the template's own functions, in order.

    Only names the template defines count. The tail is ordinary bash and also holds
    plain commands -- the lpart one guards two calls with `[ ... ] &&` -- whose first
    word is not a step in the flow. Deriving the set from the function definitions
    rather than listing exclusions means a function added or renamed is still seen and
    nothing else has to be anticipated. Lines that are not function calls are not lost
    to the suite: the whole-file comparison below sees every one of them.
    """
    tail = _read(path).split('echo "Luna2: installer script"')[-1]
    functions = _functions(path)
    out = []
    for line in tail.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(('#', 'echo', '{%', '{{')):
            continue
        for word in stripped.split():
            if word in functions:
                out.append(word)
                break
    return out


def _classic_flow():
    return _flow(CLASSIC)


def test_classic_installer_offers_the_same_functions():
    """
    OLD CLIENT + NEW DAEMON, pinned by behaviour rather than by hash.

    templ_install.cfg was byte-identical to development until the first legitimate
    fix landed in it. Bytes were never the property worth protecting -- this is: an
    osimage nobody has rebuilt must be handed the same installer it has always had.
    A function added, removed or renamed here changes what that node runs.
    """
    found = _classic_functions()
    assert found == CLASSIC_FUNCTIONS, (
        f'the classic installer\'s function set changed: '
        f'added {sorted(found - CLASSIC_FUNCTIONS)}, removed {sorted(CLASSIC_FUNCTIONS - found)}. '
        f'If that is intended, re-bless the list here in the same commit and say why -- '
        f'it is a change to what every un-rebuilt osimage executes.'
    )


def test_classic_installer_runs_them_in_the_same_order():
    """The call list is the installer's actual behaviour; order is the contract."""
    assert _classic_flow() == CLASSIC_FLOW, (
        f'the classic installer\'s execution order changed:\n'
        f'  expected: {CLASSIC_FLOW}\n'
        f'  found:    {_classic_flow()}'
    )


# Where the classic installer's content legitimately comes from, most specific first.
# The branch that owned this file has merged, so development carries its content and is
# the baseline again. Naming a feature branch ahead of its merge is what this list used
# to do, and it does not survive: the branch was renamed, the ref stopped resolving, and
# a ref that does not resolve falls through to the next entry silently rather than
# failing -- so the comparison quietly changed what it was comparing against.
CLASSIC_BASELINES = (
    'origin/development',
    'development',
)


def _baseline_classic_template():
    """The classic installer as it stands on the branch that owns it.

    Returns (ref, text), or None when no baseline can be read -- a shallow clone, an
    exported tree, no git at all -- so the test skips rather than failing for reasons
    that have nothing to do with the installer.
    """
    for ref in CLASSIC_BASELINES:
        try:
            result = subprocess.run(
                ['git', 'show', f'{ref}:daemon/templates/templ_install.cfg'],
                cwd=os.path.dirname(DAEMON), capture_output=True, timeout=30
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode == 0:
            return ref, result.stdout.decode('utf-8')
    return None


# Every line by which the classic installer differs from its owner, enumerated in both
# directions -- a line that is *changed* is a removal and an addition, and listing only
# what appeared would wave the other half through.
#
# Both are empty, and that is the healthy state: the file here is byte-identical to the
# one on the baseline branch. They were not empty while this branch's changes to the
# classic installer were still unmerged, and emptying them is what landing those changes
# means - the baseline moves, and a difference that has been ported is no longer a
# difference to bless. The reasons that used to sit here are in the history of the
# branch that now carries the lines.
#
# When a legitimate divergence appears again, list it here with the reason, in whichever
# direction it falls, and delete the entry once it lands on the baseline. What must never
# be listed is a difference nobody meant: every osimage that has not been rebuilt runs
# this file, so a line lost here changes nodes nobody has touched.
BLESSED_CLASSIC_REMOVALS = []
# TRIX-2035: hold_for_daemon and its call after bmcsetup - the install waits the
# LUNA_HOLD_SECONDS the daemon rendered (0 when nothing is scheduled) so a reset
# from a scheduled restore or BIOS push lands in the hold, not mid-install. Delete this
# block when the lines land on the baseline.
BLESSED_CLASSIC_ADDITIONS = [
    '',
    'function hold_for_daemon {',
    '    # A restore owed by a firmware flash, or a BIOS push, scheduled for this node',
    '    # resets it. The daemon decided at render time whether one is, and how long to',
    '    # hold so that the reset lands here rather than in the middle of the install.',
    '    # Fixed and bounded: nothing is asked of the daemon, and it ends regardless.',
    '    if [ "{{ LUNA_HOLD_SECONDS }}" -gt 0 ] 2>/dev/null; then',
    '        echo "Luna2: {{ LUNA_HOLD_REASON }} for this node and may reset it; holding {{ LUNA_HOLD_SECONDS }}s so that reset does not land mid-install"',
    '        sleep {{ LUNA_HOLD_SECONDS }}',
    '    fi',
    '}',
    'hold_for_daemon',
]


def test_classic_installer_only_differs_from_its_owner_by_what_we_blessed():
    """The classic path is not ours to change, and the whole file says so.

    The blessed function and flow lists above catch a function appearing, vanishing or
    moving. They cannot see a line changing *inside* one -- and that is exactly how the
    classic installer drifted once: a single `exit 1` became `exit $LUNARET`, carried in
    from the campaign's abandoned model where lpart ran inside the operator's script
    fields. Structurally identical, behaviourally different, and invisible to every
    other test here.

    So this compares the whole file against the branch that owns it, in both directions.
    Every line we add and every line we drop is listed above with its reason, rather
    than tolerated by a loose rule -- and both lists matter, because changing a line
    shows up as one of each and checking only the additions would pass half of it.

    Another ticket's changes to this file are welcome and are not blessed here: they
    are ported commit-for-commit, so they land in the baseline as well as here and
    never show up as a difference. That is the point -- carrying someone else's work
    as a diff we approve of is exactly how the ownership gets lost.
    """
    baseline = _baseline_classic_template()
    if baseline is None:
        pytest.skip('no baseline branch available in this checkout')
    ref, original = baseline
    with open(CLASSIC, 'r', encoding='utf-8') as handle:
        current = handle.read()
    diff = list(difflib.unified_diff(
        original.splitlines(), current.splitlines(), lineterm='', n=0
    ))
    added = [line[1:] for line in diff if line.startswith('+') and not line.startswith('+++')]
    removed = [line[1:] for line in diff if line.startswith('-') and not line.startswith('---')]
    assert removed == BLESSED_CLASSIC_REMOVALS, (
        f'the classic installer dropped or altered lines that {ref} has and nobody '
        f'blessed:\n  expected: {BLESSED_CLASSIC_REMOVALS}\n  found:    {removed}\n'
        f'Every osimage that has not been rebuilt executes this file, so a line lost '
        f'here changes nodes nobody has touched. If this is a port that fell behind, '
        f'finish the port rather than blessing the gap.'
    )
    assert added == BLESSED_CLASSIC_ADDITIONS, (
        f'the classic installer gained lines that {ref} does not have and nobody '
        f'blessed:\n  expected: {BLESSED_CLASSIC_ADDITIONS}\n  found:    {added}\n'
        f'Changes to the classic installer belong to whoever owns it -- land them '
        f'there and port them, rather than blessing them here.'
    )


# The lpart installer is a fork of the classic one. It exists to insert three lpart
# steps into the same sequence; everything else is meant to be the same code, and the
# fallback path inside it *is* the classic installer, so a divergence is not a variant
# but a bug in the path we promise is unchanged.
LPART_ONLY_FUNCTIONS = {'lpart_phase', 'write_provisioning_inputs'}


def test_the_two_installers_share_one_copy_of_every_common_function():
    """A fork drifts silently, and this is the shape it drifts in.

    A fix lands in the classic installer and nobody remembers the fork has its own
    copy of the same 30-odd functions. It has happened: a sweep replacing a template
    variable with the runtime mount point went through the classic file and left the
    fork addressing a path that is only correct on some distributions. Nothing failed
    -- both files are valid, both render, and the difference shows up on a node.

    Comparing the whole shared surface rather than the function someone thought to
    check is what makes the next sweep safe: whatever gets fixed in one has to be
    fixed in both, or this goes red.
    """
    classic, lpart = _functions(CLASSIC), _functions(LPART)
    assert set(lpart) - set(classic) == LPART_ONLY_FUNCTIONS, (
        f'the lpart installer defines functions the classic one does not, beyond the '
        f'lpart steps: {sorted(set(lpart) - set(classic) - LPART_ONLY_FUNCTIONS)}. '
        f'If it genuinely needs its own, add it to LPART_ONLY_FUNCTIONS and say why.'
    )
    assert set(classic) - set(lpart) == set(), (
        f'the classic installer has functions the lpart fork lacks: '
        f'{sorted(set(classic) - set(lpart))}. The fork must carry the whole classic '
        f'surface -- its fallback path runs it.'
    )
    drifted = sorted(name for name in classic if classic[name] != lpart[name])
    assert drifted == [], (
        f'these functions differ between the two installers: {drifted}. They are meant '
        f'to be one implementation in two files; a change to one is a change to both.'
    )


def test_the_lpart_installer_runs_the_classic_sequence_plus_its_own_steps():
    """Same call order, with the lpart phases interleaved -- nothing dropped.

    Derived from the classic flow rather than written out, so a step added there has
    to appear here too instead of being remembered. Dropping the lpart steps from the
    lpart flow must leave exactly the classic one.
    """
    reduced = [step for step in _flow(LPART) if step not in LPART_ONLY_FUNCTIONS]
    assert reduced == CLASSIC_FLOW, (
        f'with its lpart steps removed, the lpart installer does not run the classic '
        f'sequence:\n  classic: {CLASSIC_FLOW}\n  lpart:   {reduced}\n'
        f'A step present in one and not the other means a node installed the lpart way '
        f'quietly skips something every other node gets.'
    )


@pytest.mark.parametrize('template', ['templ_install.cfg', 'templ_install_lpart.cfg',
                                      'templ_post_boot.cfg'])
def test_the_rendered_installer_is_valid_bash(template):
    """Ask bash, rather than reading the template and forming an opinion.

    These files are edited as templates and executed as scripts, and nothing in
    between checks that. A quoting or heredoc mistake renders happily, passes every
    text-level test here, and fails on a node part-way through an install -- which is
    the most expensive place to find it. Both branch-heavy paths are rendered (roles
    and BMC on) so the conditional blocks are in the output being checked.
    """
    if shutil.which('bash') is None:
        pytest.skip('bash not available')
    rendered = _render(os.path.join(TEMPLATES, template),
                       LUNA_SETUPBMC=True, LUNA_HOLD_SECONDS=0, LUNA_HOLD_REASON='', LUNA_ROLES='role1', LUNA_SCRIPTS='s',
                       LUNA_TOKEN='t', LUNA_BOOTIF='eth0', LUNA_BOOTPROTO='dhcp',
                       DOMAIN_SEARCH=['example'], LUNA_INSTALL_MODE='full',
                       LUNA_DISKLAYOUT_B64='eyJ2IjoyfQ==', LUNA_OSIMAGE_FILTER_B64='e30=')
    check = subprocess.run(['bash', '-n'], input=rendered.encode('utf-8'),
                           capture_output=True, timeout=30)
    assert check.returncode == 0, (
        f'{template} renders to bash that will not parse:\n'
        f'{check.stderr.decode("utf-8", "replace")}'
    )


def test_every_variable_the_installers_use_is_rendered_by_the_boot_route():
    """
    A variable added to a template and not to the render call renders as nothing,
    silently - the trap a new LUNA_ variable walks into. Derived from the
    templates, so the next variable is covered without being remembered.
    """
    import os, re
    routes = open(os.path.join(DAEMON, 'routes', 'boot.py'), encoding='utf-8').read()
    for name in ('templ_install.cfg', 'templ_install_lpart.cfg'):
        text = open(os.path.join(DAEMON, 'templates', name), encoding='utf-8').read()
        for variable in sorted(set(re.findall(r'{{\s*(LUNA_[A-Z0-9_]+)', text))):
            assert re.search(rf'\b{variable}\s*=', routes), f'{name} uses {variable}, boot.py never renders it'
