#!/usr/bin/env python3
from setuptools import setup, find_packages
from os import listdir
setup(name="luna2",
version = "2.0",
description = "Luna2 is a baremetal provisioning tool",
url = "https://gitlab.taurusgroup.one:clustervision/luna2",
author = "Sumit Sharma",
author_email = "sumit.sharma@clustervision.com",
license = "MIT",
packages = find_packages(),
install_requires=[
	"termcolor",
	"pyfiglet",
	"pandas",
	"paho-mqtt",
	"argparse",
	"ipaddress",
	# "pysqlite3",
	"tk",
	"colorama",
	"prettytable"
	# "PyInquirer"
	],
entry_points ={
	'console_scripts': [
	'luna = luna.base:main'
	]
},
dependency_links = [],
package_data = {},
data_files = [],
zip_safe = False,
include_package_data = True
)
# python setup.py sdist bdist_wheel