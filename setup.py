#!/usr/bin/env python

import sys
import os

from setuptools import setup

pwd = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(pwd, "README.md")) as f:
    readme = f.read()

setup(
    name="aiokef",
    version="v0.1",
    description=readme,
    long_description=readme,
    author="Bas Nijholt",
    author_email="bas@nijho.lt",
    url="https://github.com/basnijholt/aiokef",
    py_modules=["aiokef"],
    scripts=["aiokef.py"],
    license="MIT",
    install_requires=["tenacity"],
)
