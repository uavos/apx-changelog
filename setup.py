#!/usr/bin/env python
# encoding: utf-8

"""Packaging script."""

import setuptools
import os
import re
import glob
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
readme = open(os.path.join(here, 'README.md')).read()


def versionfromfile(*filepath):
    here = os.path.abspath(os.path.dirname(__file__))
    infile = os.path.join(here, *filepath)
    with open(infile) as fp:
        version_match = re.search(r"^__version__\s*=\s*['\"]([^'\"]*)['\"]",
                                  fp.read(), re.M)
        if version_match:
            return version_match.group(1)
        raise RuntimeError(
            'Unable to find version string in {}.'.format(infile))


def versionfile(*filepath):
    with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), *filepath)) as fp:
        return fp.read().strip()


setup(
    name='apx-changelog',
    # version=versionfromfile('apxchangelog.py'),
    version=versionfile('.version'),
    author='Aliaksei Stratsiatau',
    author_email='sa@uavos.com',
    description='Generate changelog from a git repository',
    long_description=readme,
    long_description_content_type='text/markdown',
    # setup_requires=[''],
    install_requires=['regex', 'Jinja2', 'GitPython'],
    python_requires='>=3.5',
    license='MIT',
    keywords='',
    url='https://github.com/uavos/apx-changelog',
    packages=['apxchangelog'],
    package_dir={'apxchangelog': '.'},
    package_data={'apxchangelog': ['templates/*', '.version']},
    include_package_data=True,
    # py_modules=['apxchangelog'],
    entry_points={'console_scripts': ['apx-changelog=apxchangelog:main']},
    # data_files=[('templates', glob.glob('templates/*.jinja2'))],
    classifiers=['Development Status :: 5 - Production/Stable',
                 'License :: OSI Approved :: MIT License',
                 'Environment :: Console',
                 'Natural Language :: English',
                 'Programming Language :: Python :: 3',
                 'Topic :: Software Development',
                 'Topic :: Software Development :: Code Generators',
                 'Intended Audience :: Developers',
                 ],
)
