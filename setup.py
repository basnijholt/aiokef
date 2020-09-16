#!/usr/bin/env python3

# Copyright 2019-2020 Bas Nijholt.
#
# This file is part of aiokef. It is subject to the license terms
# in the file LICENSE found in the top-level directory of this distribution.
# A list of aiokef authors can be found using git, with
# `git shortlog -s HEAD` and at
# https://github.com/basnijholt/aiokef/graphs/contributors.


import sys

from setuptools import find_packages, setup

if sys.version_info < (3, 7):
    print("aiokef requires Python 3.7 or above.")
    sys.exit(1)


def get_version_and_cmdclass(package_name):
    import os
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("version", os.path.join(package_name, "_version.py"))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.__version__, module.cmdclass


version, cmdclass = get_version_and_cmdclass("aiokef")

with open("README.md") as f:
    readme = f.read()

setup(
    name="aiokef",
    version=version,
    cmdclass=cmdclass,
    python_requires=">=3.7",
    packages=find_packages(),
    include_package_data=True,
    maintainer="Bas Nijholt",
    maintainer_email="bas@nijho.lt",
    description="Asyncio Python API for KEF speakers.",
    long_description=readme,
    long_description_content_type="text/markdown",
    license="MIT",
    url="https://github.com/basnijholt/aiokef",
    download_url="https://pypi.python.org/pypi/aiokef",
    install_requires=[
        "async-timeout",
        "tenacity",
    ],
    extras_require=dict(
        test=[
            "pytest",
            "pytest-cov",
            "pytest-flake8",
            "pytest-mypy",
            "pytest-black",
            "tox",
            "flake8-per-file-ignores",
        ],
        docs=[
            "sphinx",
            "sphinx-rtd-theme",
            "m2r",  # markdown support
            "sphinxcontrib.apidoc",  # run sphinx-apidoc when building docs
        ],
        dev=["pre-commit"],
    ),
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Development Status :: 4 - Beta",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Home Automation",
    ],
    keywords="iot",
)
