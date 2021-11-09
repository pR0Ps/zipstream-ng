#!/usr/bin/env python

from setuptools import setup
import os.path


try:
    DIR = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(DIR, "README.md"), encoding='utf-8') as f:
        long_description = f.read()
except Exception:
    long_description=None


setup(
    name="zipstream-ng",
    version="1.2.0",
    description="A modern and easy to use streamable zip file generator",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pR0Ps/zipstream-ng",
    license="LGPLv3",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Operating System :: OS Independent",
        "Topic :: System :: Archiving :: Compression",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)"
    ],
    packages=["zipstream"],
    entry_points={
        "console_scripts": ["zipserver=zipstream.server:main"]
    },
    python_requires=">=3.5.0",
    extras_require={
        "tests": ["pytest", "pytest-cov"],
    },
)
