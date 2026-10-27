#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Which kernels an image tree really carries. The registered kernelversion is luna's one
statement of what a node runs; everything that reads or writes it checks the tree here.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

import os
import re


def version_key(version):
    """Sort key that orders 5.14.0-611.30.1 after 5.14.0-570.58.1, as a version sort does."""
    return [(0, int(part)) if part.isdigit() else (1, part) for part in re.split(r'(\d+)', version)]


def kernels_in_image(image_path):
    """
    Every kernel the image can boot, lowest version first. A kernel is a vmlinuz plus a
    module tree that still holds one: a removed kernel leaves its module directory behind
    with only the depmod index files in it. Rescue and debug variants are never what a
    node runs, so they do not count.
    """
    modules = os.path.join(image_path, 'lib', 'modules')
    found = []
    for version in (os.listdir(modules) if os.path.isdir(modules) else []):
        if 'rescue' in version or version.endswith('+debug'):
            continue
        if not os.path.isdir(os.path.join(modules, version, 'kernel')):
            continue
        if not os.path.isfile(os.path.join(image_path, 'boot', f'vmlinuz-{version}')):
            continue
        found.append(version)
    return sorted(found, key=version_key)


def newest_kernel(image_path):
    """The highest kernel version in the image, and the whole list it was chosen from."""
    kernels = kernels_in_image(image_path)
    return (kernels[-1] if kernels else None), kernels


def kernel_state_warning(image_path, kernelversion):
    """
    What a pack tells the operator when the tree and the registered kernel disagree, and
    nothing when the image carries exactly that one kernel. Only the registered kernel is
    served over the network; every kernel in the tree rides to disk, where the boot loader
    picks its own.
    """
    kernels = kernels_in_image(image_path)
    if kernelversion not in kernels:
        listed = ', '.join(kernels) if kernels else 'no kernel at all'
        return f"warning: registered kernel {kernelversion} is not in the image, which carries {listed}"
    others = [kernel for kernel in kernels if kernel != kernelversion]
    if others:
        return (f"warning: the image carries {len(kernels)} kernels; {kernelversion} is registered and "
                f"served, {', '.join(others)} also rides to disk. Remove it, or register it with "
                f"'luna osimage kernel -k'")
    return ''
