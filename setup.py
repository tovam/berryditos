#!/usr/bin/env python

import os
import re
import sys

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

def read(*names, **kwargs):
    with open(os.path.join(os.path.dirname(__file__), *names), 'r') as fp:
        return fp.read()

def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

classifiers = [
    "License :: OSI Approved :: MIT License",
    "Natural Language :: English",
    "Operating System :: OS Independent",
    "Programming Language :: Python",
    "Programming Language :: Python :: 2",
    "Programming Language :: Python :: 3",
    "Topic :: Software Development"
]

readme = os.path.join(os.path.dirname(__file__), 'README.md')

try:
    import pypandoc
    long_description = pypandoc.convert(readme, 'rst')
except ImportError:
    long_description = open(readme).read()

setup(
    name='berryditos',
    version=find_version('berryditos', 'base.py'),
    description='Berryditos is a tool that can edit and burn Raspbian images.',
    long_description=long_description,
    keywords=['raspberry','raspbian'],
    author='tovam',
    author_email='tovamdvlp@gmail.com',
    url='https://github.com/tovam/berryditos',
    license='MIT',
    classifiers=classifiers,
    install_requires=['requests'],
    packages=['berryditos'],
    scripts=['bin/berryditos'],
    zip_safe=True
)


