#!/usr/bin/env python
#
###############################################################################
#
# fix_heat_wxs.py: Support script for IV Swinger 2 Windows installer build
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
# building a Windows Installer for the IV Swinger 2 application.
#
# Its input is a file named heat.wxs in the current directory. This file
# is the output of the "heat" tool that is included in the WiX toolset.
# It is assumed that the heat tool has been run on a
# pyinstaller-generated IV Swinger 2 executable generated in the "one
# folder" mode (as opposed to the "one file" mode). In particular,
# pyinstaller should be run using the "run_pyi.bat" script.  The
# step-by-step process for generating the heat.wxs input file and
# running this script is in the IV_Swinger/build_tools/README file in
# the "Instructions for Windows build" section.
#
# usage: fix_heat_wxs.py [-h] [-o OUTFILE] Input .wxs file [Input .wxs file ...]
#
# positional arguments:
#   Input .wxs file
#
# optional arguments:
#   -h, --help            show this help message and exit
#   -o OUTFILE, --outfile OUTFILE
#                         Name of output file
#                         (default=IV_Swinger_<version>_win.wxs)
import argparse
from bs4 import BeautifulSoup
import os
import re

# Constants
MANUFACTURER = "Chris Satterlee"
PRODUCT_NAME = "IV Swinger 2"
UPGRADE_CODE = "{c09606ca-ca7e-47ea-9f0f-fbc246d877c9}"


# Get version from version.txt
def get_version(app_path):
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


app_path = os.path.join(".", "dist", PRODUCT_NAME)
version_from_file = get_version(app_path)   # x.x.x
version = version_from_file + ".0"          # x.x.x.0
product_name_w_version = "IV Swinger v" + version
default_outfile = "IV_Swinger2_" + version + "_win.wxs"

# Parse command line args
parser = argparse.ArgumentParser()
parser.add_argument("-o", "--outfile", type=str, default=default_outfile,
                    help=("Name of output file (default=" +
                          default_outfile + ")"))
parser.add_argument("input_wxs", metavar='input_wxs_file',
                    type=str, nargs=1,
                    help=("Name of input .wxs file"))
args = parser.parse_args()

# Read input file into a BeautifulSoup object using XML parsing
soup = BeautifulSoup(open(args.input_wxs[0]), "xml")


def prettify_4space(s, encoding=None, formatter="minimal"):
    """Wrapper function for the BeautifulSoup prettify method to convert
       indents to four spaces (which is what heat uses)
    """
    return re.compile(r'^(\s*)',
                      re.MULTILINE).sub(r'\1\1\1\1',
                                        s.prettify(encoding, formatter))


def fix_product_attributes():
    """Function to change the "placeholder" values that heat generates for
       the attributes of the Product tag.
    """
    soup.Wix.Product['Id'] = "*"
    soup.Wix.Product['Manufacturer'] = MANUFACTURER
    soup.Wix.Product['Name'] = product_name_w_version
    soup.Wix.Product['UpgradeCode'] = UPGRADE_CODE
    soup.Wix.Product['Version'] = version


def get_component_ids():
    """Function to search the whole tree for "Component" tags
    """
    component_ids = []
    for child in soup.Wix.Product.descendants:
        if child.name == "Component":
            component_ids.append(child['Id'])
    return component_ids


def find_target_dir_tag():
    """Function to search the children of the "Product" tag for a
       "Directory" tag with the Id of TARGETDIR
    """
    for child in soup.Wix.Product.children:
        if child.name == "Directory":
            if child['Id'] == "TARGETDIR":
                return child


def find_product_dir_tag():
    """Function to search the children of the TARGETDIR Directory tag for a
       Directory tag with the name of the product
    """
    target_dir_tag = find_target_dir_tag()
    for child in target_dir_tag.children:
        if child.name == "Directory":
            if child['Name'] == PRODUCT_NAME:
                return child


def fix_product_dir_id():
    """Function to change the Id value of the product directory to
       INSTALLDIR
    """
    product_dir_tag = find_product_dir_tag()
    product_dir_tag['Id'] = "INSTALLDIR"


def put_product_dir_under_program_files():
    """Function to insert a level in the hierarchy; namely a
       ProgramFilesFolder directory around the product directory
    """
    product_dir_tag = find_product_dir_tag()
    product_dir_tag.wrap(soup.new_tag("Directory",
                                      Id="ProgramFilesFolder"))


def add_product_icon():
    """Function to add the product icon. This is the icon that is used for
       the "Programs and Features" tool in Control Panel (formerly known
       as "Add/Remove Programs").
    """
    product_icon = soup.new_tag("Icon",
                                Id="ProductIcon",
                                SourceFile="IV_Swinger2.ico")
    soup.Wix.Product.append(product_icon)
    product_icon_property = soup.new_tag("Property",
                                         Id="ARPPRODUCTICON",
                                         Value="ProductIcon")
    soup.Wix.Product.append(product_icon_property)


def add_help_link():
    """Function to add the help link. This is displayed in the "Programs and
       Features" tool in Control Panel (formerly known as "Add/Remove
       Programs") at the bottom of the window when the app is selected.
    """
    url = "http://www.github.com/csatt/IV_Swinger"
    help_link_property = soup.new_tag("Property",
                                      Id="ARPHELPLINK",
                                      Value=url)
    soup.Wix.Product.append(help_link_property)


def add_upgrade_tag():
    """Function to add the upgrade tag. As configured, this tells Windows
       Installer to remove any previous versions found.
    """
    upgrade_tag = soup.new_tag("Upgrade",
                               Id=UPGRADE_CODE)
    soup.Wix.Product.append(upgrade_tag)
    upgrade_tag.append(soup.new_tag("UpgradeVersion",
                                    OnlyDetect="no",
                                    Property="PREVIOUSFOUND",
                                    Minimum="0.0.0",
                                    IncludeMinimum="yes",
                                    Maximum=version,
                                    IncludeMaximum="no"))


def add_install_execute_sequence():
    """Function to add the install execute sequence
    """
    install_execute_seq = soup.new_tag("InstallExecuteSequence")
    soup.Wix.Product.append(install_execute_seq)
    rm_exist_products = soup.new_tag("RemoveExistingProducts",
                                     Before="InstallInitialize")
    install_execute_seq.append(rm_exist_products)


def add_start_menu_shortcut():
    """Function to add a shortcut to the ProgramMenuFolder under TARGETDIR,
       which has the effect of adding it to the Start menu. A registry
       entry is also added since this is the only way to provide a
       KeyPath for a shortcut.
    """
    target_dir_tag = find_target_dir_tag()
    pmf_dir = soup.new_tag("Directory",
                           Id="ProgramMenuFolder")
    target_dir_tag.append(pmf_dir)
    pmsf_dir = soup.new_tag("Directory",
                            Id="ProgramMenuSubfolder",
                            Name=PRODUCT_NAME)
    pmf_dir.append(pmsf_dir)
    as_comp = soup.new_tag("Component",
                           Id="ApplicationShortcuts",
                           Guid="*")
    pmsf_dir.append(as_comp)
    shortcut = soup.new_tag("Shortcut",
                            Id="ApplicationShortcut",
                            Name=PRODUCT_NAME,
                            Description=PRODUCT_NAME,
                            Target="[INSTALLDIR]" + PRODUCT_NAME + ".exe",
                            WorkingDirectory="INSTALLDIR")
    as_comp.append(shortcut)
    key = "Software\\" + MANUFACTURER + "\\" + PRODUCT_NAME
    regval = soup.new_tag("RegistryValue",
                          Root="HKCU",
                          Key=key,
                          Name="installed",
                          Type="integer",
                          Value="1",
                          KeyPath="yes")
    as_comp.append(regval)
    rm_folder = soup.new_tag("RemoveFolder",
                             Id="ProgramMenuSubfolder",
                             On="uninstall")
    as_comp.append(rm_folder)


def find_feature_tag():
    """Function to search the children of the product Directory tag for the
       one with the name "Feature".
    """
    for child in soup.Wix.Product.children:
        if child.name == "Feature":
            return child


def fix_feature():
    """Function to update the Feature tag to remove its placeholder title
       (which isn't needed), and to add ComponentRef tags for all of the
       components found in the tree.
    """
    # Remove title from Feature
    feature_tag = find_feature_tag()
    del feature_tag['Title']

    # Add all components to the feature
    component_ids = get_component_ids()
    for component_id in component_ids:
        feature_tag.append(soup.new_tag("ComponentRef",
                                        Id=component_id))


# Fix Product attributes
fix_product_attributes()

# Change Id of product directory to "INSTALLDIR"
fix_product_dir_id()

# Put product directory under ProgramFilesFolder
put_product_dir_under_program_files()

# Add product icon
add_product_icon()

# Add help link
add_help_link()

# Add Start Menu shortcut
add_start_menu_shortcut()

# Fix Feature
fix_feature()

# Add upgrade tag
add_upgrade_tag()

# Add install execute sequence
add_install_execute_sequence()

# Write the updated XML to the output file
with open(args.outfile, "w") as f:
    f.write(prettify_4space(soup))
