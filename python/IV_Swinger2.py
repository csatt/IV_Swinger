#!/usr/bin/env python
"""IV Swinger 2 configuration and control module"""
#
###############################################################################
#
# IV_Swinger2.py: IV Swinger 2 configuration and control module
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
# This file contains the Python code that implements the IV Swinger 2
# hardware control, configuration, plotting, and debug logging.  It
# provides an API to higher level code such as (but not limited to) a
# graphical user interface (GUI).
#
# IV Swinger 2 (IVS2) is very different from the original IV Swinger
# (IVS1), yet there are still some opportunities to leverage the IVS1
# code (if not for that fact, it might even have made more sense to use
# a different language than Python for IVS2). The IV_Swinger2 class in
# this module extends the IV_Swinger class, allowing code re-use where
# it makes sense. The IV_Singer_plotter module is also imported and used
# for plotting the results.
#
# The Raspberry Pi (RPi) is the compute platform for IVS1.  On IVS1, the
# Python code runs on the RPi; it controls the IV Swinger hardware,
# captures measurements, and writes the data and graphs to one or more
# USB flash drives. IVS2 uses an Arduino to control the hardware and
# take the voltage and current measurements. The IVS2 Python code runs
# on an external "host", which is most likely a Windows or Mac laptop
# computer.  But the host computer can be anything that is capable of
# running Python (including RPi).
#
# As mentioned above, the higher level code that sits on top of this
# module can be something other than the GUI that is used for the IV
# Swinger 2 application. For example, a command-line interface (CLI)
# could be implemented. Another example would be a Python script that
# implements some kind of automated test, potentially also interacting
# with other devices. Imagine, for example, a device that incrementally
# moves "shade" across the PV module - a script could loop, moving the
# shade a step and swinging an IV curve on each iteration.
#
import argparse
import ConfigParser
import io
import math
import os
import re
import serial
import serial.tools.list_ports
import shutil
import subprocess
import sys
import time
from PIL import Image
try:
    # Mac only
    from AppKit import NSSearchPathForDirectoriesInDomains as get_mac_dir
    from AppKit import NSApplicationSupportDirectory as mac_app_sup_dir
    from AppKit import NSUserDomainMask as mac_domain_mask
except:
    pass
import IV_Swinger
import IV_Swinger_plotter

#################
#   Constants   #
#################
APP_NAME = "IV_Swinger2"
RC_SUCCESS = 0
RC_FAILURE = -1
RC_BAUD_MISMATCH = -2
RC_TIMEOUT = -3
RC_SERIAL_EXCEPTION = -4
RC_ZERO_VOC = -5
RC_ZERO_ISC = -6
RC_ISC_TIMEOUT = -7
CFG_STRING = 0
CFG_FLOAT = 1
CFG_INT = 2
CFG_BOOLEAN = 3
SKETCH_VER_LT = -1
SKETCH_VER_EQ = 0
SKETCH_VER_GT = 1
SKETCH_VER_ERR = -2
LATEST_SKETCH_VER = "1.1.0"

# From IV_Swinger
PLOT_COLORS = IV_Swinger.PLOT_COLORS
AMPS_INDEX = IV_Swinger.AMPS_INDEX
VOLTS_INDEX = IV_Swinger.VOLTS_INDEX
OHMS_INDEX = IV_Swinger.OHMS_INDEX
WATTS_INDEX = IV_Swinger.WATTS_INDEX
INFINITE_VAL = IV_Swinger.INFINITE_VAL

# From Arduino SPI.h:
SPI_CLOCK_DIV4 = 0x00
SPI_CLOCK_DIV16 = 0x01
SPI_CLOCK_DIV64 = 0x02
SPI_CLOCK_DIV128 = 0x03
SPI_CLOCK_DIV2 = 0x04
SPI_CLOCK_DIV8 = 0x05
SPI_CLOCK_DIV32 = 0x06
# Default plotting config
FONT_SCALE_DEFAULT = 1.0
LINE_SCALE_DEFAULT = 1.0
POINT_SCALE_DEFAULT = 1.0
# Default Arduino config
SPI_CLK_DEFAULT = SPI_CLOCK_DIV8
MAX_IV_POINTS_DEFAULT = 140
MIN_ISC_ADC_DEFAULT = 10
MAX_ISC_POLL_DEFAULT = 5000
ISC_STABLE_DEFAULT = 5
MAX_DISCARDS_DEFAULT = 300
ASPECT_HEIGHT_DEFAULT = 2
ASPECT_WIDTH_DEFAULT = 3
# Other Arduino constants
ARDUINO_MAX_INT = (1 << 15) - 1
MAX_IV_POINTS_MAX = 275
ADC_MAX = 4095
MAX_ASPECT = 8
# Default calibration values
V_CAL_DEFAULT = 1.0197
I_CAL_DEFAULT = 1.1187
V_BATT_DEFAULT = 0.0
R_BATT_DEFAULT = 0.0
# Default resistor values
R1_DEFAULT = 150000.0   # R1 = 150k nominal
R1_DEFAULT_BUG = 180000.0   # This was a bug
R2_DEFAULT = 7500.0     # R2 = 7.5k nominal
RF_DEFAULT = 75000.0    # Rf = 75k
RG_DEFAULT = 1000.0     # Rg = 1k
SHUNT_DEFAULT = 5000.0  # Shunt = 5000 microohms
# Arduino EEPROM constants
EEPROM_VALID_ADDR = 0
EEPROM_VALID_COUNT_ADDR = 4
EEPROM_R1_OHMS_ADDR = 8
EEPROM_R2_OHMS_ADDR = 12
EEPROM_RF_OHMS_ADDR = 16
EEPROM_RG_OHMS_ADDR = 20
EEPROM_SHUNT_UOHMS_ADDR = 24
EEPROM_V_CAL_X1M_ADDR = 28
EEPROM_I_CAL_X1M_ADDR = 32
EEPROM_V_BATT_X1M_ADDR = 36
EEPROM_R_BATT_X1M_ADDR = 40
EEPROM_VALID_VALUE = "123456.7890"
EEPROM_VALID_COUNT = 9  # increment if any added
# Debug constants
DEBUG_CONFIG = False


########################
#   Global functions   #
########################
def get_date_time_str():
    return IV_Swinger.DateTimeStr.get_date_time_str()


def extract_date_time_str(input_str):
    return IV_Swinger.DateTimeStr.extract_date_time_str(input_str)


def is_date_time_str(input_str):
    return IV_Swinger.DateTimeStr.is_date_time_str(input_str)


def xlate_date_time_str(date_time_str):
    return IV_Swinger.DateTimeStr.xlate_date_time_str(date_time_str)


def close_plots():
    IV_Swinger.IV_Swinger.close_plots()


def sys_view_file(file):
    """Method to use an OS-specific application to view a file, based on
       its file type/extension. e.g. a .txt file will be opened
       using a text editor, a PDF file will be opened with
       whatever is normally used to view PDFs (Acrobat reader,
       Preview, etc.)
    """
    if sys.platform == 'darwin':
        # Mac
        subprocess.call(('open', file))
    elif sys.platform == 'win32':
        # Windows
        os.startfile(file)
    else:
        # Linux
        subprocess.call(('xdg-open', file))


#################
#   Classes     #
#################


# Configuration class
#
class Configuration(object):
    """Provides support for saving and restoring configuration values. Only
       the configuration values that map to properties in the
       IV_Swinger2 class are included, but the class can be extended to
       add others.
    """

    # Initializer
    def __init__(self, ivs2=None):
        self.ivs2 = ivs2
        self.cfg = ConfigParser.SafeConfigParser()
        self.cfg_snapshot = ConfigParser.SafeConfigParser()
        self._cfg_filename = None

    # ---------------------------------
    @property
    def cfg_filename(self):
        """Name of file (full path) that contains preferences and other
           configuration options
        """
        if self._cfg_filename is None:
            self._cfg_filename = os.path.join(self.ivs2.app_data_dir,
                                              APP_NAME + ".cfg")
        return self._cfg_filename

    @cfg_filename.setter
    def cfg_filename(self, value):
        if value is not None and not os.path.isabs(value):
            raise ValueError("cfg_filename must be an absolute path")
        self._cfg_filename = value

    # -------------------------------------------------------------------------
    def cfg_set(self, section, option, value):
        """Method to set a config option. Just a wrapper around the
           ConfigParser set method, but converts value to a string
           first.
        """
        self.cfg.set(section, option, str(value))

    # -------------------------------------------------------------------------
    def cfg_dump(self):
        for section in self.cfg.sections():
            self.ivs2.logger.print_and_log(section)
            for option in self.cfg.options(section):
                err_str = " " + option + "=" + self.cfg.get(section, option)
                self.ivs2.logger.print_and_log(err_str)

    # -------------------------------------------------------------------------
    def get(self):
        """Method to get the saved preferences and other configuration from the
           .cfg file if it exists, and apply the values to the
           associated properties
        """
        if DEBUG_CONFIG:
            dbg_str = ("get: Reading config from " + self.cfg_filename)
            self.ivs2.logger.print_and_log(dbg_str)
        try:
            with open(self.cfg_filename, "r") as cfg_fp:
                self.cfg.readfp(cfg_fp)
        except IOError:
            # File doesn't exist
            self.ivs2.find_arduino_port()
            self.populate()
            self.save()
        else:
            # File does exist ...
            self.apply_all()

    # -------------------------------------------------------------------------
    def get_snapshot(self):
        """Method to get the saved preferences and other configuration
           from the .cfg file and store them in the snapshot config
        """
        if DEBUG_CONFIG:
            dbg_str = ("get_snapshot: Reading config from " +
                       self.cfg_filename)
            self.ivs2.logger.print_and_log(dbg_str)
        self.cfg_snapshot = ConfigParser.SafeConfigParser()
        with open(self.cfg_filename, "r") as cfg_fp:
            self.cfg_snapshot.readfp(cfg_fp)

    # -------------------------------------------------------------------------
    def get_old_result(self, cfg_file):
        """Method to get the preferences and other configuration from the
           specified .cfg file and apply the values to the associated
           properties. This includes the axes and title configurations,
           which are not applied in other cases. But it excludes the USB
           and Arduino configurations.
        """
        if DEBUG_CONFIG:
            dbg_str = "get_old_result: Reading config from " + cfg_file
            self.ivs2.logger.print_and_log(dbg_str)
        with open(cfg_file, "r") as cfg_fp:
            # Blow away old config and create new one
            self.cfg = ConfigParser.SafeConfigParser()
            # Read values from file
            self.cfg.readfp(cfg_fp)
            # Apply selected values to properties
            self.apply_general()
            self.apply_calibration()
            self.apply_plotting()
            self.apply_axes()
            self.apply_title()

    # -------------------------------------------------------------------------
    def get_saved_title(self, cfg_file):
        """Method to get the title configuration from the specified .cfg file
        """
        my_cfg = ConfigParser.SafeConfigParser()
        with open(cfg_file, "r") as cfg_fp:
            # Read values from file
            my_cfg.readfp(cfg_fp)
            try:
                # Get title config
                title = my_cfg.get("Plotting", "title")
            except ConfigParser.NoOptionError:
                title = None
        return title

    # -------------------------------------------------------------------------
    def get_old_title(self, cfg_file):
        """Method to get the title configuration from the specified .cfg file
           and apply its value to the current config and its
           associated property.
        """
        if DEBUG_CONFIG:
            dbg_str = "get_old_title: Reading config from " + cfg_file
            self.ivs2.logger.print_and_log(dbg_str)
        title = self.get_saved_title(cfg_file)
        # Update title in current config
        self.cfg_set("Plotting", "title", title)
        # Apply title config only
        self.apply_title()

    # -------------------------------------------------------------------------
    def apply_one(self, section, option, config_type, old_prop_val):
        """Method to apply an option read from the .cfg file to the
           associated object property. The value returned is the new (or
           perhaps old) property value. If the option is not found in
           the .cfg file, the old value is added to the config and the
           old value is returned to the caller. Also, if the option is
           found in the .cfg file, but it is not of the correct type,
           then the old value is added to the config.
        """
        full_name = section + " " + option
        try:
            if config_type == CFG_FLOAT:
                cfg_value = self.cfg.getfloat(section, option)
                return float(cfg_value)
            elif config_type == CFG_INT:
                cfg_value = self.cfg.getint(section, option)
                return int(cfg_value)
            elif config_type == CFG_BOOLEAN:
                cfg_value = self.cfg.getboolean(section, option)
                return bool(cfg_value)
            elif config_type == CFG_STRING:
                cfg_value = self.cfg.get(section, option)
                if cfg_value == "None":
                    cfg_value = None
                return cfg_value
            else:
                return old_prop_val
        except ConfigParser.NoOptionError:
            err_str = full_name + " not found in cfg file"
            self.ivs2.logger.print_and_log(err_str)
            self.cfg_set(section, option, old_prop_val)
            return old_prop_val
        except ValueError:
            err_str = full_name + " invalid in cfg file"
            self.ivs2.logger.print_and_log(err_str)
            self.cfg_set(section, option, old_prop_val)
            return old_prop_val

    # -------------------------------------------------------------------------
    def apply_all(self):
        """Method to apply the config read from the .cfg file to the
           associated object properties for all sections and options
        """
        # General section
        self.apply_general()

        # USB section
        self.apply_usb()

        # Calibration section
        self.apply_calibration()

        # Plotting section
        self.apply_plotting()

        # Arduino section
        self.apply_arduino()

    # -------------------------------------------------------------------------
    def apply_general(self):
        """Method to apply the General section options read from the
           .cfg file to the associated object properties
        """
        section = 'General'

        # X pixels
        args = (section, 'x pixels', CFG_INT, self.ivs2.x_pixels)
        self.ivs2.x_pixels = self.apply_one(*args)

    # -------------------------------------------------------------------------
    def apply_usb(self):
        """Method to apply the USB section options read from the .cfg
           file to the associated object properties
        """
        section = 'USB'

        # Port
        option = 'port'
        full_name = section + " " + option
        try:
            cfg_value = self.cfg.get(section, option)
        except ConfigParser.NoOptionError:
            err_str = full_name + " not found in cfg file"
            self.ivs2.logger.print_and_log(err_str)
            self.ivs2.find_arduino_port()
            self.cfg_set(section, option, self.ivs2.usb_port)
        else:
            port_attached = False
            for serial_port in self.ivs2.serial_ports:
                if cfg_value in str(serial_port):
                    port_attached = True
                    break
            if port_attached:
                self.ivs2.usb_port = cfg_value
            else:
                if cfg_value != "None":
                    err_str = full_name + " in cfg file not attached"
                    self.ivs2.logger.print_and_log(err_str)
                self.ivs2.find_arduino_port()
                self.cfg_set(section, option, self.ivs2.usb_port)
        # Baud
        args = (section, 'baud', CFG_INT, self.ivs2.usb_baud)
        self.ivs2.usb_baud = self.apply_one(*args)

    # -------------------------------------------------------------------------
    def apply_calibration(self):
        """Method to apply the Calibration section options read from the
           .cfg file to the associated object properties
        """
        section = 'Calibration'

        # Voltage
        args = (section, 'voltage', CFG_FLOAT, self.ivs2.v_cal)
        self.ivs2.v_cal = self.apply_one(*args)

        # Current
        args = (section, 'current', CFG_FLOAT, self.ivs2.i_cal)
        self.ivs2.i_cal = self.apply_one(*args)

        # Bias battery voltage
        args = (section, 'bias battery voltage', CFG_FLOAT,
                V_BATT_DEFAULT)
        self.ivs2.v_batt = self.apply_one(*args)

        # Bias battery resistance
        args = (section, 'bias battery resistance', CFG_FLOAT,
                R_BATT_DEFAULT)
        self.ivs2.r_batt = self.apply_one(*args)

        # NOTE: The "old" values in the args values are used when the
        # .cfg file is missing values for a particular config
        # type. Since the resistors were not originally included in the
        # config, they will be missing in the .cfg files of older
        # runs. Instead of using the current values of their associated
        # properties, we use the default values. In the case of R1,
        # however, there was a bug in the code when the older runs were
        # generated, so we need to use that older (bad) value. This
        # should prevent unexpected changes in the old graphs when they
        # are updated (for example to plot power).

        # Resistor R1
        args = (section, 'r1 ohms', CFG_FLOAT, R1_DEFAULT_BUG)
        self.ivs2.vdiv_r1 = self.apply_one(*args)

        # Resistor R2
        args = (section, 'r2 ohms', CFG_FLOAT, R2_DEFAULT)
        self.ivs2.vdiv_r2 = self.apply_one(*args)

        # Resistor Rf
        args = (section, 'rf ohms', CFG_FLOAT, RF_DEFAULT)
        self.ivs2.amm_op_amp_rf = self.apply_one(*args)

        # Resistor Rg
        args = (section, 'rg ohms', CFG_FLOAT, RG_DEFAULT)
        self.ivs2.amm_op_amp_rg = self.apply_one(*args)

        # Shunt resistor
        #
        # For "legacy" reasons, the shunt resistor is specified by two values:
        # max volts and max amps.  It's resistance is max_volts/max_amps.  The
        # max_amps value is hardcoded to 10A, so we just keep the value of
        # max_volts in the config.
        args = (section, 'shunt max volts', CFG_FLOAT,
                (self.ivs2.amm_shunt_max_amps *
                 (SHUNT_DEFAULT / 1000000.0)))
        self.ivs2.amm_shunt_max_volts = self.apply_one(*args)

    # -------------------------------------------------------------------------
    def apply_plotting(self):
        """Method to apply the Plotting section options read from the
           .cfg file to the associated object properties
        """
        section = 'Plotting'

        # Plot power
        args = (section, 'plot power', CFG_BOOLEAN, self.ivs2.plot_power)
        self.ivs2.plot_power = self.apply_one(*args)

        # Fancy labels
        args = (section, 'fancy labels', CFG_BOOLEAN, self.ivs2.fancy_labels)
        self.ivs2.fancy_labels = self.apply_one(*args)

        # Interpolation
        args = (section, 'linear', CFG_BOOLEAN, self.ivs2.linear)
        self.ivs2.linear = self.apply_one(*args)

        # Font scale
        args = (section, 'font scale', CFG_FLOAT, self.ivs2.font_scale)
        self.ivs2.font_scale = self.apply_one(*args)

        # Line scale
        args = (section, 'line scale', CFG_FLOAT, self.ivs2.line_scale)
        self.ivs2.line_scale = self.apply_one(*args)

        # Point scale
        args = (section, 'point scale', CFG_FLOAT, self.ivs2.point_scale)
        self.ivs2.point_scale = self.apply_one(*args)

        # ADC correction
        args = (section, 'correct adc', CFG_BOOLEAN, self.ivs2.correct_adc)
        self.ivs2.correct_adc = self.apply_one(*args)

        # Noise reduction
        args = (section, 'reduce noise', CFG_BOOLEAN, self.ivs2.reduce_noise)
        self.ivs2.reduce_noise = self.apply_one(*args)

        # Battery bias
        args = (section, 'battery bias', CFG_BOOLEAN, self.ivs2.battery_bias)
        self.ivs2.battery_bias = self.apply_one(*args)

    # -------------------------------------------------------------------------
    def apply_axes(self):
        """Method to apply the Plotting section "plot max x" and "plot max y"
           options read from the .cfg file to the associated object
           properties
        """
        section = 'Plotting'

        # Max x
        args = (section, 'plot max x', CFG_FLOAT, self.ivs2.plot_max_x)
        self.ivs2.plot_max_x = self.apply_one(*args)

        # Max y
        args = (section, 'plot max y', CFG_FLOAT, self.ivs2.plot_max_y)
        self.ivs2.plot_max_y = self.apply_one(*args)

        # Set the axis lock property so the values are used when the
        # plot is generated
        self.ivs2.plot_lock_axis_ranges = True

    # -------------------------------------------------------------------------
    def apply_title(self):
        """Method to apply the Plotting section "title" option read from the
           .cfg file to the associated object property
        """
        section = 'Plotting'
        args = (section, 'title', CFG_STRING, self.ivs2.plot_title)
        self.ivs2.plot_title = self.apply_one(*args)

    # -------------------------------------------------------------------------
    def apply_arduino(self):
        """Method to apply the Arduino section options read from the
           .cfg file to the associated object properties
        """
        section = 'Arduino'

        # SPI clock divider
        args = (section, 'spi clock div', CFG_INT, self.ivs2.spi_clk_div)
        self.ivs2.spi_clk_div = self.apply_one(*args)

        # Max IV points
        args = (section, 'max iv points', CFG_INT, self.ivs2.max_iv_points)
        self.ivs2.max_iv_points = self.apply_one(*args)

        # Min Isc ADC
        args = (section, 'min isc adc', CFG_INT, self.ivs2.min_isc_adc)
        self.ivs2.min_isc_adc = self.apply_one(*args)

        # Max Isc poll
        args = (section, 'max isc poll', CFG_INT, self.ivs2.max_isc_poll)
        self.ivs2.max_isc_poll = self.apply_one(*args)

        # Isc stable ADC
        args = (section, 'isc stable adc', CFG_INT, self.ivs2.isc_stable_adc)
        self.ivs2.isc_stable_adc = self.apply_one(*args)

        # Max discards
        args = (section, 'max discards', CFG_INT, self.ivs2.max_discards)
        self.ivs2.max_discards = self.apply_one(*args)

        # Aspect height
        args = (section, 'aspect height', CFG_INT, self.ivs2.aspect_height)
        self.ivs2.aspect_height = self.apply_one(*args)

        # Aspect width
        args = (section, 'aspect width', CFG_INT, self.ivs2.aspect_width)
        self.ivs2.aspect_width = self.apply_one(*args)

    # -------------------------------------------------------------------------
    def save(self, copy_dir=None):
        """Method to save preferences and other configuration to the
           .cfg file
        """
        if DEBUG_CONFIG:
            dbg_str = ("save: Writing config to " +
                       self.cfg_filename)
            self.ivs2.logger.print_and_log(dbg_str)
        # Attempt to open the file for writing
        try:
            with open(self.cfg_filename, "wb") as cfg_fp:
                # Write config to file
                self.cfg.write(cfg_fp)
        except IOError:
            # Failed to open file for writing
            err_str = "Couldn't open config file for writing"
            self.ivs2.logger.print_and_log(err_str)
            return

        # Copy the file to the specified directory (if any, and if it is
        # actually a directory)
        if copy_dir is not None and os.path.isdir(copy_dir):
            self.copy_file(copy_dir)

    # -------------------------------------------------------------------------
    def save_snapshot(self):
        """Method to save preferences and other configuration to the
           .cfg file from the snapshot copy
        """
        if DEBUG_CONFIG:
            dbg_str = ("save_snapshot: Writing snapshot config to " +
                       self.cfg_filename)
            self.ivs2.logger.print_and_log(dbg_str)
        # Attempt to open the file for writing
        try:
            with open(self.cfg_filename, "wb") as cfg_fp:
                self.cfg_snapshot.write(cfg_fp)
        except IOError:
            # Failed to open file for writing
            err_str = "Couldn't open config file for writing"
            self.ivs2.logger.print_and_log(err_str)

    # -------------------------------------------------------------------------
    def copy_file(self, dir):
        """Method to copy the current .cfg file to the specified directory
        """
        if os.path.dirname(self.cfg_filename) == dir:
            # Return without doing anything if the property is already
            # pointing to the specified directory
            return
        if DEBUG_CONFIG:
            dbg_str = ("copy_file: Copying config from " +
                       self.cfg_filename + " to " + dir)
            self.ivs2.logger.print_and_log(dbg_str)
        try:
            shutil.copy(self.cfg_filename, dir)
        except shutil.Error as e:
            err_str = "Couldn't copy config file to " + dir
            err_str += " ({})".format(e)
            self.ivs2.logger.print_and_log(err_str)

    # -------------------------------------------------------------------------
    def populate(self):
        """Method to populate the ConfigParser object from the current
           property values
        """
        # Start with a fresh ConfigParser object
        self.cfg = ConfigParser.SafeConfigParser()

        # General config
        section = "General"
        self.cfg.add_section(section)
        self.cfg_set(section, 'x pixels', self.ivs2.x_pixels)

        # USB port config
        section = "USB"
        self.cfg.add_section(section)
        self.cfg_set(section, 'port', self.ivs2.usb_port)
        self.cfg_set(section, 'baud', self.ivs2.usb_baud)

        # Calibration
        section = "Calibration"
        self.cfg.add_section(section)
        self.cfg_set(section, 'voltage', self.ivs2.v_cal)
        self.cfg_set(section, 'current', self.ivs2.i_cal)
        self.cfg_set(section, 'bias battery voltage', self.ivs2.v_batt)
        self.cfg_set(section, 'bias battery resistance', self.ivs2.r_batt)
        self.cfg_set(section, 'r1 ohms', self.ivs2.vdiv_r1)
        self.cfg_set(section, 'r2 ohms', self.ivs2.vdiv_r2)
        self.cfg_set(section, 'rf ohms', self.ivs2.amm_op_amp_rf)
        self.cfg_set(section, 'rg ohms', self.ivs2.amm_op_amp_rg)
        self.cfg_set(section, 'shunt max volts',
                     self.ivs2.amm_shunt_max_volts)

        # Plotting config
        section = "Plotting"
        self.cfg.add_section(section)
        self.cfg_set(section, 'plot power', self.ivs2.plot_power)
        self.cfg_set(section, 'fancy labels', self.ivs2.fancy_labels)
        self.cfg_set(section, 'linear', self.ivs2.linear)
        self.cfg_set(section, 'font scale', self.ivs2.font_scale)
        self.cfg_set(section, 'line scale', self.ivs2.line_scale)
        self.cfg_set(section, 'point scale', self.ivs2.point_scale)
        self.cfg_set(section, 'correct adc', self.ivs2.correct_adc)
        self.cfg_set(section, 'reduce noise', self.ivs2.reduce_noise)
        self.cfg_set(section, 'battery bias', self.ivs2.battery_bias)

        # Arduino config
        section = "Arduino"
        self.cfg.add_section(section)
        self.cfg_set(section, 'spi clock div', self.ivs2.spi_clk_div)
        self.cfg_set(section, 'max iv points', self.ivs2.max_iv_points)
        self.cfg_set(section, 'min isc adc', self.ivs2.min_isc_adc)
        self.cfg_set(section, 'max isc poll', self.ivs2.max_isc_poll)
        self.cfg_set(section, 'isc stable adc', self.ivs2.isc_stable_adc)
        self.cfg_set(section, 'max discards', self.ivs2.max_discards)
        self.cfg_set(section, 'aspect height', self.ivs2.aspect_height)
        self.cfg_set(section, 'aspect width', self.ivs2.aspect_width)

    # -------------------------------------------------------------------------
    def add_axes_and_title(self):
        self.cfg_set("Plotting", 'plot max x', self.ivs2.plot_max_x)
        self.cfg_set("Plotting", 'plot max y', self.ivs2.plot_max_y)
        self.cfg_set("Plotting", 'title', self.ivs2.plot_title)


# The (extended) PrintAndLog class
#
class PrintAndLog(IV_Swinger.PrintAndLog):
    """Provides printing and logging methods (extended from IV_Swinger)"""

    # -------------------------------------------------------------------------
    def terminate_log(self):
        """Add newline to end of log file"""

        with open(IV_Swinger.PrintAndLog.log_file_name, "a") as f:
            f.write("\n")


# IV Swinger2 plotter class
#
class IV_Swinger2_plotter(IV_Swinger_plotter.IV_Swinger_plotter):
    """IV Swinger 2 plotter class (extended from IV_Swinger_plotter)"""

    def __init__(self):
        self.csv_proc = None
        IV_Swinger_plotter.IV_Swinger_plotter.__init__(self)
        self._csv_files = None
        self._plot_dir = None
        self._args = None
        self._current_img = None
        self._x_pixels = None
        self._generate_pdf = True
        self._curve_names = None
        self._title = None
        self._fancy_labels = True
        self._label_all_iscs = False
        self._label_all_mpps = False
        self._mpp_watts_only = False
        self._label_all_vocs = False
        self._linear = True
        self._overlay = False
        self._plot_power = True
        self._font_scale = 1.0
        self._line_scale = 1.0
        self._point_scale = 1.0
        self._logger = None
        self._ivsp_ivse = None

    # ---------------------------------
    @property
    def csv_files(self):
        """List of CSV files
        """
        return self._csv_files

    @csv_files.setter
    def csv_files(self, value):
        self._csv_files = value

    # ---------------------------------
    @property
    def plot_dir(self):
        """Directory use for plotting
        """
        return self._plot_dir

    @plot_dir.setter
    def plot_dir(self, value):
        self._plot_dir = value

    # ---------------------------------
    @property
    def args(self):
        """The argparse.Namespace() object used to specify options to
           the plotter
        """
        return self._args

    @args.setter
    def args(self, value):
        self._args = value

    # ---------------------------------
    @property
    def current_img(self):
        """File name of the current GIF
        """
        return self._current_img

    @current_img.setter
    def current_img(self, value):
        self._current_img = value

    # ---------------------------------
    @property
    def x_pixels(self):
        """Width in pixels of the GIFs
        """
        return self._x_pixels

    @x_pixels.setter
    def x_pixels(self, value):
        self._x_pixels = value

    # ---------------------------------
    @property
    def generate_pdf(self):
        """Value of the generate PDF flag
        """
        return self._generate_pdf

    @generate_pdf.setter
    def generate_pdf(self, value):
        if value not in set([True, False]):
            raise ValueError("generate_pdf must be boolean")
        self._generate_pdf = value

    # ---------------------------------
    @property
    def curve_names(self):
        """Value of the curve names list
        """
        return self._curve_names

    @curve_names.setter
    def curve_names(self, value):
        self._curve_names = value

    # ---------------------------------
    @property
    def title(self):
        """Value of the plot title
        """
        return self._title

    @title.setter
    def title(self, value):
        self._title = value

    # ---------------------------------
    @property
    def fancy_labels(self):
        """Value of the fancy labels flag
        """
        return self._fancy_labels

    @fancy_labels.setter
    def fancy_labels(self, value):
        if value not in set([True, False]):
            raise ValueError("fancy_labels must be boolean")
        self._fancy_labels = value

    # ---------------------------------
    @property
    def label_all_iscs(self):
        """Value of the label all Iscs flag
        """
        return self._label_all_iscs

    @label_all_iscs.setter
    def label_all_iscs(self, value):
        if value not in set([True, False]):
            raise ValueError("label_all_iscs must be boolean")
        self._label_all_iscs = value

    # ---------------------------------
    @property
    def label_all_mpps(self):
        """Value of the label all Mpps flag
        """
        return self._label_all_mpps

    @label_all_mpps.setter
    def label_all_mpps(self, value):
        if value not in set([True, False]):
            raise ValueError("label_all_mpps must be boolean")
        self._label_all_mpps = value

    # ---------------------------------
    @property
    def mpp_watts_only(self):
        """Value of the MPP watts only flag
        """
        return self._mpp_watts_only

    @mpp_watts_only.setter
    def mpp_watts_only(self, value):
        if value not in set([True, False]):
            raise ValueError("mpp_watts_only must be boolean")
        self._mpp_watts_only = value

    # ---------------------------------
    @property
    def label_all_vocs(self):
        """Value of the label all Vocs flag
        """
        return self._label_all_vocs

    @label_all_vocs.setter
    def label_all_vocs(self, value):
        if value not in set([True, False]):
            raise ValueError("label_all_vocs must be boolean")
        self._label_all_vocs = value

    # ---------------------------------
    @property
    def linear(self):
        """Value of the linear flag
        """
        return self._linear

    @linear.setter
    def linear(self, value):
        if value not in set([True, False]):
            raise ValueError("linear must be boolean")
        self._linear = value

    # ---------------------------------
    @property
    def overlay(self):
        """Value of the overlay flag
        """
        return self._overlay

    @overlay.setter
    def overlay(self, value):
        if value not in set([True, False]):
            raise ValueError("overlay must be boolean")
        self._overlay = value

    # ---------------------------------
    @property
    def plot_power(self):
        """Value of the plot power flag
        """
        return self._plot_power

    @plot_power.setter
    def plot_power(self, value):
        if value not in set([True, False]):
            raise ValueError("plot_power must be boolean")
        self._plot_power = value

    # ---------------------------------
    @property
    def font_scale(self):
        """Value of the font scale value
        """
        return self._font_scale

    @font_scale.setter
    def font_scale(self, value):
        self._font_scale = value

    # ---------------------------------
    @property
    def line_scale(self):
        """Value of the line scale value
        """
        return self._line_scale

    @line_scale.setter
    def line_scale(self, value):
        self._line_scale = value

    # ---------------------------------
    @property
    def point_scale(self):
        """Value of the point scale value
        """
        return self._point_scale

    @point_scale.setter
    def point_scale(self, value):
        self._point_scale = value

    # ---------------------------------
    @property
    def logger(self):
        """Logger object"""
        return self._logger

    @logger.setter
    def logger(self, value):
        self._logger = value

    # ---------------------------------
    @property
    def ivsp_ivse(self):
        """IV Swinger object (as extended in IV_Swinger_plotter)"""
        return self._ivsp_ivse

    @ivsp_ivse.setter
    def ivsp_ivse(self, value):
        self._ivsp_ivse = value

    # -------------------------------------------------------------------------
    def set_default_args(self):
        """Method to set argparse args to default values"""

        self.args.name = self.curve_names
        self.args.overlay_name = "overlaid_" + os.path.basename(self.plot_dir)
        self.args.title = self.title
        self.args.fancy_labels = self.fancy_labels
        self.args.interactive = False
        self.args.label_all_iscs = self.label_all_iscs
        self.args.label_all_mpps = self.label_all_mpps
        self.args.mpp_watts_only = self.mpp_watts_only
        self.args.label_all_vocs = self.label_all_vocs
        self.args.linear = self.linear
        self.args.overlay = self.overlay
        self.args.plot_power = self.plot_power
        self.args.recalc_isc = False
        self.args.use_gnuplot = False
        self.args.gif = False
        self.args.png = False
        self.args.scale = 1.0
        self.args.font_scale = self.font_scale
        self.args.line_scale = self.line_scale
        self.args.point_scale = self.point_scale
        self.args.plot_scale = 1.0
        self.args.plot_x_scale = 1.0
        self.args.plot_y_scale = 1.0
        self.args.max_x = self.max_x
        self.args.max_y = self.max_y

    # -------------------------------------------------------------------------
    def plot_graphs_to_pdf(self, ivs, csvp):
        """Method to plot the graphs to a PDF"""

        self.args.gif = False
        self.args.png = False
        self.set_ivs_properties(self.args, ivs)
        ivs.plot_graphs(self.args, csvp)

    # -------------------------------------------------------------------------
    def plot_graphs_to_gif(self, ivs, csvp):
        """Method to plot the graphs to a GIF"""

        # Pyplot cannot generate GIFs on Windows, so we generate a PNG
        # and then convert it to GIF with PIL (regardless of platform).
        #
        # Before calling the plot_graphs() method, we have to adjust the
        # scale parameters and the DPI value based on the value of the
        # x_pixels property. The x_pixels property can be changed from a
        # combobox in the GUI.
        self.args.png = True
        self.set_ivs_properties(self.args, ivs)
        default_dpi = 100.0
        default_x_pixels = 1100.0
        ivs.plot_dpi = default_dpi * (self.x_pixels/default_x_pixels)
        ivs.plot_graphs(self.args, csvp)
        png_file = ivs.plt_img_filename
        (file, ext) = os.path.splitext(png_file)
        gif_file = file + ".gif"
        im = Image.open(png_file)
        im.save(gif_file)
        self.current_img = gif_file

    # -------------------------------------------------------------------------
    def run(self):
        """Main method to run the IV Swinger 2 plotter"""

        # The plotter uses the argparse library for command line
        # argument parsing. Here we just need to "manually" create an
        # argparse.Namespace() object and populate it.
        self.args = argparse.Namespace()
        self.set_default_args()

        # Change to plot directory so files will be created there
        os.chdir(self.plot_dir)

        # Create IV Swinger object (as extended in IV_Swinger_plotter)
        self.ivsp_ivse = IV_Swinger_plotter.IV_Swinger_extended()
        self.set_ivs_properties(self.args, self.ivsp_ivse)
        self.ivsp_ivse.logger = self.logger

        # Process all CSV files
        self.csv_proc = IV_Swinger_plotter.CsvFileProcessor(self.args,
                                                            self.csv_files,
                                                            self.ivsp_ivse,
                                                            logger=self.logger)
        # Plot graphs to PDF
        if self.generate_pdf:
            self.plot_graphs_to_pdf(self.ivsp_ivse, self.csv_proc)

        # Plot graphs to GIF
        self.plot_graphs_to_gif(self.ivsp_ivse, self.csv_proc)

        # Capture max_x and max_y for locking feature
        self.max_x = self.ivsp_ivse.plot_max_x
        self.max_y = self.ivsp_ivse.plot_max_y


#  Main IV Swinger 2 class
#
class IV_Swinger2(IV_Swinger.IV_Swinger):
    """IV_Swinger derived class extended for IV Swinger 2
    """
    # Initializer
    def __init__(self, app_data_dir=None):
        IV_Swinger.IV_Swinger.__init__(self)
        self.lcd = None
        self.ivp = None
        self.prev_date_time_str = None
        # Property variables
        self._app_data_dir = app_data_dir
        self._hdd_output_dir = None
        self._file_prefix = "iv_swinger2_"
        self._serial_ports = []
        self._usb_port = None
        self._usb_baud = 57600
        self._serial_timeout = 0.1
        self._ser = None
        self._sio = None
        self._arduino_ready = False
        self._data_points = []
        self._unfiltered_adc_pairs = []
        self._adc_pairs = []
        self._adc_pairs_corrected = []
        self._adc_ch0_offset = 0
        self._adc_ch1_offset = 0
        self._adc_range = 4096.0
        self._msg_timer_timeout = 50
        self._vdiv_r1 = R1_DEFAULT
        self._vdiv_r2 = R2_DEFAULT
        self._amm_op_amp_rf = RF_DEFAULT
        self._amm_op_amp_rg = RG_DEFAULT
        self._adc_vref = 5.0             # ADC voltage reference = 5V
        self._amm_shunt_max_amps = 10.0  # Legacy - hardcoded
        self._amm_shunt_max_volts = (self._amm_shunt_max_amps *
                                     (SHUNT_DEFAULT / 1000000.0))
        self._v_cal = V_CAL_DEFAULT
        self._i_cal = I_CAL_DEFAULT
        self._v_batt = V_BATT_DEFAULT
        self._r_batt = R_BATT_DEFAULT
        self._plot_title = None
        self._current_img = None
        self._x_pixels = 770  # Default GIF width (770x595)
        self._plot_lock_axis_ranges = False
        self._generate_pdf = True
        self._fancy_labels = True
        self._linear = True
        self._plot_power = False
        self._font_scale = FONT_SCALE_DEFAULT
        self._line_scale = LINE_SCALE_DEFAULT
        self._point_scale = POINT_SCALE_DEFAULT
        self._correct_adc = True
        self._reduce_noise = True
        self._battery_bias = False
        self._arduino_ver_major = -1
        self._arduino_ver_minor = -1
        self._arduino_ver_patch = -1
        self._spi_clk_div = SPI_CLK_DEFAULT
        self._max_iv_points = MAX_IV_POINTS_DEFAULT
        self._min_isc_adc = MIN_ISC_ADC_DEFAULT
        self._max_isc_poll = MAX_ISC_POLL_DEFAULT
        self._isc_stable_adc = ISC_STABLE_DEFAULT
        self._max_discards = MAX_DISCARDS_DEFAULT
        self._aspect_height = ASPECT_HEIGHT_DEFAULT
        self._aspect_width = ASPECT_WIDTH_DEFAULT
        # Configure logging and find serial ports
        self.configure_logging()
        self.find_serial_ports()

    # Properties
    # ---------------------------------
    @property
    def data_points(self):
        """Property to get the data points"""
        return self._data_points

    @data_points.setter
    def data_points(self, value):
        self._data_points = value

    # ---------------------------------
    @property
    def unfiltered_adc_pairs(self):
        """Property to get the unfiltered ADC value pairs. These are only
           captured when using a debug Arduino sketch.
        """
        return self._unfiltered_adc_pairs

    @unfiltered_adc_pairs.setter
    def unfiltered_adc_pairs(self, value):
        self._unfiltered_adc_pairs = value

    # ---------------------------------
    @property
    def adc_pairs(self):
        """Property to get the ADC value pairs"""
        return self._adc_pairs

    @adc_pairs.setter
    def adc_pairs(self, value):
        self._adc_pairs = value

    # ---------------------------------
    @property
    def adc_pairs_corrected(self):
        """Property to get the corrected ADC value pairs"""
        return self._adc_pairs_corrected

    @adc_pairs_corrected.setter
    def adc_pairs_corrected(self, value):
        self._adc_pairs_corrected = value

    # ---------------------------------
    @property
    def adc_range(self):
        """Property to get the ADC range (i.e. 2^^#bits)"""
        return self._adc_range

    @adc_range.setter
    def adc_range(self, value):
        self._adc_range = value

    # ---------------------------------
    @property
    def msg_timer_timeout(self):
        """Property to get the message timer timeout"""
        return self._msg_timer_timeout

    @msg_timer_timeout.setter
    def msg_timer_timeout(self, value):
        self._msg_timer_timeout = value

    # ---------------------------------
    @property
    def adc_vref(self):
        """Property to get the ADC reference voltage"""
        return self._adc_vref

    @adc_vref.setter
    def adc_vref(self, value):
        self._adc_vref = value

    # ---------------------------------
    @property
    def v_cal(self):
        """Property to get the voltage calibration value"""
        return self._v_cal

    @v_cal.setter
    def v_cal(self, value):
        self._v_cal = value

    # ---------------------------------
    @property
    def i_cal(self):
        """Property to get the current calibration value"""
        return self._i_cal

    @i_cal.setter
    def i_cal(self, value):
        self._i_cal = value

    # ---------------------------------
    @property
    def v_batt(self):
        """Property to get the bias battery voltage calibration value"""
        return self._v_batt

    @v_batt.setter
    def v_batt(self, value):
        self._v_batt = value

    # ---------------------------------
    @property
    def r_batt(self):
        """Property to get the bias battery resistance calibration value"""
        return self._r_batt

    @r_batt.setter
    def r_batt(self, value):
        self._r_batt = value

    # ---------------------------------
    @property
    def app_data_dir(self):
        """Application data directory where results, log files, and
           preferences are written. Default is platform-dependent.  The
           default can be overridden by setting the property after
           instantiation.
        """
        if self._app_data_dir is None:
            if sys.platform == 'darwin':
                # Mac
                self._app_data_dir = os.path.join(get_mac_dir(mac_app_sup_dir,
                                                              mac_domain_mask,
                                                              True)[0],
                                                  APP_NAME)
            elif sys.platform == 'win32':
                # Windows
                self._app_data_dir = os.path.join(os.environ['APPDATA'],
                                                  APP_NAME)
            else:
                # Linux
                self._app_data_dir = os.path.expanduser(os.path.join("~", "." +
                                                                     APP_NAME))
        return self._app_data_dir

    @app_data_dir.setter
    def app_data_dir(self, value):
        if not os.path.isabs(value):
            raise ValueError("app_data_dir must be an absolute path")
        self._app_data_dir = value

    # ---------------------------------
    @property
    def root_dir(self):
        """Alias for app_data_dir used by legacy (parent) IV_Swinger class"""
        return self.app_data_dir

    # ---------------------------------
    @property
    def hdd_output_dir(self):
        """Directory (on HDD) where a given run's results are written"""
        return self._hdd_output_dir

    @hdd_output_dir.setter
    def hdd_output_dir(self, value):
        if not os.path.isabs(value):
            raise ValueError("hdd_output_dir must be an absolute path")
        self._hdd_output_dir = value

    # ---------------------------------
    @property
    def serial_ports(self):
        """List of serial ports found on this computer"""
        return self._serial_ports

    @serial_ports.setter
    def serial_ports(self, value):
        self._serial_ports = value

    # ---------------------------------
    @property
    def file_prefix(self):
        """Prefix for data point CSV, GIF, and PDF files"""
        return self._file_prefix

    @file_prefix.setter
    def file_prefix(self, value):
        self._file_prefix = value

    # ---------------------------------
    @property
    def logs_dir(self):
        """ Directory on where log files are written"""
        logs_dir = self.app_data_dir + "/logs"
        return logs_dir

    # ---------------------------------
    @property
    def usb_port(self):
        """Property to get the current USB port path"""
        return self._usb_port

    @usb_port.setter
    def usb_port(self, value):
        self._usb_port = value

    # ---------------------------------
    @property
    def usb_baud(self):
        """Property to get the current USB baud rate"""
        return self._usb_baud

    @usb_baud.setter
    def usb_baud(self, value):
        self._usb_baud = value

    # ---------------------------------
    @property
    def serial_timeout(self):
        """Property to get the current serial timeout value"""
        return self._serial_timeout

    @serial_timeout.setter
    def serial_timeout(self, value):
        self._serial_timeout = value

    # ---------------------------------
    @property
    def arduino_ready(self):
        """Property to get flag that indicates if the Arduino is ready
        """
        return self._arduino_ready

    @arduino_ready.setter
    def arduino_ready(self, value):
        if value not in set([True, False]):
            raise ValueError("arduino_ready must be boolean")
        self._arduino_ready = value

    # ---------------------------------
    @property
    def plot_title(self):
        """Title for the plot
        """
        return self._plot_title

    @plot_title.setter
    def plot_title(self, value):
        self._plot_title = value

    # ---------------------------------
    @property
    def current_img(self):
        """File name of the current GIF
        """
        return self._current_img

    @current_img.setter
    def current_img(self, value):
        self._current_img = value

    # ---------------------------------
    @property
    def x_pixels(self):
        """Width in pixels of the GIFs
        """
        return self._x_pixels

    @x_pixels.setter
    def x_pixels(self, value):
        self._x_pixels = value

    # ---------------------------------
    @property
    def plot_lock_axis_ranges(self):
        """Value of the axis lock flag
        """
        return self._plot_lock_axis_ranges

    @plot_lock_axis_ranges.setter
    def plot_lock_axis_ranges(self, value):
        if value not in set([True, False]):
            raise ValueError("plot_lock_axis_ranges must be boolean")
        self._plot_lock_axis_ranges = value

    # ---------------------------------
    @property
    def generate_pdf(self):
        """Value of the generate PDF flag
        """
        return self._generate_pdf

    @generate_pdf.setter
    def generate_pdf(self, value):
        if value not in set([True, False]):
            raise ValueError("generate_pdf must be boolean")
        self._generate_pdf = value

    # ---------------------------------
    @property
    def fancy_labels(self):
        """Value of the fancy labels flag
        """
        return self._fancy_labels

    @fancy_labels.setter
    def fancy_labels(self, value):
        if value not in set([True, False]):
            raise ValueError("fancy_labels must be boolean")
        self._fancy_labels = value

    # ---------------------------------
    @property
    def linear(self):
        """Value of the linear flag
        """
        return self._linear

    @linear.setter
    def linear(self, value):
        if value not in set([True, False]):
            raise ValueError("linear must be boolean")
        self._linear = value

    # ---------------------------------
    @property
    def plot_power(self):
        """Value of the plot power flag
        """
        return self._plot_power

    @plot_power.setter
    def plot_power(self, value):
        if value not in set([True, False]):
            raise ValueError("plot_power must be boolean")
        self._plot_power = value

    # ---------------------------------
    @property
    def font_scale(self):
        """Value of the font scale value
        """
        return self._font_scale

    @font_scale.setter
    def font_scale(self, value):
        self._font_scale = value

    # ---------------------------------
    @property
    def line_scale(self):
        """Value of the line scale value
        """
        return self._line_scale

    @line_scale.setter
    def line_scale(self, value):
        self._line_scale = value

    # ---------------------------------
    @property
    def point_scale(self):
        """Value of the point scale value
        """
        return self._point_scale

    @point_scale.setter
    def point_scale(self, value):
        self._point_scale = value

    # ---------------------------------
    @property
    def correct_adc(self):
        """Value of the correct_adc flag
        """
        return self._correct_adc

    @correct_adc.setter
    def correct_adc(self, value):
        if value not in set([True, False]):
            raise ValueError("correct_adc must be boolean")
        self._correct_adc = value

    # ---------------------------------
    @property
    def reduce_noise(self):
        """Value of the reduce_noise flag
        """
        return self._reduce_noise

    @reduce_noise.setter
    def reduce_noise(self, value):
        if value not in set([True, False]):
            raise ValueError("reduce_noise must be boolean")
        self._reduce_noise = value

    # ---------------------------------
    @property
    def battery_bias(self):
        """Value of the battery_bias flag
        """
        return self._battery_bias

    @battery_bias.setter
    def battery_bias(self, value):
        if value not in set([True, False]):
            raise ValueError("battery_bias must be boolean")
        self._battery_bias = value

    # ---------------------------------
    @property
    def spi_clk_div(self):
        """Arduino: SPI bus clock divider value
        """
        return self._spi_clk_div

    @spi_clk_div.setter
    def spi_clk_div(self, value):
        self._spi_clk_div = value

    # ---------------------------------
    @property
    def max_iv_points(self):
        """Arduino: Max number of I/V pairs to capture
        """
        return self._max_iv_points

    @max_iv_points.setter
    def max_iv_points(self, value):
        self._max_iv_points = value

    # ---------------------------------
    @property
    def min_isc_adc(self):
        """Arduino: Minimum ADC count for Isc
        """
        return self._min_isc_adc

    @min_isc_adc.setter
    def min_isc_adc(self, value):
        self._min_isc_adc = value

    # ---------------------------------
    @property
    def max_isc_poll(self):
        """Arduino: Max loops to wait for Isc to stabilize
        """
        return self._max_isc_poll

    @max_isc_poll.setter
    def max_isc_poll(self, value):
        self._max_isc_poll = value

    # ---------------------------------
    @property
    def isc_stable_adc(self):
        """Arduino: Stable Isc changes less than this
        """
        return self._isc_stable_adc

    @isc_stable_adc.setter
    def isc_stable_adc(self, value):
        self._isc_stable_adc = value

    # ---------------------------------
    @property
    def max_discards(self):
        """Arduino: Maximum consecutive discarded points
        """
        return self._max_discards

    @max_discards.setter
    def max_discards(self, value):
        self._max_discards = value

    # ---------------------------------
    @property
    def aspect_height(self):
        """Arduino: Height of graph's aspect ratio (max 8)
        """
        return self._aspect_height

    @aspect_height.setter
    def aspect_height(self, value):
        self._aspect_height = value

    # ---------------------------------
    @property
    def aspect_width(self):
        """Arduino: Width of graph's aspect ratio (max 8)
        """
        return self._aspect_width

    @aspect_width.setter
    def aspect_width(self, value):
        self._aspect_width = value

    # Derived properties
    # ---------------------------------
    @property
    def adc_inc(self):
        """Volts per ADC increment"""
        adc_inc = (1.0 / self.adc_range) * self.adc_vref
        return adc_inc

    # ---------------------------------
    @property
    def voc_adc(self):
        """Property to get the ADC voltage value at the Voc point"""
        # The last (Voc) CH0 value is the Voc voltage ADC reading
        voc_adc = self.adc_pairs[-1][0]
        return voc_adc

    # ---------------------------------
    @property
    def isc_adc(self):
        """Property to get the ADC current value at the Isc point"""
        # The first CH1 value is the Isc current ADC reading
        isc_adc = self.adc_pairs[0][1]
        return isc_adc

    # ---------------------------------
    @property
    def vdiv_ratio(self):
        """Voltage divider ratio"""
        vdiv_ratio = self.vdiv_r2 / (self.vdiv_r1 + self.vdiv_r2)
        return vdiv_ratio

    # ---------------------------------
    @property
    def v_mult(self):
        """Voltage multiplier"""
        v_mult = (self.adc_inc / self.vdiv_ratio) * self.v_cal
        return v_mult

    # ---------------------------------
    @property
    def i_mult(self):
        """Current multiplier"""
        i_mult = ((self.adc_inc /
                   self.amm_op_amp_gain /
                   self.amm_shunt_resistance) * self.i_cal)
        return i_mult

    # ---------------------------------
    @property
    def v_adj(self):
        """Voltage adjustment value"""

        # Compensate for (as-of-yet-not-understood) effect where the voltage
        # of the final measured points is greater than Voc
        v_adj = 1.0
        last_measured_adc = self.adc_pairs[-2][0]
        last_measured_minus_offset = last_measured_adc - self._adc_ch0_offset
        voc_adc_minus_offset = self.voc_adc - self._adc_ch0_offset
        if last_measured_minus_offset > voc_adc_minus_offset:
            v_adj = (float(voc_adc_minus_offset) /
                     float(last_measured_minus_offset))
        return v_adj

    # ---------------------------------
    @property
    def arduino_sketch_ver(self):
        """Arduino sketch version"""
        if self._arduino_ver_major > -1:
            return "%d.%d.%d" % (self._arduino_ver_major,
                                 self._arduino_ver_minor,
                                 self._arduino_ver_patch)
        else:
            return "Unknown"

    # ---------------------------------
    @property
    def pdf_filename(self):
        """PDF file name"""
        dts = extract_date_time_str(self.hdd_output_dir)
        pdf_filename = os.path.join(self.hdd_output_dir,
                                    self.file_prefix + dts + ".pdf")
        return pdf_filename

    # -------------------------------------------------------------------------
    def find_serial_ports(self):
        """Method to find the serial ports on this computer
        """

        # Get list of serial ports and put it in the serial_ports
        # property
        self.serial_ports = list(serial.tools.list_ports.comports())

    # -------------------------------------------------------------------------
    def find_arduino_port(self):
        """Method to identify the serial port connected to the Arduino
        """

        # If one of the serial ports has "uino" (Arduino, Genuino, etc.)
        # in the name, choose that one. Note that this will choose the
        # first one if more than one Arduino is connected.
        if self.usb_port is None:
            for serial_port in self.serial_ports:
                if "uino" in str(serial_port):
                    self.usb_port = str(serial_port).split(' ')[0]
                    break

    # -------------------------------------------------------------------------
    def reset_arduino(self):
        """Method to reset the Arduino and establish communication to it
           over USB
        """

        # Set up to talk to Arduino via USB (this resets the Arduino)
        if self._ser is not None and self._ser.is_open:
            # First close port if it is already open
            self._ser.close()
        try:
            self._ser = serial.Serial(self.usb_port, self.usb_baud,
                                      timeout=self.serial_timeout)
        except (serial.SerialException) as e:
            self.logger.print_and_log("reset_arduino: ({})".format(e))
            return RC_SERIAL_EXCEPTION

        # Create buffered text stream
        self._sio = io.TextIOWrapper(io.BufferedRWPair(self._ser, self._ser),
                                     line_buffering=True)

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def wait_for_arduino_ready_and_ack(self, write_eeprom=False):
        """Method to wait for the Arduino ready message, and send
           acknowledgement
        """

        # Return immediately if ready flag is already set
        if self.arduino_ready:
            return RC_SUCCESS

        # Otherwise wait for ready message from Arduino
        rc = self.receive_msg_from_arduino()
        version_intro = "IV Swinger2 sketch version"
        if (rc == RC_SUCCESS and
                self.msg_from_arduino.startswith(version_intro)):
            rc = self.get_arduino_sketch_ver(self.msg_from_arduino)
            if rc != RC_SUCCESS:
                return rc
            rc = self.receive_msg_from_arduino()
        if rc == RC_SUCCESS and self.msg_from_arduino == unicode('Ready\n'):
            self.arduino_ready = True
        elif rc != RC_SUCCESS:
            return rc
        else:
            err_str = ("ERROR: Malformed Arduino ready message: " +
                       self.msg_from_arduino)
            self.logger.print_and_log(err_str)
            return RC_FAILURE

        # Send config message(s) to Arduino
        rc = self.send_config_msgs_to_arduino(write_eeprom)
        if rc != RC_SUCCESS:
            return rc

        # Request EEPROM values from Arduino
        self.eeprom_values_received = False
        rc = self.request_eeprom_dump()
        if rc != RC_SUCCESS:
            return rc
        # Special case: EEPROM has never been written (and therefore no values
        # are returned).  We want to write it with the current values rather
        # than waiting for a calibration.
        if (self.arduino_sketch_ver_ge("1.1.0") and
                not self.eeprom_values_received):
            rc = self.send_config_msgs_to_arduino(write_eeprom=True)
            if rc != RC_SUCCESS:
                return rc
            rc = self.request_eeprom_dump()
            if rc != RC_SUCCESS:
                return rc

        # Send ready message to Arduino
        rc = self.send_msg_to_arduino("Ready")
        if rc != RC_SUCCESS:
            return rc

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def send_config_msgs_to_arduino(self, write_eeprom=False):
        """Method to send config messages to the Arduino, waiting for each
        reply"""
        config_dict = {"CLK_DIV": self.spi_clk_div,
                       "MAX_IV_POINTS": self.max_iv_points,
                       "MIN_ISC_ADC": self.min_isc_adc,
                       "MAX_ISC_POLL": self.max_isc_poll,
                       "ISC_STABLE_ADC": self.isc_stable_adc,
                       "MAX_DISCARDS": self.max_discards,
                       "ASPECT_HEIGHT": self.aspect_height,
                       "ASPECT_WIDTH": self.aspect_width}
        for config_type, config_value in config_dict.iteritems():
            rc = self.send_one_config_msg_to_arduino(config_type, config_value)
            if rc != RC_SUCCESS:
                return rc

        if write_eeprom and self.arduino_sketch_ver_ge("1.1.0"):
            config_values = [(str(EEPROM_VALID_ADDR) + " " +
                              EEPROM_VALID_VALUE),
                             (str(EEPROM_VALID_COUNT_ADDR) + " " +
                              str(EEPROM_VALID_COUNT)),
                             (str(EEPROM_R1_OHMS_ADDR) + " " +
                              str(int(self.vdiv_r1))),
                             (str(EEPROM_R2_OHMS_ADDR) + " " +
                              str(int(self.vdiv_r2))),
                             (str(EEPROM_RF_OHMS_ADDR) + " " +
                              str(int(self.amm_op_amp_rf))),
                             (str(EEPROM_RG_OHMS_ADDR) + " " +
                              str(int(self.amm_op_amp_rg))),
                             (str(EEPROM_SHUNT_UOHMS_ADDR) + " " +
                              str(int(self.amm_shunt_resistance *
                                      1000000.0))),
                             (str(EEPROM_V_CAL_X1M_ADDR) + " " +
                              str(int(self.v_cal * 1000000.0))),
                             (str(EEPROM_I_CAL_X1M_ADDR) + " " +
                              str(int(self.i_cal * 1000000.0))),
                             (str(EEPROM_V_BATT_X1M_ADDR) + " " +
                              str(int(self.v_batt * 1000000.0))),
                             (str(EEPROM_R_BATT_X1M_ADDR) + " " +
                              str(int(self.r_batt * 1000000.0)))]
            for config_value in config_values:
                rc = self.send_one_config_msg_to_arduino("WRITE_EEPROM",
                                                         config_value)
                if rc != RC_SUCCESS:
                    return rc

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def send_one_config_msg_to_arduino(self, config_type, config_value):
        """Method to send one config message to the Arduino, waiting for the
        reply"""
        rc = self.send_msg_to_arduino("Config: " + config_type +
                                      " " + str(config_value))
        if rc != RC_SUCCESS:
            return rc
        self.msg_from_arduino = "None"
        while self.msg_from_arduino != unicode('Config processed\n'):
            rc = self.receive_msg_from_arduino()
            if rc != RC_SUCCESS:
                return rc

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def send_msg_to_arduino(self, msg):
        """Method to send a message to the Arduino"""

        if self.arduino_sketch_ver_lt("1.1.0"):
            MAX_MSG_LEN_TO_ARDUINO = 30
        else:
            MAX_MSG_LEN_TO_ARDUINO = 35
        if len(msg + "\n") > MAX_MSG_LEN_TO_ARDUINO:
            err_str = "ERROR: Message to Arduino is too long: " + msg
            self.logger.print_and_log(err_str)
            return RC_FAILURE

        try:
            self._sio.write(unicode(msg + "\n"))
        except (serial.SerialException) as e:
            self.logger.print_and_log("send_msg_to_arduino: ({})".format(e))
            return RC_SERIAL_EXCEPTION

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def receive_msg_from_arduino(self):
        """Method to receive a single message from the Arduino"""

        msg_timer = self.msg_timer_timeout
        while msg_timer:
            try:
                self.msg_from_arduino = self._sio.readline()
            except (serial.SerialException) as e:
                err_str = "receive_msg_from_arduino: ({})"
                self.logger.print_and_log(err_str.format(e))
                return RC_SERIAL_EXCEPTION
            except UnicodeDecodeError:
                return RC_BAUD_MISMATCH
            if len(self.msg_from_arduino) > 0:
                self.log_msg_from_arduino(self.msg_from_arduino)
                return RC_SUCCESS
            msg_timer -= 1

        self.msg_from_arduino = "NONE"
        return RC_TIMEOUT

    # -------------------------------------------------------------------------
    def receive_data_from_arduino(self):
        """Method to receive raw IV data from the Arduino"""

        received_msgs = []
        while True:
            # Loop receiving messages and appending them to the
            # received_msgs list until the "Output complete" message is
            # received
            rc = self.receive_msg_from_arduino()
            if rc == RC_SUCCESS:
                received_msgs.append(self.msg_from_arduino)
                if self.msg_from_arduino == unicode('Output complete\n'):
                    break
            else:
                return rc

        # Loop through list, filling the adc_pairs list with the CH0/CH1
        # pairs
        self.adc_pairs = []
        self.unfiltered_adc_pairs = []
        adc_re = re.compile('CH0:(\d+)\s+CH1:(\d+)')
        unfiltered_adc_re_str = 'Unfiltered CH0:(\d+)\s+Unfiltered CH1:(\d+)'
        unfiltered_adc_re = re.compile(unfiltered_adc_re_str)
        for msg in received_msgs:
            if msg.startswith('Polling for stable Isc timed out'):
                return RC_ISC_TIMEOUT
            match = adc_re.search(msg)
            if match:
                ch0_adc = int(match.group(1))
                ch1_adc = int(match.group(2))
                self.adc_pairs.append((ch0_adc, ch1_adc))
            unfiltered_match = unfiltered_adc_re.search(msg)
            if unfiltered_match:
                ch0_adc = int(unfiltered_match.group(1))
                ch1_adc = int(unfiltered_match.group(2))
                self.unfiltered_adc_pairs.append((ch0_adc, ch1_adc))

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def log_msg_from_arduino(self, msg):
        """Method to log a message from the Arduino"""
        self.logger.log("Arduino: " + msg.rstrip())

    # -------------------------------------------------------------------------
    def request_eeprom_dump(self):
        """Method to send a DUMP_EEPROM 'config' message to the Arduino and
           capture the values returned
        """
        if self.arduino_sketch_ver_lt("1.1.0"):
            return RC_SUCCESS
        rc = self.send_msg_to_arduino("Config: DUMP_EEPROM")
        if rc != RC_SUCCESS:
            return rc
        self.msg_from_arduino = "None"
        while self.msg_from_arduino != unicode('Config processed\n'):
            rc = self.receive_msg_from_arduino()
            if rc != RC_SUCCESS:
                return rc
            if self.msg_from_arduino.startswith("EEPROM addr"):
                rc = self.process_eeprom_value()
                self.eeprom_values_received = True
                if rc != RC_SUCCESS:
                    return rc

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def get_arduino_sketch_ver(self, msg):
        """Method to extract the version number of the Arduino sketch from the
           message containing it
        """
        sketch_ver_re = re.compile('sketch version (\d+)\.(\d+)\.(\d+)')
        match = sketch_ver_re.search(msg)
        if match:
            self._arduino_ver_major = int(match.group(1))
            self._arduino_ver_minor = int(match.group(2))
            self._arduino_ver_patch = int(match.group(3))
        else:
            err_str = "ERROR: Bad Arduino version message: " + msg
            self.logger.print_and_log(err_str)
            return RC_FAILURE

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def compare_arduino_sketch_ver(self, test_version):
        """Method to compare the Arduino sketch version with the
           specified value. Returns:
              SKETCH_VER_LT: if sketch version is lower
              SKETCH_VER_EQ: if sketch version is equal
              SKETCH_VER_GT: if sketch version is greater
        """
        test_ver_re = re.compile('(\d+)\.(\d+)\.(\d+)')
        match = test_ver_re.search(test_version)
        if match:
            test_ver_major = int(match.group(1))
            test_ver_minor = int(match.group(2))
            test_ver_patch = int(match.group(3))
            if (self._arduino_ver_major < test_ver_major or
                (self._arduino_ver_major == test_ver_major and
                 self._arduino_ver_minor < test_ver_minor) or
                (self._arduino_ver_major == test_ver_major and
                 self._arduino_ver_minor == test_ver_minor and
                 self._arduino_ver_patch < test_ver_patch)):
                return SKETCH_VER_LT
            elif (self._arduino_ver_major == test_ver_major and
                  self._arduino_ver_minor == test_ver_minor and
                  self._arduino_ver_patch == test_ver_patch):
                return SKETCH_VER_EQ
            else:
                return SKETCH_VER_GT
        else:
            err_str = "ERROR: Bad test version: " + test_version
            self.logger.print_and_log(err_str)
            return SKETCH_VER_ERR

    # -------------------------------------------------------------------------
    def arduino_sketch_ver_lt(self, test_version):
        """Method to test whether the Arduino sketch version is less than the
           specified value
        """
        if self.compare_arduino_sketch_ver(test_version) == SKETCH_VER_LT:
            return True
        else:
            return False

    # -------------------------------------------------------------------------
    def arduino_sketch_ver_eq(self, test_version):
        """Method to test whether the Arduino sketch version is equal to the
           specified value
        """
        if self.compare_arduino_sketch_ver(test_version) == SKETCH_VER_EQ:
            return True
        else:
            return False

    # -------------------------------------------------------------------------
    def arduino_sketch_ver_gt(self, test_version):
        """Method to test whether the Arduino sketch version is greater than
           the specified value
        """
        if self.compare_arduino_sketch_ver(test_version) == SKETCH_VER_GT:
            return True
        else:
            return False

    # -------------------------------------------------------------------------
    def arduino_sketch_ver_le(self, test_version):
        """Method to test whether the Arduino sketch version is less than or
           equal to the specified value
        """
        if (self.arduino_sketch_ver_lt(test_version) or
                self.arduino_sketch_ver_eq(test_version)):
            return True
        else:
            return False

    # -------------------------------------------------------------------------
    def arduino_sketch_ver_ge(self, test_version):
        """Method to test whether the Arduino sketch version is greater than
           or equal to the specified value
        """
        if (self.arduino_sketch_ver_gt(test_version) or
                self.arduino_sketch_ver_eq(test_version)):
            return True
        else:
            return False

    # -------------------------------------------------------------------------
    def process_eeprom_value(self):
        """Method to process one EEPROM value returned by the Arduino"""
        eeprom_re = re.compile('EEPROM addr: (\d+)\s+value: (\d+\.\d+)')
        match = eeprom_re.search(self.msg_from_arduino)
        if match:
            eeprom_addr = int(match.group(1))
            eeprom_value = match.group(2)
        else:
            err_str = ("ERROR: Bad EEPROM value message: " +
                       self.msg_from_arduino)
            self.logger.print_and_log(err_str)
            return RC_FAILURE

        if eeprom_addr == EEPROM_VALID_ADDR:
            if eeprom_value != EEPROM_VALID_VALUE:
                err_str = ("ERROR: Bad EEPROM valid value: " +
                           self.msg_from_arduino)
                self.logger.print_and_log(err_str)
                return RC_FAILURE
        elif eeprom_addr == EEPROM_VALID_COUNT_ADDR:
            if int(float(eeprom_value)) > EEPROM_VALID_COUNT:
                warn_str = ("WARNING: EEPROM contains more values than " +
                            "supported by this version of the application: " +
                            self.msg_from_arduino)
                self.logger.print_and_log(warn_str)
        elif eeprom_addr == EEPROM_R1_OHMS_ADDR:
            self.vdiv_r1 = float(eeprom_value)
        elif eeprom_addr == EEPROM_R2_OHMS_ADDR:
            self.vdiv_r2 = float(eeprom_value)
        elif eeprom_addr == EEPROM_RF_OHMS_ADDR:
            self.amm_op_amp_rf = float(eeprom_value)
        elif eeprom_addr == EEPROM_RG_OHMS_ADDR:
            self.amm_op_amp_rg = float(eeprom_value)
        elif eeprom_addr == EEPROM_SHUNT_UOHMS_ADDR:
            self.amm_shunt_max_volts = (self.amm_shunt_max_amps *
                                        (float(eeprom_value) / 1000000.0))
        elif eeprom_addr == EEPROM_V_CAL_X1M_ADDR:
            self.v_cal = float(eeprom_value) / 1000000.0
        elif eeprom_addr == EEPROM_I_CAL_X1M_ADDR:
            self.i_cal = float(eeprom_value) / 1000000.0
        elif eeprom_addr == EEPROM_V_BATT_X1M_ADDR:
            self.v_batt = float(eeprom_value) / 1000000.0
        elif eeprom_addr == EEPROM_R_BATT_X1M_ADDR:
            self.r_batt = float(eeprom_value) / 1000000.0
        else:
            warn_str = ("WARNING: EEPROM value not " +
                        "supported by this version of the application: " +
                        self.msg_from_arduino)
            self.logger.print_and_log(warn_str)

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def correct_adc_values(self):
        """Method to remove errors from the ADC values. This consists of the
        following corrections:
           - Adjust voltages to compensate for offset and Voc shift
           - Combine points with same voltage (use average current)
           - Apply a noise reduction algorithm
        """
        self.logger.log("Correcting ADC values:")
        self.adc_pairs_corrected = []
        voc_pair_num = (len(self.adc_pairs) - 1)  # last one is Voc
        v_adj = self.v_adj
        self.logger.log("  v_adj = " + str(v_adj))
        for pair_num, adc_pair in enumerate(self.adc_pairs):
            # Adjust voltages to compensate for offset and Voc shift
            if pair_num == voc_pair_num:
                v_adj = 1.0
            ch0_adc_corrected = (adc_pair[0] - self._adc_ch0_offset) * v_adj
            ch1_adc_corrected = adc_pair[1] - self._adc_ch1_offset
            if pair_num == 0:
                self.adc_pairs_corrected.append((ch0_adc_corrected,
                                                 ch1_adc_corrected))
                prev_adc0_corrected = ch0_adc_corrected
                prev_adc1_corrected = ch1_adc_corrected
                continue

            # Combine points with same voltage
            if ch0_adc_corrected == prev_adc0_corrected:
                if pair_num == voc_pair_num:
                    # For Voc point, use corrected current (which should
                    # be zero)
                    ch1_adc_corrected = ch1_adc_corrected
                else:
                    # For all others, use average current
                    ch1_adc_corrected = (ch1_adc_corrected +
                                         prev_adc1_corrected) / 2.0
                del self.adc_pairs_corrected[-1]
            self.adc_pairs_corrected.append((ch0_adc_corrected,
                                             ch1_adc_corrected))

            prev_adc0_corrected = ch0_adc_corrected
            prev_adc1_corrected = ch1_adc_corrected

        # Remove point 0 (which was extrapolated by the Arduino code) if
        # the next point's CH0 value is more than 20% of the last CH0
        # value.
        second_ch0 = float(self.adc_pairs_corrected[1][0])
        last_ch0 = float(self.adc_pairs_corrected[-1][0])
        if (second_ch0 / last_ch0) > 0.20:
            del self.adc_pairs_corrected[0]

        # Noise reduction
        if self.reduce_noise:
            self.noise_reduction(starting_rot_thresh=10.0,
                                 iterations=25,
                                 thresh_divisor=2.0)

    # -------------------------------------------------------------------------
    def noise_reduction(self, starting_rot_thresh=5.0, iterations=1,
                        thresh_divisor=2.0):
        """Method to smooth out "bumps" in the curve. The trick is to
           disambiguate between deviations (bad) and inflections
           (normal). For each point on the curve, the rotation angle at
           that point is calculated. If this angle exceeds a threshold,
           it is either a deviation or an inflection. It is an
           inflection if the rotation angle relative to several points
           away is actually larger than the rotation angle relative to
           the neighbor points.  Inflections are left alone. Deviations
           are corrected by replacing them with a point interpolated
           (linearly) between its neighbors. This algorithm may be
           performed incrementally, starting with a large threshold and
           then dividing that threshold by some amount each time - in
           theory this should provide better results because the larger
           deviations will be smoothed out first, so it is more clear
           what is a deviation and what isn't.
        """
        num_points = len(self.adc_pairs_corrected)
        rot_thresh = starting_rot_thresh
        for ii in xrange(25):
            # Calculate the distance (in points) of the "far" points for
            # the inflection comparison.  It is 1/25 of the total number
            # of points, but always at least 2.
            dist = int(num_points / 25.0)
            if dist < 2:
                dist = 2
            for point in xrange(num_points - 1):
                # Rotation calculation
                pairs_list = self.adc_pairs_corrected
                rot_degrees = self.rotation_at_point(pairs_list, point)
                if abs(rot_degrees) > rot_thresh:
                    deviation = True
                    if point > (dist - 1) and (point + dist) < num_points:
                        long_rot_degrees = self.rotation_at_point(pairs_list,
                                                                  point,
                                                                  dist)
                        if ((long_rot_degrees > 0) and (rot_degrees > 0) and
                                (long_rot_degrees > rot_degrees)):
                            deviation = False
                        if ((long_rot_degrees <= 0) and (rot_degrees < 0) and
                                (long_rot_degrees < rot_degrees)):
                            deviation = False
                    if deviation:
                        curr_point = pairs_list[point]
                        prev_point = pairs_list[point-1]
                        next_point = pairs_list[point+1]
                        if point > 1:
                            ch0_adc_corrected = (prev_point[0] +
                                                 next_point[0]) / 2.0
                        else:
                            # Don't correct voltage of point 1.  Otherwise
                            # it migrates toward the Isc point each
                            # iteration, and that doesn't seem right since
                            # the Isc point is extrapolated.
                            ch0_adc_corrected = curr_point[0]
                        ch1_adc_corrected = (prev_point[1] +
                                             next_point[1]) / 2.0
                        self.adc_pairs_corrected[point] = (ch0_adc_corrected,
                                                           ch1_adc_corrected)
            rot_thresh /= thresh_divisor

    # -------------------------------------------------------------------------
    def rotation_at_point(self, pairs_list, point, distance=1):
        """Method to calculate the angular rotation at a point on the
           curve. The list of points and the point number of
           interest are passed in.  By default, the angle is
           calculated using the immediate neighbor points
           (distance=1), but setting this parameter to a larger
           value calculates the angle using points at that distance
           on either side from the specified point.
        """
        if point == 0:
            return 0.0
        if pairs_list:
            i_scale = pairs_list[-1][0] / pairs_list[0][1]  # Voc/Isc
        else:
            i_scale = INFINITE_VAL
        i1 = pairs_list[point - distance][1]
        v1 = pairs_list[point - distance][0]
        i2 = pairs_list[point][1]
        v2 = pairs_list[point][0]
        i3 = pairs_list[point + distance][1]
        v3 = pairs_list[point + distance][0]
        if v2 == v1:
            m12 = INFINITE_VAL
        else:
            m12 = i_scale * (i2 - i1) / (v2 - v1)
        if v3 == v2:
            m23 = INFINITE_VAL
        else:
            m23 = i_scale * (i3 - i2) / (v3 - v2)
        rot_degrees = (math.degrees(math.atan(m12)) -
                       math.degrees(math.atan(m23)))
        return rot_degrees

    # -------------------------------------------------------------------------
    def convert_adc_values(self):
        """Method to convert the ADC values to voltage, current, power,
           and resistance tuples and fill the data_points structure
        """

        self.data_points = []
        adc_pairs = self.adc_pairs
        if self.correct_adc:
            adc_pairs = self.adc_pairs_corrected
        for pair_num, adc_pair in enumerate(adc_pairs):
            volts = adc_pair[0] * self.v_mult
            amps = adc_pair[1] * self.i_mult
            watts = volts * amps
            if amps:
                ohms = volts / amps
            else:
                ohms = INFINITE_VAL
            self.data_points.append((amps, volts, ohms, watts))
            output_line = ("V=%.6f, I=%.6f, P=%.6f, R=%.6f" %
                           (volts, amps, watts, ohms))
            self.logger.log(output_line)

    # -------------------------------------------------------------------------
    def apply_battery_bias(self):
        """Method to subtract the battery bias from the data points
        """
        biased_data_points = []

        for data_point in self.data_points:
            volts = data_point[VOLTS_INDEX]
            amps = data_point[AMPS_INDEX]
            biased_volts = volts - (self.v_batt - (amps * self.r_batt))
            if biased_volts < 0:
                continue
            else:
                if amps:
                    ohms = biased_volts / amps
                else:
                    ohms = INFINITE_VAL
                watts = biased_volts * amps
                biased_point = (amps, biased_volts, ohms, watts)
                biased_data_points.append(biased_point)

        # Extrapolate new Isc point
        max_watt_point_number = (
            self.get_max_watt_point_number(biased_data_points))
        isc_point = self.extrapolate_isc(biased_data_points,
                                         max_watt_point_number)
        self.data_points = [isc_point] + biased_data_points

    # -------------------------------------------------------------------------
    def log_initial_debug_info(self):
        """Method to write pre-run debug info to the log file"""

        self.logger.log("app_data_dir = " + self.app_data_dir)
        self.logger.log("log_file_name = " + self.logger.log_file_name)
        self.logger.log("adc_inc = " + str(self.adc_inc))
        self.logger.log("vdiv_ratio = " + str(self.vdiv_ratio))
        self.logger.log("v_mult = " + str(self.v_mult))
        self.logger.log("amm_op_amp_gain = " + str(self.amm_op_amp_gain))
        self.logger.log("i_mult = " + str(self.i_mult))

    # -------------------------------------------------------------------------
    def create_hdd_output_dir(self, date_time_str):
        """Method to create the HDD output directory"""

        # Create the HDD output directory
        hdd_iv_swinger_dirs = self.create_iv_swinger_dirs([""],
                                                          include_csv=False,
                                                          include_pdf=False)
        hdd_iv_swinger_dir = hdd_iv_swinger_dirs[0]  # only one
        self.hdd_output_dir = os.path.join(hdd_iv_swinger_dir, date_time_str)
        os.makedirs(self.hdd_output_dir)

    # -------------------------------------------------------------------------
    def write_adc_pairs_to_csv_file(self, filename, adc_pairs):
        """Method to write each pair of readings from the ADC to a CSV
        file. This file is not used for the current run, but may be used
        later for debug or for regenerating the data points after
        algorithm improvements. It is the only history of the raw
        readings.
        """
        with open(filename, "w") as f:
            # Write headings
            f.write("CH0 (voltage), CH1 (current)\n")
            # Write ADC pairs
            for adc_pair in adc_pairs:
                f.write("%d,%d\n" % (adc_pair[0], adc_pair[1]))

        self.logger.log("Raw ADC values written to " + filename)

    # -------------------------------------------------------------------------
    def read_adc_pairs_from_csv_file(self, filename):
        """Method to read a CSV file containing ADC pairs and return the list
           of ADC pairs
        """
        adc_pairs = []
        try:
            with open(filename, "r") as f:
                for ii, line in enumerate(f.read().splitlines()):
                    if ii == 0:
                        expected_first_line = "CH0 (voltage), CH1 (current)"
                        if line != expected_first_line:
                            err_str = ("ERROR: first line of ADC CSV is not " +
                                       expected_first_line)
                            self.ivs2.logger.print_and_log(err_str)
                            return []
                    else:
                        adc_pair = map(float, line.split(","))
                        if len(adc_pair) != 2:
                            err_str = ("ERROR: CSV line %d is not in "
                                       "expected CH0, CH1 "
                                       "format" % (ii + 1))
                            self.ivs2.logger.print_and_log(err_str)
                            return []
                        adc_tuple = (adc_pair[0], adc_pair[1])
                        adc_pairs.append(adc_tuple)
        except (IOError):
            print "Cannot open " + filename
            return []

        return adc_pairs

    # -------------------------------------------------------------------------
    def get_adc_offsets(self):
        """Method to determine the "zero" value of the ADC for each
        channel
        """
        # Normally The last (Voc) CH1 value is the offset, or "zero"
        # value (assumed to apply to both channels since we don't ever
        # see the "zero" value on CH0). However, occasionally a lower
        # value shows up, in which case we want to use that.
        self._adc_ch0_offset = self.adc_pairs[-1][1]
        self._adc_ch1_offset = self.adc_pairs[-1][1]
        for adc_pair in self.adc_pairs:
            if adc_pair[0] < self._adc_ch0_offset:
                self._adc_ch0_offset = adc_pair[0]
            if adc_pair[1] < self._adc_ch1_offset:
                self._adc_ch1_offset = adc_pair[1]

    # -------------------------------------------------------------------------
    def adc_sanity_check(self):
        """Method to do basic sanity checks on the ADC values
        """
        # Check for Voc = 0V
        if self.voc_adc - self._adc_ch0_offset == 0:
            self.logger.log("Voc is zero volts")
            return RC_ZERO_VOC

        # Check for Isc = 0A
        if self.isc_adc - self._adc_ch1_offset == 0:
            self.logger.log("Isc is zero amps")
            return RC_ZERO_ISC

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def swing_iv_curve(self, loop_mode=False, first_loop=False):
        """Method to generate and plot an IV curve. This overrides the
           method in the IV_Swinger base class, but is completely
           different. The actual swinging of the IV curve is done by the
           Arduino. This method triggers the Arduino, receives the data
           points from it, converts the results to
           volts/amps/watts/ohms, writes the values to a CSV file, and
           plots the results to both PDF and GIF files.
           """

        # Generate the date/time string from the current time
        while True:
            date_time_str = IV_Swinger.DateTimeStr.get_date_time_str()
            # Sleep and retry if it's the same as last time. Current resolution
            # is 1 second, so this limits the rate to one curve per second.
            if date_time_str == self.prev_date_time_str:
                time.sleep(0.1)
            else:
                self.prev_date_time_str = date_time_str
                break

        # Create the HDD output directory
        self.create_hdd_output_dir(date_time_str)

        # Write info to the log file
        self.logger.log("================== Swing! ==========================")
        self.logger.log("Loop mode: " + str(loop_mode))
        self.logger.log("Output directory: " + self.hdd_output_dir)

        # Get the name of the CSV files
        self.get_csv_filenames(self.hdd_output_dir, date_time_str)

        # If Arduino has not already been reset and communication
        # established, do that now
        if not self.arduino_ready:

            # Reset Arduino
            rc = self.reset_arduino()
            if rc != RC_SUCCESS:
                return rc

            # Wait for Arduino ready message
            rc = self.wait_for_arduino_ready_and_ack()
            if rc != RC_SUCCESS:
                return rc

        # Send "go" message to Arduino
        rc = self.send_msg_to_arduino("Go")
        if rc != RC_SUCCESS:
            return rc

        # Receive ADC data from Arduino and store in adc_pairs property
        # (list of tuples)
        rc = self.receive_data_from_arduino()
        if rc != RC_SUCCESS:
            return rc

        # Write ADC pairs to CSV file
        self.write_adc_pairs_to_csv_file(self.hdd_adc_pairs_csv_filename,
                                         self.adc_pairs)

        # Write Unfiltered ADC pairs (if any) to CSV file
        if len(self.unfiltered_adc_pairs):
            unfiltered_adc_csv = self.hdd_unfiltered_adc_pairs_csv_filename
            self.write_adc_pairs_to_csv_file(unfiltered_adc_csv,
                                             self.unfiltered_adc_pairs)

        # Process ADC values
        rc = self.process_adc_values()
        if rc != RC_SUCCESS:
            return rc

        # Plot results
        self.plot_results()

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def get_csv_filenames(self, dir, date_time_str):
        """Method to derive the names of the CSV files (ADC pairs and data
        points) and set the corresponding instance variables.
        """
        # Create the leaf file names
        adc_pairs_csv_leaf_name = "adc_pairs_" + date_time_str + ".csv"
        unfiltered_adc_pairs_csv_leaf_name = ("unfiltered_adc_pairs_" +
                                              date_time_str + ".csv")
        csv_data_pt_leaf_name = self.file_prefix + date_time_str + ".csv"

        # Get the full-path names of the HDD output files
        unfiltered_adc_csv = os.path.join(dir,
                                          unfiltered_adc_pairs_csv_leaf_name)
        self.hdd_unfiltered_adc_pairs_csv_filename = unfiltered_adc_csv
        adc_csv = os.path.join(dir, adc_pairs_csv_leaf_name)
        self.hdd_adc_pairs_csv_filename = adc_csv
        csv = os.path.join(dir, csv_data_pt_leaf_name)
        self.hdd_csv_data_point_filename = csv

    # -------------------------------------------------------------------------
    def process_adc_values(self):
        """Method to process the ADC values from the Arduino, i.e. write
        them to a CSV file, determine the offset values, perform sanity
        checks, convert the values to volts, amps, watts, and ohms; and
        write those values to a CSV file
        """
        # Determine ADC offset values
        self.get_adc_offsets()

        # Sanity check ADC values
        rc = self.adc_sanity_check()
        if rc != RC_SUCCESS:
            return rc

        # Correct the ADC values to compensate for offset etc.
        if self.correct_adc:
            self.correct_adc_values()

        # Convert the ADC values to volts, amps, watts, and ohms
        self.convert_adc_values()

        # Apply battery bias, if enabled
        if self.battery_bias:
            self.apply_battery_bias()

        # Write CSV file
        self.write_csv_data_points_to_file(self.hdd_csv_data_point_filename,
                                           self.data_points)
        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def plot_results(self):
        """Method to plot results"""
        self.ivp = IV_Swinger2_plotter()
        self.ivp.title = self.plot_title
        self.ivp.logger = self.logger
        self.ivp.csv_files = [self.hdd_csv_data_point_filename]
        self.ivp.plot_dir = self.hdd_output_dir
        self.ivp.x_pixels = self.x_pixels
        self.ivp.generate_pdf = self.generate_pdf
        self.ivp.fancy_labels = self.fancy_labels
        self.ivp.linear = self.linear
        self.ivp.plot_power = self.plot_power
        self.ivp.font_scale = self.font_scale
        self.ivp.line_scale = self.line_scale
        self.ivp.point_scale = self.point_scale
        if self.plot_lock_axis_ranges:
            self.ivp.max_x = self.plot_max_x
            self.ivp.max_y = self.plot_max_y
        self.ivp.run()
        self.current_img = self.ivp.current_img
        self.plot_max_x = self.ivp.max_x
        self.plot_max_y = self.ivp.max_y

    # -------------------------------------------------------------------------
    def configure_logging(self):
        """Method to set up logging"""

        # Generate the date/time string from the current time
        date_time_str = IV_Swinger.DateTimeStr.get_date_time_str()

        # Create logs directory
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)

        # Create the logger
        IV_Swinger.PrintAndLog.log_file_name = os.path.join(self.logs_dir,
                                                            ("log_" +
                                                             date_time_str +
                                                             ".txt"))
        self.logger = PrintAndLog()


############
#   Main   #
############
def main():
    """Main function"""
    # This module is not normally run as a standalone program - but if
    # it is, we might as well do something interesting. The code below
    # swings one IV curve, stores the result in the standard
    # (OS-dependent) place, and opens the PDF. The configuration is read
    # from the standard place. A copy of the configuration is saved in
    # the run directory, but the original config is restored.

    # Create an IVS2 object
    ivs2 = IV_Swinger2()
    ivs2.logger.print_and_log("Running from IV_Swinger2.main()")

    # Create a configuration object and get the current configuration
    # from the standard file (if it exists) and also keep a snapshot of
    # this starting config.
    config = Configuration(ivs2=ivs2)
    config.get()
    config.get_snapshot()

    # Log the initial debug stuff
    ivs2.log_initial_debug_info()

    # Swing the curve
    ivs2.swing_iv_curve()

    # Update the config
    config.populate()
    config.add_axes_and_title()

    # Save the config and copy it to the output directory
    config.save(ivs2.hdd_output_dir)

    # Restore the master config file from the snapshot
    config.save_snapshot()  # restore original

    # Print message and close the log file
    ivs2.logger.print_and_log("  Results in: " + ivs2.hdd_output_dir)
    ivs2.logger.terminate_log()

    # Open the PDF
    if os.path.exists(ivs2.pdf_filename):
        sys_view_file(ivs2.pdf_filename)


# Boilerplate main() call
if __name__ == '__main__':
    main()
