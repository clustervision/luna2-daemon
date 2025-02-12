#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Setup file, will build the pip package for the project.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.1'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

from time import time
from setuptools import setup, find_packages

PRE = "{Personal-Access-Token-Name}:{Personal-Access-Token}"

def get_requirements():
    """
    This Method will read the requirements.txt file and return the list of requirements.
    """

    # for pip <= 9.0.3
    try: 
        from pip.req import parse_requirements
        install_requirements = parse_requirements('requirements.txt', session='hack')
        return  [str(ir.req) for ir in install_requirements]
    except ImportError: 
        pass

    # for pip >= 10 AND pip <= 23.1
    try:
        from pip._internal.req import parse_requirements
        install_requirements = list(parse_requirements('requirements.txt', session='hack'))
        return [str(ir.requirement) for ir in install_requirements]
    except ImportError: 
        pass

    # anything else
    with open('requirements.txt', 'r', encoding='utf-8') as f:
        requirements = f.read().splitlines()
    return requirements


def new_version():
    """
    This Method will create a New version and update the Version file.
    """
    time_now = int(time())
    version = f'2.1.{time_now}'
    with open('daemon/VERSION.txt', 'w', encoding='utf-8') as ver:
        ver.write(version)
    return version


setup(
    name = "luna2-daemon",
    version = new_version(),
    description = "Luna Daemon to make Luna SystemD Service",
    long_description = "Luna Daemon is a base tool of luna, that means, \
        it will install the luna daemon and start it as a service.",
    author = "ClusterVision Development team",
    author_email = "support@clustervision.com",
    maintainer = "ClusterVision Development team",
    maintainer_email = "support@clustervision.com",
    url = "https://gitlab.taurusgroup.one/clustervision/luna2-daemon.git",
    download_url = f"https://{PRE}@gitlab.taurusgroup.one/api/v4/projects/20/packages/pypi/simple",
    packages = find_packages(),
    license = "MIT",
    keywords = ["luna", "daemon", "Trinity", "ClusterVision", "Sumit", "Sumit Sharma"],
    entry_points = {
        'console_scripts': [
            'daemon = daemon.daemon:main'
        ]
    },
    install_requires = get_requirements(),
    dependency_links = [],
    package_data = {
        "daemon": ["*.txt"],
        "daemon/config": ["*.monitor", "*.ini", "*.service", "*.json", "*.conf"],
        "daemon/config/third-party": ["*.service","*.conf"],
        "daemon/log": ["*.log"],
        "daemon/templates": ["*.cfg"],
        "daemon/plugins/control": ["README","*.py"],
        "daemon/plugins/boot/bmc": ["README","*.py"],
        "daemon/plugins/boot/detection": ["README","*.py"],
        "daemon/plugins/boot/scripts": ["README","*py"],
        "daemon/plugins/boot/network": ["README","*.py"],
        "daemon/plugins/boot/provision": ["README","*.py"],
        "daemon/plugins/boot/localinstall": ["README","*.py"],
        "daemon/plugins/osimage/operations/osgrab": ["README","*.py"],
        "daemon/plugins/osimage/operations/ospush": ["README","*py"],
        "daemon/plugins/osimage/operations/image": ["README","*py"],
        "daemon/plugins/osimage/filesystem": ["README","*py"],
        "daemon/plugins/osimage/other": ["README","*py"]
    },
    data_files = [],
    zip_safe = False,
    include_package_data = True,
    classifiers = [
        'Development Status :: BETA',
        'Environment :: REST API',
        'Intended Audience :: System Administrators',
        'License :: MIT',
        'Operating System :: RockyLinux :: CentOS :: RedHat',
        'Programming Language :: Python',
        'Topic :: Trinity :: Luna'
    ],
    platforms = [
        'RockyLinux',
        'CentOS',
        'RedHat'
    ]
)
# python setup.py sdist bdist_wheel
