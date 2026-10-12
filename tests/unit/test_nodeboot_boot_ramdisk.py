#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
boot=ramdisk is what makes an initramfs-tools ramdisk (ubuntu 22/24) run the luna
installer instead of waiting for a root device that never appears. It has to be on
every kernel line the node boot template renders, and last, so osimage kerneloptions
cannot override it.
"""

import os

import pytest
from jinja2 import Template

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, '..', '..', 'daemon', 'templates', 'templ_nodeboot.cfg')

RENDER = {
    'WEBSERVER_PROTOCOL': 'http', 'WEBSERVER_PORT': '7051', 'LUNA_API_PROTOCOL': 'http',
    'LUNA_API_PORT': '7050', 'OSIMAGE_KERNELFILE': 'vmlinuz', 'OSIMAGE_INITRDFILE': 'initrd',
    'OSIMAGE_KERNELOPTIONS': 'net.ifnames=0 boot=local', 'NODE_MAC_ADDRESS': '00:11:22:33:44:55',
    'NODE_IPADDRESS': '10.141.0.1/16', 'NETWORK_GATEWAY': '10.141.255.254',
    'VERIFY_CERTIFICATE': 'False', 'NODE_NAME': 'node001', 'NODE_HOSTNAME': 'node001',
    'LUNA_LOGHOST': '10.141.255.254', 'NODE_SERVICE': '0',
}


@pytest.mark.parametrize('controller', ['10.141.255.254', 'fd00:141::254'])
def test_every_kernel_line_ends_with_boot_ramdisk(controller):
    with open(TEMPLATE) as fh:
        rendered = Template(fh.read()).render(LUNA_CONTROLLER=controller, **RENDER)
    assert rendered.startswith('#!ipxe\n')
    kernel_lines = [l for l in rendered.split('\n') if l.startswith('imgargs kernel ')]
    assert kernel_lines
    for line in kernel_lines:
        assert line.split()[-1] == 'boot=ramdisk', line
