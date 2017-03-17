#!/usr/bin/env python
# -*- coding: utf-8 -*-#
###############################################################################
#
# fix_info_plist.py: Support script for IV Swinger 2 Mac executable build
#
# Copyright (C) 2017  Chris Satterlee
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
#
# IV Swinger and IV Swinger 2 are open source hardware and software
# projects
#
# Permission to use the hardware designs is granted under the terms of
# the TAPR Open Hardware License Version 1.0 (May 25, 2007) -
# http://www.tapr.org/OHL
#
# Permission to use the software is granted under the terms of the GNU
# GPL v3 as noted above.
#
# Current versions of the licensing files, documentation, Fritzing file
# (hardware description), and software can be found at:
#
#    https://github.com/csatt/IV_Swinger
#
###############################################################################
#
# This file contains a Python script to assist in the process of
# building a Mac executable for the IV Swinger 2 application.
#
# Its input is the default Info.plist file that pyinstaller generates.
# It modifies that file as follows:
#
#   - Changes the value of CFBundleShortVersionString to the version
#     number in the version.txt file
#   - Adds NSHumanReadableCopyright with the copyright string
#   - Adds NSHighResolutionCapable, set to True
#
#  usage: fix_info_plist.py [-h] info_plist_file
#
#  positional arguments:
#    info_plist_file  (full or relative path)
#
#  optional arguments:
#    -h, --help       show this help message and exit
#
import argparse
import plistlib
import os


def get_version(app_path):
    """Get version from version.txt"""
    version_file = os.path.join(app_path, "version.txt")
    try:
        with open(version_file, "r") as f:
            lines = f.read().splitlines()
            if len(lines) != 1:
                err_str = ("ERROR: " + version_file + " has " +
                           str(len(lines)) + " lines")
                print err_str
                return "vFIXME"
            version = lines[0]
            if len(version) == 0 or version[0] != 'v':
                err_str = ("ERROR: " + version_file + " has invalid " +
                           "version: " + version)
                print err_str
                return "vFIXME"
            print "Application version: " + version
            return version
    except IOError:
        err_str = "ERROR: " + version_file + " doesn't exist"
        print err_str
        return "vFIXME"


# Parse command line args
parser = argparse.ArgumentParser()
parser.add_argument("info_plist", metavar='info_plist_file',
                    type=str, nargs=1,
                    help=("(full or relative path)"))
args = parser.parse_args()

# Get the version number
app_path = os.path.join(".", "dist", "IV Swinger 2")
version_from_file = get_version(app_path)   # vX.X.X
version = version_from_file[1:]             # X.X.X

# Read Info.plist into a plist object
plist = plistlib.readPlist(args.info_plist[0])

# Change version number
plist['CFBundleShortVersionString'] = version

# Add copyright string
plist['NSHumanReadableCopyright'] = u"Copyright © 2017  Chris Satterlee"

# Enable retina display resolution
plist['NSHighResolutionCapable'] = True

# Write the modified plist back to the Info.plist file
plistlib.writePlist(plist, args.info_plist[0])
