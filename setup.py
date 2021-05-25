#!/usr/bin/env python
"""Setup for completor packages"""
from __future__ import annotations

from glob import glob
from os.path import basename, splitext

import setuptools
from setuptools import find_packages

SSCRIPTS = ["completor = completor.main:main"]

LEGACYSCRIPTS: list[str] = []

REQUIREMENTS = [
    "matplotlib",
    "numpy<2",
    "pandas",
    "scipy",
