
# This code is part of the TrinityX software suite
# Copyright (C) 2026  ClusterVision Solutions b.v.
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This Is the BIOS staging planner.

Redfish does not apply BIOS attributes when you write them. It stages them in a
settings object and the machine applies them on its next reset - so a change is
one PATCH, one reboot, and a wait for POST.

Some attributes cannot be written at all until another one has already been
applied, which is what makes a single payload insufficient: the second half is
refused until the first half has been through a reboot. The obvious answer is a
hand-written per-model recipe, and it is the wrong one - the machine already
publishes the relationship.

The BIOS attribute registry carries a Dependencies array, and each entry says "if
these attributes hold these values, then that attribute's ReadOnly / GrayOut /
Hidden / Immutable becomes this". That is exactly the cascade that forces a second
payload. So the order is derived from what the machine says about itself rather
than from a table we maintain per vendor and per model, which is the same
discovery-first rule the rest of the Redfish work follows.

Where a machine serves no registry, or serves one with no dependencies, the plan
is a single stage - which is the correct answer for a machine that has not said
otherwise, and is what everything did before this existed.

Nothing here talks to a BMC. It is a pure function of two documents, which is why
every case below is testable without hardware.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'


import re
from fnmatch import fnmatch

from utils.log import Log

# The metadata properties that stop an attribute being written. A dependency that
# turns one of these on for an attribute is the machine saying "not yet".
BLOCKING = ('ReadOnly', 'GrayOut', 'Hidden', 'Immutable')

# What a MapFrom entry may compare with, from the AttributeRegistry schema.
CONDITIONS = ('EQU', 'NEQ', 'GTR', 'GEQ', 'LSS', 'LEQ')

# Registry flags that mean an attribute must not be carried to another machine.
# Each says something different and the wording here is the schema's own, because
# the distinctions matter: IsSystemUniqueProperty is the machine telling us this
# value belongs to it alone, where ReadOnly is only telling us we cannot write it.
UNPORTABLE = (
    ('IsSystemUniqueProperty', 'unique to this system and not to be replicated'),
    ('ReadOnly',               'read-only'),
    ('Immutable',              'immutable, reflects a hardware state'),
    ('WriteOnly',              'write-only, reverts after settings are applied'),
)

# The default exclude list, seeded onto a config when it is created so that an
# administrator can see it and change it - the same shape as an osimage carrying
# its own grab_exclude rather than the daemon holding one list for everybody.
#
# This exists because IsSystemUniqueProperty is optional in the schema and a
# vendor is under no obligation to set it. Every entry below is per-machine
# identity, which is what the vendor precedent excludes too: a Dell Server
# Configuration Profile exported for cloning comments out its I/O identity, where
# one exported to replace a machine keeps the service tag.
# How many times a stage may be re-attempted when the machine reports no error and
# simply does not take the change. It is a count rather than a clock so the answer
# is the same on a fast machine and a slow one, and so a report can say "3 of 3"
# rather than "we gave it a while".
MAX_ATTEMPTS = 3

# A settings object can report a payload as rejected without the write itself
# failing, and these are the severities that mean rejected. Anything else is
# informational and must not be read as a refusal.
REJECTED = ('critical', 'warning')

DEFAULT_EXCLUDE = (
    '*AssetTag*', '*ServiceTag*', '*SerialNumber*', '*Uuid*', '*UUID*',
    '*HostName*', '*IscsiInitiatorName*', '*VirtualMac*', '*VirtualAddress*',
    '*MacAddr*', '*WWPN*', '*WWNN*',
)

# Value shapes that are machine identity wherever they turn up, whatever the
# attribute happens to be called.
#
# A name list only catches what a vendor named honestly, and a vendor is under no
# obligation to. A board that calls a boot entry FBO204, describes it only as
# "Boot Option #4" and puts this machine's MAC in its value defeats every pattern
# above - all twelve of them - while carrying exactly the identity they exist to
# keep off another machine. Shapes travel where names do not.
#
# Only the three that cannot plausibly be anything else. A looser "looks like a
# serial number" pattern matches real settings, and dropping a legitimate
# attribute is the same silent shrinking of a configuration that this filter
# exists to prevent, just in the other direction. The world wide name comes first
# because a MAC pattern also matches the front of one, and the reason an operator
# reads should be the accurate one.
IDENTITY_SHAPES = (
    ('a world wide name', re.compile(r'\b[0-9a-f]{2}(?::[0-9a-f]{2}){7}\b', re.I)),
    ('a MAC address',     re.compile(r'\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b', re.I)),
    ('a MAC address',     re.compile(r'\b[0-9a-f]{2}(?:-[0-9a-f]{2}){5}\b', re.I)),
    ('a UUID',            re.compile(r'\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}'
                                     r'-[0-9a-f]{12}\b', re.I)),
)


class Bios():
    """
    Turns a desired set of BIOS attributes into the stages it takes to apply them.
    """

    def __init__(self):
        """
        Constructor - As of now, nothing have to initialize.
        """
        self.logger = Log.get_logger()


    def compare(self, have=None, condition='EQU', want=None):
        """
        This method evaluates one MapFrom comparison.

        The ordered comparisons are only meaningful on numbers, and a registry can
        name an attribute this machine does not have. Either way the honest answer
        is None - unknown - rather than False, because False would read as "the
        dependency does not apply" and let a write through that the machine will
        refuse.
        """
        if condition == 'EQU':
            return have == want
        if condition == 'NEQ':
            return have != want
        try:
            have, want = float(have), float(want)
        except (TypeError, ValueError):
            return None
        if condition == 'GTR':
            return have > want
        if condition == 'GEQ':
            return have >= want
        if condition == 'LSS':
            return have < want
        if condition == 'LEQ':
            return have <= want
        return None


    def holds(self, mapfrom=None, values=None):
        """
        This method evaluates a dependency's MapFrom list against a set of
        attribute values, and returns True, False, or None where it cannot be
        evaluated at all.

        MapTerms joins an entry to the one before it, so the list is folded left to
        right. A condition on anything other than a CurrentValue - on another
        attribute's ReadOnly, say - cannot be answered from the Bios resource, and
        is reported as unknown rather than guessed.
        """
        result = None
        for entry in mapfrom or []:
            if str(entry.get('MapFromProperty') or 'CurrentValue') != 'CurrentValue':
                return None
            name = entry.get('MapFromAttribute')
            if name not in (values or {}):
                return None
            outcome = self.compare(values[name],
                                   str(entry.get('MapFromCondition') or 'EQU'),
                                   entry.get('MapFromValue'))
            if outcome is None:
                return None
            if result is None:
                result = outcome
            elif str(entry.get('MapTerms') or 'AND').upper() == 'OR':
                result = result or outcome
            else:
                result = result and outcome
        return result


    def blocked(self, dependencies=None, values=None):
        """
        This method returns the attributes that cannot be written while the machine
        holds these values.

        Only a dependency that turns a blocking property ON counts. One that turns
        it off is the machine saying an attribute has become writable, which is the
        situation this planner exists to reach rather than something to avoid.
        """
        unwritable = {}
        for entry in dependencies or []:
            dependency = entry.get('Dependency') or {}
            if str(dependency.get('MapToProperty')) not in BLOCKING:
                continue
            if not dependency.get('MapToValue'):
                continue
            # MapToAttribute names what is affected; where a registry omits it, the
            # attribute the dependency is declared for is the one it affects. The
            # schema's wording and the DMTF's own example disagree about whether
            # DependencyFor is the affected attribute or the triggering one, so it
            # is only used as a fallback and never as the answer to "what is in the
            # way" - the MapFrom attributes are that, unambiguously.
            target = dependency.get('MapToAttribute') or entry.get('DependencyFor')
            if not target:
                continue
            if self.holds(mapfrom=dependency.get('MapFrom'), values=values) is True:
                sources = [item.get('MapFromAttribute')
                           for item in dependency.get('MapFrom') or []
                           if item.get('MapFromAttribute')]
                unwritable.setdefault(target, []).extend(sources)
        return unwritable


    def dependencies(self, registry=None):
        """
        This method pulls the Dependencies out of an attribute registry.
        """
        entries = (registry or {}).get('RegistryEntries') or {}
        found = entries.get('Dependencies')
        return found if isinstance(found, list) else []


    def attributes(self, registry=None):
        """
        This method pulls the attribute entries out of an attribute registry,
        keyed by name so a caller can ask about one without walking the list.
        """
        entries = (registry or {}).get('RegistryEntries') or {}
        found = entries.get('Attributes')
        if not isinstance(found, list):
            return {}
        return {entry['AttributeName']: entry for entry in found
                if isinstance(entry, dict) and entry.get('AttributeName')}


    def unportable(self, entry=None):
        """
        This method says why an attribute must not be carried to another machine,
        or None where nothing in the registry objects to it.

        The order matters only for what an operator reads: an attribute that is
        both unique and read-only is reported as unique, because that is the more
        useful thing to know.
        """
        for flag, reason in UNPORTABLE:
            if (entry or {}).get(flag) is True:
                return reason
        return None


    def excluded(self, name=None, patterns=None, entry=None):
        """
        This method returns the exclude pattern that matched an attribute, or
        None. Matching is case-insensitive because vendors do not agree on case
        for the same concept - AssetTag, Assettag and ASSETTAG all occur.

        The registry's display name is matched as well as the attribute name. A
        board is free to call an attribute SETUP042 and only say "Asset Tag" in
        the registry, and on such a board every pattern here is dead while the
        thing it names is copied anyway. The display name is what an operator can
        write a pattern against, so it is what a pattern is matched against.
        """
        candidates = [str(name)]
        display = (entry or {}).get('DisplayName')
        if display:
            candidates.append(str(display))
        for pattern in patterns or []:
            pattern = str(pattern).strip()
            if not pattern:
                continue
            for candidate in candidates:
                if fnmatch(candidate.lower(), pattern.lower()):
                    return pattern
        return None


    def identity(self, value=None):
        """
        This method returns what machine identity a value carries, or None.

        The registry flags answer this where a vendor sets them, and the exclude
        list answers it where a vendor named the attribute for what it holds.
        Neither is guaranteed, and a board that does neither is not unusual - so
        the value itself is read, because a MAC in a boot entry is that machine's
        MAC on any board that ever publishes one.
        """
        text = str(value)
        for shape, pattern in IDENTITY_SHAPES:
            if pattern.search(text):
                return shape
        return None


    def portable(self, registry=None, attributes=None, exclude=None):
        """
        This method splits a machine's attributes into what may be carried to
        another machine and what may not, and says why for each one dropped.

        Returns (kept, dropped) where dropped maps a name to its reason, so the
        caller can report what was left behind rather than silently shrinking the
        set. A grab that quietly drops half a configuration is indistinguishable
        from one that found half a configuration.

        Five things are dropped, and they are genuinely different questions: the
        registry says the attribute is not portable; the administrator's exclude
        list names it; it has no value; the registry does not describe it at all;
        or the value carries this machine's identity whatever the registry and the
        exclude list say about it.

        The fourth is worth stating out loud - an attribute the machine will not
        talk about is not one we should be copying. The fifth is the one that
        earns its place on real hardware, where the flags are absent and the names
        are opaque and the identity is sitting in the value regardless.
        """
        described = self.attributes(registry=registry)
        kept, dropped = {}, {}
        for name, value in (attributes or {}).items():
            if value is None:
                dropped[name] = 'no value'
                continue
            if name not in described:
                dropped[name] = 'not described by the attribute registry'
                continue
            reason = self.unportable(entry=described[name])
            if reason:
                dropped[name] = reason
                continue
            pattern = self.excluded(name=name, patterns=exclude,
                                    entry=described[name])
            if pattern:
                dropped[name] = f'excluded by {pattern}'
                continue
            shape = self.identity(value=value)
            if shape:
                dropped[name] = f'the value carries {shape}'
                continue
            kept[name] = value
        return kept, dropped


    def plan(self, registry=None, desired=None, current=None):
        """
        This method returns the ordered stages needed to apply a set of attributes,
        each stage being one PATCH and one reboot.

        The loop is the whole idea: write everything the machine will accept right
        now, then take those values as applied - which is what the reboot does -
        and ask again. An attribute that was refused because another one had not
        landed yet becomes writable on the next pass, and falls into the next
        stage. A machine that publishes no dependencies yields exactly one stage.

        Attributes already at the value asked for are dropped rather than written:
        a stage that changes nothing still costs a reboot.

        Returns (status, stages) or (False, reason). It refuses rather than guesses
        when nothing left is writable - that means the machine says these values
        cannot be reached from here, and sending them anyway produces a reboot and
        a rejection instead of an answer.
        """
        current = dict(current or {})
        pending = {name: value for name, value in (desired or {}).items()
                   if name not in current or current[name] != value}
        if not pending:
            return True, []
        dependencies = self.dependencies(registry=registry)
        values = dict(current)
        stages = []
        while pending:
            unwritable = self.blocked(dependencies=dependencies, values=values)
            writable = {name: value for name, value in pending.items()
                        if name not in unwritable}
            if not writable:
                blockers = sorted({source for name in pending
                                   for source in unwritable.get(name, [])})
                return False, (f"cannot reach these settings: "
                               f"{sorted(pending)} stay unwritable, blocked by "
                               f"{blockers}")
            stages.append(writable)
            values.update(writable)
            for name in writable:
                del pending[name]
        return True, stages


    def rejection(self, messages=None):
        """
        This method returns why a machine rejected a settings payload, or None.

        A settings object carries its own report, and it is the only place a
        refusal shows up when the write itself succeeded: the PATCH is answered
        200, the machine reboots, and the settings object says it would not take
        it. Reading only the HTTP status misses this entirely.
        """
        for entry in messages or []:
            if not isinstance(entry, dict):
                continue
            severity = str(entry.get('MessageSeverity')
                           or entry.get('Severity') or '').strip().lower()
            if severity in REJECTED:
                text = entry.get('Message') or entry.get('MessageId')
                resolution = entry.get('Resolution')
                if text and resolution and str(resolution).strip().lower() != 'none':
                    return f'{text} ({resolution})'
                if text:
                    return str(text)
                return f'the machine reported a {severity} condition with no message'
        return None


    def verdict(self, wanted=None, attributes=None, error=None, messages=None,
                attempts=0, limit=MAX_ATTEMPTS):
        """
        This method decides what happens after one attempt at one stage, and it is
        the whole of that decision - deterministic, so the same inputs always give
        the same answer and the same number of attempts.

        Returns (outcome, reason) where outcome is one of:
          'done'   everything asked for is in place
          'retry'  no error, but the machine did not take it, and attempts remain
          'failed' stop, for a reason that is stated

        The two ways of giving up are deliberately different, because retrying
        them has different value:

        A clear, direct refusal - the write failed, or the settings object reports
        the payload as rejected - ends it immediately. Retrying a refusal only
        reboots the machine to be refused again, and the reason is already in hand.

        No error and no effect is the other one, and it is the case people never
        predict: the PATCH is accepted, the machine reboots, and the attribute is
        simply not there. Nothing anywhere reports it, so the only way to know is
        to read back and compare - and the only sane response is a bounded number
        of attempts and then a stop that says how many were spent.
        """
        if error:
            return 'failed', f'the machine refused the change: {error}'
        refused = self.rejection(messages=messages)
        if refused:
            return 'failed', f'the machine rejected the settings: {refused}'
        missing = self.unapplied(wanted=wanted, attributes=attributes)
        if not missing:
            return 'done', 'applied'
        detail = ', '.join(f'{name} is {value!r}, wanted {wanted[name]!r}'
                           for name, value in sorted(missing.items()))
        if attempts < limit:
            return 'retry', (f'{len(missing)} setting(s) did not take on attempt '
                             f'{attempts} of {limit}: {detail}')
        return 'failed', (f'{len(missing)} setting(s) never took after {limit} '
                          f'attempt(s), with no error from the machine: {detail}')


    def compatible(self, config=None, target=None, policy='warn'):
        """
        This method decides whether a configuration grabbed from one machine may
        be pushed to another, and returns (status, reason).

        The board is not negotiable: BIOS settings are only meaningful on the
        hardware that published them, so a different manufacturer or model is
        refused whatever the policy says.

        The BIOS version is the judgement call, and it is a policy rather than a
        rule because both answers are defensible - pushing across a firmware
        refresh is a deliberate act, and doing it by accident is not. 'strict'
        refuses, 'warn' proceeds and says what differed, 'ignore' does not look.

        Note what this does NOT have to catch: an attribute the target's registry
        does not carry is dropped when the push filters against that registry, so
        an older BIOS missing three options loses those three rather than failing.
        This gate is for the other case - the same attribute name meaning
        something different, or taking different values, which no filter can see.
        """
        for field, label in (('manufacturer', 'manufacturer'), ('model', 'model')):
            want = str((config or {}).get(field) or '').strip()
            have = str((target or {}).get(field) or '').strip()
            if not want or not have:
                return False, f'the {label} is not known for both machines'
            if want.casefold() != have.casefold():
                return False, (f'{label} differs: the configuration came from '
                               f'{want!r} and this node is {have!r}')
        policy = str(policy or 'warn').strip().lower()
        want = str((config or {}).get('biosversion') or '').strip()
        have = str((target or {}).get('biosversion') or '').strip()
        if policy == 'ignore' or (want and have and want == have):
            return True, None
        if not want or not have:
            difference = 'the BIOS version is not known for both machines'
        else:
            difference = (f'BIOS version differs: the configuration came from '
                          f'{want} and this node runs {have}')
        if policy == 'strict':
            return False, difference
        return True, difference


    def unapplied(self, wanted=None, attributes=None):
        """
        This method returns what a machine did not take, comparing what was asked
        for against what it now reports.

        Read back what the machine holds rather than trusting the write. A BIOS
        accepts a settings payload and applies what it likes of it - the rest is
        dropped on the next boot with nothing said about it, and the PATCH answered
        success long before. An attribute missing from the reported set counts as
        unapplied: vendors differ on whether a pending area lists everything or
        only what changed, and absent is not evidence of applied.
        """
        missing = {}
        for name, value in (wanted or {}).items():
            if name not in (attributes or {}):
                missing[name] = None
            elif attributes[name] != value:
                missing[name] = attributes[name]
        return missing
