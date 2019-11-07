#!/usr/bin/env python

import shutil

import setuptools

import pykef

with open("README.md", "r") as fh:
    long_description = fh.read()

shutil.rmtree("dist", ignore_errors=True)

setuptools.setup(
    name="pykef",
    version="1.3.0",
    author="Robin Grönberg",
    author_email="robingronberg@gmail.com",
    description="A python implementation to interface Kef speakers over tcp/ip",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Gronis/pykef/",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
