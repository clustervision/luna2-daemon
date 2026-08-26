
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


from utils.log import Log

# The metadata properties that stop an attribute being written. A dependency that
# turns one of these on for an attribute is the machine saying "not yet".
BLOCKING = ('ReadOnly', 'GrayOut', 'Hidden', 'Immutable')

# What a MapFrom entry may compare with, from the AttributeRegistry schema.
CONDITIONS = ('EQU', 'NEQ', 'GTR', 'GEQ', 'LSS', 'LEQ')


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
