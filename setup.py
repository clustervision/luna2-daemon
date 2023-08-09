#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Setup file, will build the pip package for the project.
"""

__author__      = 'Sumit Sharma'
__copyright__   = 'Copyright 2022, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.0'
__maintainer__  = 'Sumit Sharma'
__email__       = 'sumit.sharma@clustervision.com'
__status__      = 'Development'

from setuptools import setup, find_packages

PRE = "{Personal-Access-Token-Name}:{Personal-Access-Token}"

try: # for pip >= 10
    from pip._internal.req import parse_requirements
    install_requirements = list(parse_requirements('requirements.txt', session='hack'))
    requirements = [str(ir.requirement) for ir in install_requirements]
except ImportError: # for pip <= 9.0.3
    from pip.req import parse_requirements
    install_requirements = parse_requirements('requirements.txt', session='hack')
    requirements = [str(ir.req) for ir in install_requirements]


def new_version():
    """This Method will create a New version and update the Version file."""
    version = "0.0.0"
    with open('VERSION.txt', 'r', encoding='utf-8') as ver:
        version = ver.read()
    return version


setup(
	name = "daemon",
	version = new_version(),
	description = "Luna Daemon to make Luna SystemD Service",
	long_description = "Luna Daemon is a base tool of luna, that means, \
        it will install the luna daemon and start it as a service.",
	author = "Sumit Sharma",
	author_email = "sumit.sharma@clustervision.com",
	maintainer = "Sumit Sharma",
	maintainer_email = "sumit.sharma@clustervision.com",
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
	install_requires = requirements,
	dependency_links = [],
	package_data = {
        "daemon/config": ["*.monitor", "*.ini", "*.service", "*.json", "*.conf"],
        "daemon/config/third-party": ["*.service","*.conf"],
        "daemon/documentation": ["*.png", "*.bkp"],
        "daemon/log": ["*.log"],
        "daemon/templates": ["*.cfg"]
    },
	data_files = [],
	zip_safe = False,
	include_package_data = True,
	classifiers = [
		'Development Status :: Beta',
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