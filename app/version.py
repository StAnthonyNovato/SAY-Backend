# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT
from os.path import isfile
from setuptools_scm._run_cmd import CommandNotFoundError
# File for tracking the application version


try:
    from setuptools_scm import get_version
    __version__ = get_version()

except (ImportError, LookupError, OSError, CommandNotFoundError):
    try:
        with open("version.txt", "r") as f:
            __version__ = f.read().strip()
    except (FileNotFoundError, IOError):
        __version__ = "0.0.0"