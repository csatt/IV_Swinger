#!/usr/bin/env python
"""IV Swinger control module"""
# pylint: disable=too-many-lines
#
###############################################################################
#
# IV_Swinger.py: IV Swinger control module
#
# Copyright (C) 2016-2021  Chris Satterlee
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
# The IV Swinger is an open source hardware and software project
#
# Permission to use the hardware design is granted under the terms of
# the TAPR Open Hardware License Version 1.0 (May 25, 2007) -
# http://www.tapr.org/OHL
#
# Permission to use the software is granted under the terms of the GNU
# GPL v3 as noted above.
#
# Current versions of the licensing files, documentation, hardware
# design files, and software can be found at:
#
#    https://github.com/csatt/IV_Swinger
#
###############################################################################
#
# NOTE: This module was originally written for IV Swinger 1. The
# remainder of this comment block pertains to IV Swinger 1. Much of the
# code in this module is specific to IV Swinger 1 and is not used for IV
# Swinger 2. On the other hand, a lot of the code was applicable to IV
# Swinger 2, so it was re-used as much as possible. The comment '# IVS1'
# identifies code that is not used at all for IV Swinger 2, and that
# comment is used when running code coverage to exclude the
# IVS1-specific code from the coverage metrics.
#
###############################################################################
#
# This file contains the Python code that controls the IV Swinger
# hardware, captures measurements, and displays the results graphically.
#
# The hardware consists of a chain of loads that are selected or
# deselected using relays.  When a load is deselected, the current
# passes through a wire bypassing that load.  Ideally when all loads are
# deselected, the resistance of the chain would be zero (short circuit).
# In reality the bypass wires, relay terminal connections, and relay
# contacts have small resistances that add up to a non-negligible total
# (close to half an ohm).
#
# There are 16 relays (two 8-relay Sainsmart-type modules) which are
# driven by a MCP23017 I/O extender IC that is controlled from the
# Raspberry Pi i2c bus.  The MCP23017 outputs are connected to the
# relays as follows.  This list in is order from RIGHT to LEFT as seen
# from the front of the box.
#
# MCP23017  Relay pin         Load (see defines below)
# --------  ---------         ----
#  B0       Module 1, IN1     HALF
#  B1       Module 1, IN2     OPEN
#  B2       Module 1, IN3     ONE
#  B3       Module 1, IN4     TWO
#  B4       Module 1, IN5     THREE
#  B5       Module 1, IN6     FOUR
#  B6       Module 1, IN7     FIVE
#  B7       Module 1, IN8     SIX
#  A7       Module 0, IN1     SEVEN
#  A6       Module 0, IN2     EIGHT
#  A5       Module 0, IN3     NINE
#  A4       Module 0, IN4     TEN
#  A3       Module 0, IN5     ELEVEN
#  A2       Module 0, IN6     TWELVE
#  A1       Module 0, IN7     THIRTEEN
#  A0       Module 0, IN8     FOURTEEN
#
# Note that one of the "loads" (OPEN) is actually not connected.  This
# was a design change required to support maximizing the lifetime of the
# relay contacts. The load bank does include a coil associated with this
# relay, but one of its leads is simply left unconnected so that when
# the relay is activated the circuit is open. The OPEN load is in the
# second position purely for logistical reasons; it was the easiest one
# to disconnect when the decision was made to implement the change.
#
# There is a double-pole single-throw (DPST) switch in the load circuit
# that has two purposes: 1) on one side it opens and closes the load
# circuit, and 2) on the other side it is connected to a GPIO pin so the
# code can sense whether the load circuit is open or closed and can poll
# for changes.  While the load circuit is open, the code continuously
# measures the voltage and records the last value before it detects that
# the switch was flipped - this is the Voc value.  Then it starts into a
# loop of incrementally adding to the load value and at each increment
# measuring and recording the current (I) and the voltage (V).
#
# The ADS1115 analog-to-digital converter (ADC) is used for both the
# voltage and current measurements.  The ADS1115 is also controlled and
# read via the Raspberry Pi i2c bus.  Since the voltage generated by a
# PV panel can be much higher than the 5V maximum ADC input voltage, the
# actual voltage that is fed to the ADC input is divided down from the
# PV inputs using series resistors (classic voltage divider).  The
# software then scales that back up to calculate the original voltage.
# The current measurement is actually a voltage measurement too - across
# a low resistance (7.5 milliohm) "shunt resistor".  The current is
# calculated from Ohm's Law using the measured voltage and the known
# precision resistance of the shunt resistor.  This voltage is very
# small however (75mV for 10A) so it is amplified using a simple (and
# also classic) non-inverting op amp circuit before being fed to the ADC
# input.  The software does the math of converting the voltage value
# read by the ADC to a measured value for the current.
#
# Each of the measured I-V pairs is recorded for each selected load
# value.  Two important points are where V=0 and where I=0.  The current
# when V=0 is the short-circuit current, Isc.  The voltage when I=0 is
# the open-circuit voltage Voc.  Voc is captured when the DPST switch is
# in the open position.  Since there is still a small resistance when
# the circuit is closed - even with zero loads selected, the Isc value
# is estimated by a linear extrapolation from that "zero" load point and
# the next point (minimum load selected - "HALF").
#
# When the program is started the DPST switch is expected to be in the
# OFF (open) position.  If it is not, it prompts the user to turn it
# off, sounding a warning (piezo buzzer) until this has happened. When
# the switch is off, the program measures Voc. When Voc is stable it
# then asks the user to turn ON (close) the DPST switch, polling until
# this has happened.  During this polling the Voc value is continually
# updated since it could be changing.  When the switch is closed, the
# program begins the loop incrementing the load value and measuring the
# current and voltage at each point. The original code toggled the HALF
# relay at every increment to get ~1/2 ohm steps. But this results in a
# drastically shorter lifetime for this one relay. Now there are both
# "fine" and "coarse" modes.  The "coarse" mode starts with the HALF
# load, but only takes full steps after that. Even in "fine" mode, the
# HALF relay isn't switched at every step. Where the code determines
# that the curve is relatively straight (typically at the beginning and
# the end), it skips the half load values since they don't add value.
# This turns out to be a very good optimization - most of the time there
# are only two added points relative to coarse mode.  For this reason,
# the default is fine mode.  Coarse mode should probably be removed, but
# it has been left in.  The user can toggle the mode by pressing the
# pushbutton briefly (if the fine_mode_toggle property is set to True).
#
# The recorded values are written to a CSV file on both the Raspberry
# Pi's SD card file system and also on one or more USB thumb drives.
# The USB thumb drive(s) can then be removed and inserted in an external
# computer to import the CSV to Excel and/or to perform other analysis.
# Note that if more than one USB drive is found, the files are written
# to ALL of them.  This is to save time when the IV Swinger is used in a
# educational lab setting where there may be multiple lab partners.
# There are four USB ports, so up to four students can use their own USB
# thumb drives and no one has to copy the files from anyone else. The
# files are written to the /IV_Swinger directory on the SD card and all
# USB drives.  The subdirectory under /IV_Swinger is named for the date
# and time that the measurement was taken (yymmdd_hh_mm_ss)
# e.g. directory /IV_Swinger/141213_09_33_31 contains files for a
# measurement taken on December 13th, 2014 at 9:33:13 am.
#
# The program also uses pyplot (matplotlib) to generate a graph of the
# IV curve that it writes to a PDF (or GIF) file, which is also copied
# to the USB drive(s) in the same directory.
#
# If the DPST switch remains OFF (open) for more than 10 minutes, the
# program initiates a shutdown of the Raspberry Pi.  There is also a
# shutdown pushbutton switch that is monitored at all times; when it is
# pressed and held for more than 3 seconds the program does an immediate
# shutdown of the Raspberry Pi. Also if an unexpected exception is
# taken, the Raspberry Pi is shut down after a short delay.
#
import queue
import datetime as dt
import glob
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import warnings
import numpy

# Conditionally import RPi-specific modules. This is so this module can
# be imported on other platforms for post-processing the output files.
try:
    import Adafruit_ADS1x15
    import Adafruit_CharLCD
    import Adafruit_MCP230xx
    import RPi.GPIO as GPIO  # pylint: disable=import-error
except ImportError:
    pass
if not platform.machine().startswith("armv6"):
    # Suppress matplotlib import on RPi 1 (too slow))
    import matplotlib.pyplot as plt
    import matplotlib.font_manager
    from matplotlib import __version__ as matplotlib_version


#################
#   Constants   #
#################

# GPIO defines
DPST_ON = True
DPST_OFF = False
BUTTON_ON = True
BUTTON_OFF = False

# I/O extender (MCP23017 on Slice of PI/O) defines
MCP23017_PIN_COUNT = 16   # MCP23017 is 16 GPIO extension

# Relay defines
RELAY_OFF = 1  # Relays are active low
RELAY_ON = 0
ALL_RELAYS_OFF = 0xFFFF

# Load pattern defines
#
# There are 16 loads.  The basic "unit" loads are the immersion coils
# (~0.9 ohm each).  The first load in the chain is two of these in
# parallel, i.e. half a unit load.  The next one is the "open" load,
# which is not connected to anything (this was a late design
# change). The next eleven are unit loads.  The last three loads in the
# chain consist of 6 ohm resistors.  Number 12 is two of these in
# parallel (3 ohms).  Number 13 is one 6 ohm resistor.  Number 14 is two
# in series (12 ohms).
#
NONE = 0x0000  # No loads selected. Resistance is only relays/wires
HALF_ONLY = 0x8000
OPEN_ONLY = 0x4000
ONE_ONLY = 0x2000
TWO_ONLY = 0x1000
THREE_ONLY = 0x0800
FOUR_ONLY = 0x0400
FIVE_ONLY = 0x0200
SIX_ONLY = 0x0100
SEVEN_ONLY = 0x0080
EIGHT_ONLY = 0x0040
NINE_ONLY = 0x0020
TEN_ONLY = 0x0010
ELEVEN_ONLY = 0x0008
TWELVE_ONLY = 0x0004
THIRTEEN_ONLY = 0x0002
FOURTEEN_ONLY = 0x0001

HALF = NONE + HALF_ONLY               # 1/2 unit load selected
ONE = NONE + ONE_ONLY                 # 1 unit load selected
TWO = ONE + TWO_ONLY                  # 2 unit loads selected
THREE = TWO + THREE_ONLY              # 3 unit loads selected
FOUR = THREE + FOUR_ONLY              # 4 unit loads selected
FIVE = FOUR + FIVE_ONLY               # 5 unit loads selected
SIX = FIVE + SIX_ONLY                 # 6 unit loads selected
SEVEN = SIX + SEVEN_ONLY              # 7 unit loads selected
EIGHT = SEVEN + EIGHT_ONLY            # 8 unit loads selected
NINE = EIGHT + NINE_ONLY              # 9 unit loads selected
TEN = NINE + TEN_ONLY                 # 10 unit loads selected
ELEVEN = TEN + ELEVEN_ONLY            # 11 unit loads selected
TWELVE = ELEVEN + TWELVE_ONLY         # 11 unit + 3 ohm loads
THIRTEEN = TWELVE + THIRTEEN_ONLY     # 11 unit + 3 + 6 ohm loads
FOURTEEN = THIRTEEN + FOURTEEN_ONLY   # 11 unit + 3 + 6+ 12 ohm loads

ONE_AND_A_HALF = ONE + HALF            # 1.5 unit load selected
TWO_AND_A_HALF = TWO + HALF            # 2.5 unit loads selected
THREE_AND_A_HALF = THREE + HALF        # 3.5 unit loads selected
FOUR_AND_A_HALF = FOUR + HALF          # 4.5 unit loads selected
FIVE_AND_A_HALF = FIVE + HALF          # 5.5 unit loads selected
SIX_AND_A_HALF = SIX + HALF            # 6.5 unit loads selected
SEVEN_AND_A_HALF = SEVEN + HALF        # 7.5 unit loads selected
EIGHT_AND_A_HALF = EIGHT + HALF        # 8.5 unit loads selected
NINE_AND_A_HALF = NINE + HALF          # 9.5 unit loads selected
TEN_AND_A_HALF = TEN + HALF            # 10.5 unit loads selected
ELEVEN_AND_A_HALF = ELEVEN + HALF      # 11.5 unit loads selected
TWELVE_AND_A_HALF = TWELVE + HALF      # 11.5 unit + 3 ohm load
THIRTEEN_AND_A_HALF = THIRTEEN + HALF  # 11.5 unit + 3 + 6 ohm loads
FOURTEEN_AND_A_HALF = FOURTEEN + HALF  # 11.5 unit + 3 + 6 + 12 ohm loads

# In some cases where the ratio of Voc to Isc is high (e.g. low
# insolation), it's better to start off with a "base" load using one or
# more of the power resistors.  This pushes the fine grained sampling to
# the right, where the knee of the curve is.
BASE_0_OHM = [NONE]
BASE_3_OHM = [TWELVE_ONLY]
BASE_6_OHM = [THIRTEEN_ONLY]
BASE_9_OHM = [THIRTEEN_ONLY, TWELVE_ONLY]
BASE_12_OHM = [FOURTEEN_ONLY]
BASE_15_OHM = [FOURTEEN_ONLY, TWELVE_ONLY]
BASE_18_OHM = [FOURTEEN_ONLY, THIRTEEN_ONLY]
BASE_21_OHM = [FOURTEEN_ONLY, THIRTEEN_ONLY, TWELVE_ONLY]

# The 6 ohm resistors are rated at 50W.  We assume that they can handle
# at least 100W for a couple seconds.  The 3 ohm load is two in
# parallel, so it can handle 200W.  The 12 ohm load is two in series, so
# it can also handle 200W. Since power is I^2*R, here are the current
# limits for each of these loads:
#
#  TWELVE (3 ohm):    sqrt(200W/3ohm)  = 8 amps
#  THIRTEEN (6 ohm):  sqrt(100W/6ohm)  = 4 amps
#  FOURTEEN (12 ohm): sqrt(200W/12ohm) = 4 amps
#
TWELVE_MAX_AMPS = 8
THIRTEEN_MAX_AMPS = 4
FOURTEEN_MAX_AMPS = 4

COARSE_LOAD_LIST = [NONE,
                    HALF,
                    ONE_AND_A_HALF,
                    TWO_AND_A_HALF,
                    THREE_AND_A_HALF,
                    FOUR_AND_A_HALF,
                    FIVE_AND_A_HALF,
                    SIX_AND_A_HALF,
                    SEVEN_AND_A_HALF,
                    EIGHT_AND_A_HALF,
                    NINE_AND_A_HALF,
                    TEN_AND_A_HALF,
                    ELEVEN_AND_A_HALF,
                    TWELVE_AND_A_HALF,
                    THIRTEEN_AND_A_HALF,
                    FOURTEEN_AND_A_HALF]

FINE_LOAD_LIST = [NONE,
                  HALF,
                  ONE_AND_A_HALF,
                  ONE,                # skip if prev is in line
                  TWO_AND_A_HALF,
                  TWO,                # skip if prev is in line
                  THREE_AND_A_HALF,
                  THREE,              # skip if prev is in line
                  FOUR_AND_A_HALF,
                  FOUR,               # skip if prev is in line
                  FIVE_AND_A_HALF,
                  FIVE,               # skip if prev is in line
                  SIX_AND_A_HALF,
                  SIX,                # skip if prev is in line
                  SEVEN_AND_A_HALF,
                  SEVEN,              # skip if prev is in line
                  EIGHT_AND_A_HALF,
                  EIGHT,              # skip if prev is in line
                  NINE_AND_A_HALF,
                  NINE,               # skip if prev is in line
                  TEN_AND_A_HALF,
                  TEN,                # skip if prev is in line
                  ELEVEN_AND_A_HALF,
                  ELEVEN,             # skip if prev is in line
                  TWELVE_AND_A_HALF,
                  THIRTEEN_AND_A_HALF,
                  FOURTEEN_AND_A_HALF]

DIAG_LOAD_LIST = [NONE,
                  HALF_ONLY,
                  OPEN_ONLY,
                  ONE_ONLY,
                  TWO_ONLY,
                  THREE_ONLY,
                  FOUR_ONLY,
                  FIVE_ONLY,
                  SIX_ONLY,
                  SEVEN_ONLY,
                  EIGHT_ONLY,
                  NINE_ONLY,
                  TEN_ONLY,
                  ELEVEN_ONLY,
                  TWELVE_ONLY,
                  THIRTEEN_ONLY,
                  FOURTEEN_ONLY]

# Misc
INFINITE_VAL = 99999999
# Colors generated using: http://tools.medialab.sciences-po.fr/iwanthue/
# First color locked at pure blue.
PLOT_COLORS = ["#0000ff",
               "#54a763",
               "#c95ea0",
               "#c9803d",
               "#8d62c9",
               "#979d3b",
               "#6b91d0",
               "#cd5253"]
DEFAULT_MARKER_POINTSIZE = 6.0
DEFAULT_LINEWIDTH = 2.5
POWER_LINEWIDTH_MULT = 1.25
DEFAULT_FONT = "Arial Unicode MS"

# ADC
ADS1115 = 0x01  # 16-bit ADC

# List of PGA gains (max +- mV)
PGA_LIST = [6144, 4096, 2048, 1024, 512, 256]

# Data point list
AMPS_INDEX = 0
VOLTS_INDEX = 1
OHMS_INDEX = 2
WATTS_INDEX = 3


########################
#   Global functions   #
########################
def turn_off_all_relays(io_extender):  # IVS1
    """Global function to turn off all the relays"""
    io_extender.write16(ALL_RELAYS_OFF)


def swizzle_byte(byte):  # IVS1
    """Global function to reverse the order of the bits in a byte"""
    swizzled_byte = 0

    for bit in range(8):
        swizzled_byte |= ((byte & (1 << bit)) >> bit) << (7 - bit)

    return swizzled_byte


def swizzle_msb(value):  # IVS1
    """Global function to reverse the order of the bits in the upper byte of
       a 16-bit value
    """
    msb = (value & 0xFF00) >> 8
    lsb = value & 0xFF

    swizzled_msb = swizzle_byte(msb)

    return (swizzled_msb << 8) | lsb


def set_relays_to_pattern(load_pattern, io_extender):  # IVS1
    """Global function to set the relays to the supplied load pattern,
       performing the appropriate inversion (for active-low inputs) and
       swizzling (for cabling quirk).
    """
    # Due to the fact that the "B" outputs are in the reverse order
    # from the "A" outputs on the Slice of PI/O board, the upper
    # byte is bit-swizzled.
    io_extender.write16(swizzle_msb(~load_pattern))


def prime_relays(io_extender):  # IVS1
    """Global function to turn on each relay briefly (workaround for "weak"
       relay issue.
    """
    prime_pattern = 0x8000
    while prime_pattern:
        set_relays_to_pattern(prime_pattern, io_extender)
        time.sleep(0.02)
        prime_pattern >>= 1
    turn_off_all_relays(io_extender)


def write_csv_data_to_file(open_filehandle, volts,
                           amps, watts, ohms):
    """Global function to write the current voltage, current, watts, and
       ohms values to an output file which the caller has opened and has
       passed the filehandle.
    """
    output_line = ("{:.6f},{:.6f},{:.6f},{:.6f}\n"
                   .format(volts, amps, watts, ohms))
    open_filehandle.write(output_line)


def write_csv_data_points_to_file(filename, data_points):
    """Global function to write each of the CSV data points to the output
       file.
    """
    with open(filename, "w", encoding="utf-8") as f:
        # Write headings
        f.write("Volts, Amps, Watts, Ohms\n")
        # Write data points
        for data_point in data_points:
            write_csv_data_to_file(f,
                                   data_point[VOLTS_INDEX],
                                   data_point[AMPS_INDEX],
                                   data_point[WATTS_INDEX],
                                   data_point[OHMS_INDEX])


def write_plt_data_to_file(open_filehandle, volts, amps,
                           watts, new_data_set=False):
    """Global function to write/append the current voltage and current
       readings to an output file which the caller has opened for
       appending and has passed the filehandle.  If new_data_set=True,
       then the other values are ignored and two blank lines are
       appended to the file.
    """
    output_line = "{:.6f} {:.6f} {:.6f}\n".format(volts, amps, watts)
    if new_data_set:
        # two blank lines signify a new data set to plotter
        open_filehandle.write("\n")
        open_filehandle.write("\n")
    else:
        open_filehandle.write(output_line)


def write_plt_data_points_to_file(filename, data_points,
                                  new_data_set=False):
    """Global function to write/append each of the plotter data points to
       the output file.
    """
    with open(filename, "a", encoding="utf-8") as f:
        # Add new data set delimiter
        if new_data_set:
            write_plt_data_to_file(f, 0, 0, 0, new_data_set=True)

        prev_vals = ""
        for data_point in data_points:
            curr_vals = ("{:.6f} {:.6f} {:.6f}\n"
                         .format(data_point[VOLTS_INDEX],
                                 data_point[AMPS_INDEX],
                                 data_point[WATTS_INDEX]))
            if curr_vals != prev_vals:
                write_plt_data_to_file(f,
                                       data_point[VOLTS_INDEX],
                                       data_point[AMPS_INDEX],
                                       data_point[WATTS_INDEX])
            prev_vals = curr_vals


def pyplot_annotate_point(label_str, x, y, xtext, ytext, fontsize,
                          bbox, arrowprops, textcoords="offset points"):
    """Global function to add a label (Isc, Voc, MPP) to the plot
    """
    # pylint: disable=too-many-arguments
    plt.annotate(label_str,
                 xy=(x, y),
                 xytext=(xtext, ytext),
                 textcoords=textcoords,
                 fontsize=fontsize,
                 horizontalalignment="left",
                 verticalalignment="bottom",
                 bbox=bbox,
                 arrowprops=arrowprops)


def read_measured_and_interp_points(f):
    """Global function to read the measured points and interpolated points
       from the data point file
    """
    first_data_set = True
    measured_volts = []
    measured_amps = []
    measured_watts = []
    interp_volts = []
    interp_amps = []
    interp_watts = []
    for line in f.read().splitlines():
        if line:
            volts, amps, watts = line.split()
            if first_data_set:
                measured_volts.append(float(volts))
                measured_amps.append(float(amps))
                measured_watts.append(float(watts))
            else:
                interp_volts.append(float(volts))
                interp_amps.append(float(amps))
                interp_watts.append(float(watts))
        else:
            # Blank lines delimit data sets
            first_data_set = False

    return (measured_volts, measured_amps, measured_watts,
            interp_volts, interp_amps, interp_watts)


#################
#   Classes     #
#################

# The DateTimeStr class
class DateTimeStr():
    """Provides a static method to return the current date and time in a
       string in the canonical yymmdd_hh_mm_ss format used by the IV
       Swinger code for directory names, file names, etc. Also provides
       static methods to extract a substring in this format from an
       input string, and to translate a string in this format to a more
       readable format.
    """

    @staticmethod
    def get_date_time_str():
        """Method to return a date/time string based on the current time
        """
        return dt.datetime.now().strftime("%y%m%d_%H_%M_%S")
        # return dt.datetime.now().strftime("%y%m%d_%H_%M_%S_%f")[:-3]

    @staticmethod
    def extract_date_time_str(input_str):
        """Method to parse the date/time string from a leaf file name or
           other string
        """
        dt_file_re = re.compile(r"(\d{6}_\d{2}_\d{2}_\d{2})")
        match = dt_file_re.search(input_str)
        if match:
            return match.group(1)
        return "No match"

    @staticmethod
    def is_date_time_str(input_str):
        """Method to test if a given string is a date/time string
        """
        dt_file_re = re.compile(r"^(\d{6}_\d{2}_\d{2}_\d{2})$")
        match = dt_file_re.search(input_str)
        if match:
            return True
        return False

    @staticmethod
    def xlate_date_time_str(date_time_str):
        """Method to translate a date_time_str from yymmdd_hh_mm_ss
           format to a more readable format
        """
        yymmdd, hh, mm, ss = date_time_str.split("_")
        date_str = "{}/{}/{}".format(yymmdd[2:4], yymmdd[4:6], yymmdd[0:2])
        time_str = "{}:{}:{}".format(hh, mm, ss)
        return (date_str, time_str)


# The PrintAndLog class
class PrintAndLog():
    """Provides printing and logging methods"""

    # Class variables (must be set externally before instantiation)
    log_file_name = None

    def __init__(self):
        if self.log_file_name is None:
            print("log_file_name class variable is not initialized!!")
            sys.exit(-1)

    def log(self, print_str):
        """Print to the log file only"""

        # Print to log file with timestamp
        date_time_str = DateTimeStr.get_date_time_str()
        with open(self.log_file_name, "a", encoding="utf-8") as f:
            f.write("\n{}: {}".format(date_time_str, print_str))

    def print_and_log(self, print_str):
        """Print to the screen (if there is one) and also to a log file
        """

        # Print to screen
        print(print_str)

        # Print to log file with timestamp
        self.log(print_str)


# The BeepGenerator class
class BeepGenerator():  # IVS1
    """Generates beeps from the piezo buzzer"""
    # pylint: disable=too-few-public-methods

    # Class variables (must be set externally before instantiation)
    buzzer_gpio = None

    def __init__(self):
        if self.buzzer_gpio is None:
            print("buzzer_gpio class variable is not initialized!!")
            sys.exit(-1)

    def generate_beep(self, on_time=0.2, off_time=0.1, stop_event=None):
        """Method to activate the piezo buzzer to generate a loud
           beep. When called in a loop, the beep pulses in a warning
           pattern. The on_time arg is the amount of time in seconds that
           the buzzer is on (0.1 second resolution) and the off_time arg is
           the amount of time in seconds to wait after turning it off.  If
           the stop_event arg is not None, it must be a threading.Event()
           object in which case it is checked every 0.1 second during the
           on time and off time and if set, the method returns immediately.
        """
        # Calculate number of 0.1 second loops for both on and off
        on_loops = 1
        if on_time > 0.1:
            on_loops = int(on_time / 0.1)

        off_loops = 1
        if off_time > 0.1:
            off_loops = int(off_time / 0.1)

        # Turn on buzzer
        GPIO.output(self.buzzer_gpio, True)

        # Wait for on_time
        for _ in range(on_loops):
            # bail out now if stop event is set
            if stop_event is not None and stop_event.is_set():
                continue
            time.sleep(0.1)

        # Turn off buzzer
        GPIO.output(self.buzzer_gpio, False)

        # Wait for off_time
        for _ in range(off_loops):
            # bail out now if stop event is set
            if stop_event is not None and stop_event.is_set():
                continue
            time.sleep(0.1)


# The StoppableThread class is from pibrella.py
# (https://github.com/pimoroni/pibrella).
#
class StoppableThread(threading.Thread):  # IVS1
    """Adds Event for stopping the execution loop and exiting cleanly.
    """
    def __init__(self):
        threading.Thread.__init__(self)
        self.stop_event = threading.Event()
        self.daemon = True

    def start(self):
        """Start the thread"""
        if not self.isAlive():
            self.stop_event.clear()
            threading.Thread.start(self)

    def stop(self):
        """Stop the thread"""
        if self.isAlive():
            # set event to signal thread to terminate
            self.stop_event.set()
            # block calling thread until thread really has terminated
            self.join()


#  Class to continuously scroll a message until signalled to stop
#
#  Subclass of StoppableThread that calls the scrolling_message method
#  until signalled to stop. The text parameter accepts either a single
#  string or a list of strings.  In the latter case, each string in the
#  list is displayed in sequence with scrolling.
#
#  The exc_queue parameter is a Queue object. If the thread takes an
#  exception, the exception info is placed into the queue so the main
#  thread knows that something went wrong.
#
class ScrollingMessage(StoppableThread):  # IVS1
    """Class to continuously scroll a message until signalled to stop"""

    # Class variables (must be set externally before instantiation)
    lcd_lines = None
    lcd_disp_chars_per_line = None
    lcd_mem_chars_per_line = None
    lcd_chars_per_scroll = None
    lcd_scroll_delay = None

    def __init__(self, text, lcd, beep, lock, exc_queue):
        # pylint: disable=too-many-arguments
        StoppableThread.__init__(self)
        self.text = text
        self.lcd = lcd
        self.beep = beep
        self.lock = lock
        self.exc_queue = exc_queue
        self.logger = PrintAndLog()
        self.beeper = BeepGenerator()

        err_var = None
        if ScrollingMessage.lcd_lines is None:
            err_var = "lcd_lines"
        elif ScrollingMessage.lcd_disp_chars_per_line is None:
            err_var = "lcd_disp_chars_per_line"
        elif ScrollingMessage.lcd_mem_chars_per_line is None:
            err_var = "lcd_mem_chars_per_line"
        elif ScrollingMessage.lcd_chars_per_scroll is None:
            err_var = "lcd_chars_per_scroll"
        elif ScrollingMessage.lcd_scroll_delay is None:
            err_var = "lcd_scroll_delay"
        if err_var is not None:
            err_msg = ("ERROR: {} class variable is not initialized!! "
                       .format(err_var))
            self.logger.print_and_log(err_msg)
            self.exc_queue.put(err_msg)
            sys.exit(-1)

    def scrolling_message(self, text, repeat_count=0):
        """Method to display a longer message on the 16x2 LCD display.
           The message must be 80 or fewer characters, and if it contains a
           \n, there must be 40 or fewer characters before and after the
           \n.  The 16x2 LCD display has memory for 40 characters per line,
           but only shows 16.  This method scrolls the message left once
           (unless repeat_count is non-zero) so that the whole message can
           be read. If the caller doesn't include a \n, the first line will
           contain the first 40 characters and the second will contain the
           remainder, with the split not necesssarily coming between words.
           If the beep arg is set, sound the beep once per repetition.  If
           the stop_event arg is not None, it must be a threading.Event()
           object in which case it is checked during the scrolling and if
           set, the display is returned to the home position and the method
           returns immediately.  If the lock arg is not None, it must be a
           threading.Lock() object in which case it is acquired and
           released around each LCD object method call.  The first of these
           is blocking, but the others are non-blocking.  For those that
           are non-blocking, the method returns if the lock is not
           acquired.
        """
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements

        # Init variables
        char_count = [0, 0]  # List containing character counts for each line
        line = 0
        newline_count = 0

        # Count characters per line and check that there is no more than one
        # newline
        for char in text:
            if char == "\n":
                line = 1
                newline_count += 1
                if newline_count > 1:
                    err_msg = ("ERROR (scrolling_message): "
                               "More than two lines in text:\n{}"
                               .format(text))
                    self.logger.print_and_log(err_msg)
                    self.exc_queue.put(err_msg)
                    sys.exit(-1)
            else:
                char_count[line] += 1

        # Check character limits (40 per line or 80 total)
        if char_count[1] > 0:
            if char_count[0] > ScrollingMessage.lcd_mem_chars_per_line:
                err_msg = ("ERROR (scrolling_message): >40 characters "
                           "before newline in text:\n{}".format(text))
                self.logger.print_and_log(err_msg)
                self.exc_queue.put(err_msg)
                sys.exit(-1)
            elif char_count[1] > ScrollingMessage.lcd_mem_chars_per_line:
                err_msg = ("ERROR (scrolling_message): "
                           ">40 characters after newline in text:\n{}"
                           .format(text))
                self.logger.print_and_log(err_msg)
                self.exc_queue.put(err_msg)
                sys.exit(-1)
        elif char_count[0] > (ScrollingMessage.lcd_lines *
                              ScrollingMessage.lcd_mem_chars_per_line):
            err_msg = ("ERROR (scrolling_message): "
                       ">80 characters in text:\n{}".format(text))
            self.logger.print_and_log(err_msg)
            self.exc_queue.put(err_msg)
            sys.exit(-1)

        # Determine maximum number of characters in longer line and number
        # of hidden characters in that line
        if char_count[0] > ScrollingMessage.lcd_mem_chars_per_line:
            max_chars = ScrollingMessage.lcd_mem_chars_per_line
        elif char_count[0] > char_count[1]:
            max_chars = char_count[0]
        else:
            max_chars = char_count[1]
        hidden_chars = max_chars - ScrollingMessage.lcd_disp_chars_per_line

        # Calculate the number of scrolls needed to show hidden characters
        float_chars_per_scroll = float(ScrollingMessage.lcd_chars_per_scroll)
        num_scrolls = int(math.ceil(hidden_chars / float_chars_per_scroll))

        # Display the message unscrolled for a short time
        if self.lock is None:
            self.lcd.clear()
            self.lcd.message(text)
        else:
            with self.lock:
                self.lcd.clear()
                self.lcd.message(text)
        if self.beep:
            self.beeper.generate_beep()
        time.sleep(ScrollingMessage.lcd_scroll_delay)

        # Scroll the message the calculated number of times and repeat the
        # whole thing the requested number of times
        for _ in range(repeat_count + 1):
            for _ in range(num_scrolls):
                for _ in range(ScrollingMessage.lcd_chars_per_scroll):
                    got_lock = True
                    if self.lock is not None:
                        got_lock = self.lock.acquire(0)  # non-blocking
                    if got_lock:
                        # shift left once
                        self.lcd.DisplayLeft()
                        if self.lock is not None:
                            self.lock.release()
                    else:
                        return
                # bail out now if stop event is set
                if self.stop_event and self.stop_event.is_set():
                    self.lcd.home()
                    return
                # pause so it's visible
                time.sleep(ScrollingMessage.lcd_scroll_delay)
            got_lock = True
            if self.lock is not None:
                got_lock = self.lock.acquire(0)  # non-blocking
            if got_lock:
                # back to beginning of message
                self.lcd.home()
                if self.lock is not None:
                    self.lock.release()
            else:
                return

            if repeat_count:
                # bail out now if stop event is set
                if self.stop_event and self.stop_event.is_set():
                    return
                if self.beep:
                    self.beeper.generate_beep()
                # pause before next repetition
                time.sleep(ScrollingMessage.lcd_scroll_delay)

    def run(self):
        """Method to run the ScrollingMessage thread. Overrides
           threading.Thread run() method.
        """
        text_list = [self.text]
        if isinstance(self.text, list):
            text_list = self.text
        while not self.stop_event.is_set():
            for text in text_list:
                try:
                    self.scrolling_message(text, repeat_count=0)
                except:  # pylint: disable=bare-except
                    self.logger.print_and_log("Unexpected error: {}"
                                              .format(sys.exc_info()[0]))
                    self.logger.print_and_log(traceback.format_exc())
                    self.exc_queue.put("Exception in scrolling_message")
                    sys.exit(-1)


#  Class to continuously sound a warning until signalled to stop
#
#  Subclass of StoppableThread that calls the generate_beep method until
#  signalled to stop
class SoundWarning(StoppableThread):  # IVS1
    """Class to continuously sound a warning until signalled to stop"""
    def __init__(self, on_time, off_time):
        StoppableThread.__init__(self)
        self.on_time = on_time
        self.off_time = off_time
        self.off_time = off_time
        self.beeper = BeepGenerator()

    def run(self):
        """Method to run the SoundWarning thread. Overrides
           threading.Thread run() method.
        """
        while not self.stop_event.is_set():
            self.beeper.generate_beep(self.on_time, self.off_time,
                                      self.stop_event)


#  Interpolator class
#
class Interpolator():
    """Class to create an interpolated curve from an given set of data
       points, i.e. (I,V,R,P) tuples. Linear interpolation and
       centripetal Catmull-Rom spline interpolation are supported. It
       also identifies the interpolated point with the highest power.

       The initial set of points is provided by the caller as a list of
       tuples, where each of the tuples contains the (I,V,R,P)
       values. The interpolation is based on the I and V values only.

       The results are available via the following properties:

          - The linear_interpolated_curve property returns a list of
            tuples containing the initial set of points and all of the
            linearly-interpolated points

          - The spline_interpolated_curve property returns a list of
            tuples containing the initial set of points and all of the
            spline-interpolated points

          - The linear_interpolated_mpp property returns the (I,V,R,P)
            tuple of the maximum power point on the
            linearly-interpolated curve

          - The spline_interpolated_mpp property returns the (I,V,R,P)
            tuple of the maximum power point on the spline-interpolated
            curve

       """

    # Initializer
    def __init__(self, given_points):
        self.given_points = given_points  # List of (I, V, R, P)
        # Property variables
        self._linear_interpolated_curve = None
        self._spline_interpolated_curve = None
        self._linear_interpolated_mpp = None
        self._spline_interpolated_mpp = None

    # Properties
    @property
    def linear_interpolated_curve(self):
        """List of tuples that contains all of the given points plus
           points that are interpolated between the given points using
           linear interpolation. Since the only purpose of linear
           interpolation is to more accurately locate the MPP, the
           interpolation is only performed for the segments before and
           after the measured point with the highest power.
        """
        if self._linear_interpolated_curve is None:
            self._linear_interpolated_curve = []

            # Identify which of the given points has the highest power
            mwp_num = IV_Swinger.get_max_watt_point_number(self.given_points)

            # Loop through all but the last point
            for point_num, given_point in enumerate(self.given_points[:-1]):
                next_point = self.given_points[point_num + 1]
                # Set the number of interpolated points to zero unless
                # one end of the segment is the given point with the
                # highest power in which case it is set to 100
                if mwp_num not in (point_num, point_num + 1):
                    num_interp_points = 0
                else:
                    num_interp_points = 100
                # Get a list of all the interpolated I values
                new_i_vals = numpy.linspace(given_point[AMPS_INDEX],
                                            next_point[AMPS_INDEX],
                                            num_interp_points + 1,
                                            endpoint=False).tolist()
                # Get a list of all the interpolated V values
                new_v_vals = numpy.linspace(given_point[VOLTS_INDEX],
                                            next_point[VOLTS_INDEX],
                                            num_interp_points + 1,
                                            endpoint=False).tolist()
                # Create new tuples from these I and V values
                new_points = []
                for new_point_num, new_i_val in enumerate(new_i_vals):
                    new_v_val = new_v_vals[new_point_num]
                    if new_v_val:
                        new_r_val = new_i_val / new_v_val
                    else:
                        new_r_val = INFINITE_VAL
                    new_p_val = new_i_val * new_v_val
                    new_point = (new_i_val, new_v_val, new_r_val, new_p_val)
                    new_points.append(new_point)

                # Add these new (and one old) points to the interpolated
                # curve list
                self._linear_interpolated_curve.extend(new_points)

            # Tack on the last point
            self._linear_interpolated_curve.append(self.given_points[-1])

        return self._linear_interpolated_curve

    @property
    def spline_interpolated_curve(self):
        """List of tuples that contain all of the given points plus all
           of the points that are interpolated between each of the given
           points using centripetal Catmull-Rom spline interpolation
        """
        if self._spline_interpolated_curve is None:
            self._spline_interpolated_curve = []

            # Generate list of [V, I] pairs
            vi_points_list = []
            for point in self.given_points:
                vi_points_list.append([point[VOLTS_INDEX],
                                       point[AMPS_INDEX]])

            # Call the interpolation method and put the results in a
            # temporary list
            temp_points = self.catmull_rom_chain(vi_points_list)

            # At this point the curve is only [V, I] pairs and is
            # missing the first and last points. So we add the missing
            # points and compute the R and P values for each of the
            # final points in the interpolated curve. Note that there
            # are no points interpolated between the first two points
            # (Isc point and its successor) and the last two points (Voc
            # point and its predecessor). This ensures straight lines on
            # the graph for these two segments which is preferable in
            # nearly all cases to curved segments. It does assume that
            # the MPP will never be in one of these segments, but that
            # is a very good assumption.
            self._spline_interpolated_curve.append(self.given_points[0])
            for temp_point in temp_points:
                volts = temp_point[0]
                amps = temp_point[1]
                if amps:
                    ohms = volts / amps
                else:
                    ohms = INFINITE_VAL
                watts = volts * amps
                new_point = (amps, volts, ohms, watts)
                self._spline_interpolated_curve.append(new_point)
            self._spline_interpolated_curve.append(self.given_points[-1])

        return self._spline_interpolated_curve

    @property
    def linear_interpolated_mpp(self):
        """(I, V, R, P) tuple of the maximum power point on the
           linearly-interpolated curve
        """
        if self._linear_interpolated_mpp is None:
            mpp_power = 0
            points = self.linear_interpolated_curve
            for point in points:
                if point[WATTS_INDEX] >= mpp_power:
                    mpp_power = point[WATTS_INDEX]
                    mpp = point

            self._linear_interpolated_mpp = mpp

        return self._linear_interpolated_mpp

    @property
    def spline_interpolated_mpp(self):
        """(I, V, R, P) tuple of the maximum power point on the
           spline-interpolated curve
        """
        if self._spline_interpolated_mpp is None:
            mpp_power = 0
            points = self.spline_interpolated_curve
            for point in points:
                if point[WATTS_INDEX] >= mpp_power:
                    mpp_power = point[WATTS_INDEX]
                    mpp = point

            self._spline_interpolated_mpp = mpp

        return self._spline_interpolated_mpp

    # Methods
    def catmull_rom_spline(self, four_points, num_interp_points,
                           rerun_with_low_alpha=False):
        """Method mostly borrowed from the Wikipedia article on centripetal
           Catmull-Rom splines.

           The first parameter is a list of four (x,y) point pairs that
           will be used for this interpolation. The interpolation is only
           done between the middle two points and num_interp_points is the
           number of points that will be interpolated between those two
           points.

           The method returns a list of interpolated points starting with
           the second given point and ending with the third given point
           (both are included).
        """
        # pylint: disable=too-many-locals

        # Convert the points to numpy so that we can do array multiplication
        p_0, p_1, p_2, p_3 = list(map(numpy.array, [four_points[0],
                                                    four_points[1],
                                                    four_points[2],
                                                    four_points[3]]))

        # Set alpha value
        if rerun_with_low_alpha:
            # A low alpha value reduces the swings of an "S" in the
            # curve. We call the method recursively (once) with this
            # parameter set to improve the interpolation where there is
            # a non-monotonicity of the interpolation results in either
            # the I or V direction.
            alpha = 0.1
        else:
            # Otherwise, set the alpha exponent to 0.5. This is what
            # makes this a "centripetal" Catmull-Rom interpolation, and
            # it looks the best.
            alpha = 0.5

        # Local function to calculate t sub i+1 (aka t_j)
        def t_j(t_i, p_i, p_j):
            """Local function to calculate t sub i+1 (aka t_j)"""
            x_i, y_i = p_i
            x_j, y_j = p_j
            t_j = math.hypot(x_j - x_i, y_j - y_i) ** alpha + t_i
            if t_j == t_i:
                # Prevent divide-by-zero
                t_j += (1.0 / INFINITE_VAL)
            return t_j

        # Calculate t_0 to t_3
        t_0 = 0.0
        t_1 = t_j(t_0, p_0, p_1)
        t_2 = t_j(t_1, p_1, p_2)
        t_3 = t_j(t_2, p_2, p_3)

        # Only calculate points between p_1 and p_2
        t = numpy.linspace(t_1, t_2, num_interp_points)

        # Reshape so that we can multiply by the points p_0 to p_3
        # and get a point for each value of t.
        t = t.reshape(len(t), 1)

        # A equations
        a_1 = (t_1 - t) / (t_1 - t_0) * p_0 + (t - t_0) / (t_1 - t_0) * p_1
        a_2 = (t_2 - t) / (t_2 - t_1) * p_1 + (t - t_1) / (t_2 - t_1) * p_2
        a_3 = (t_3 - t) / (t_3 - t_2) * p_2 + (t - t_2) / (t_3 - t_2) * p_3

        # B equations
        b_1 = (t_2 - t) / (t_2 - t_0) * a_1 + (t - t_0) / (t_2 - t_0) * a_2
        b_2 = (t_3 - t) / (t_3 - t_1) * a_2 + (t - t_1) / (t_3 - t_1) * a_3

        # C equation
        c = (t_2 - t) / (t_2 - t_1) * b_1 + (t - t_1) / (t_2 - t_1) * b_2

        # IV curves normally are "monotonic", i.e. the voltage increases
        # along the curve and the current decreases. Even if this is
        # true for the measured points, the interpolated curve can
        # violate monotonicity, and the resulting "S" in the curve will
        # look wrong. This can happen especially in shading cases, where
        # there is a sudden inflection in the curve. This is addressed
        # by re-running the interpolation for the "S" shaped segment
        # with a smaller alpha value. This doesn't completely correct
        # the problem, but it reduces it to the point where it is much
        # less noticeable. An alternate solution would be to revert to
        # linear interpolation for such segments, but that can be too
        # harsh.
        p1_p2_points = c.tolist()
        if rerun_with_low_alpha:
            return p1_p2_points

        # Determine direction of voltage and current from p1 to
        # p2. Normal case is v_p2_gt_v_p1 and i_p2_lte_i_p1.
        v_p2_gt_v_p1 = True
        if four_points[2][0] <= four_points[1][0]:
            v_p2_gt_v_p1 = False
        v_p2_lte_v_p1 = not v_p2_gt_v_p1
        i_p2_gt_i_p1 = True
        if four_points[2][1] <= four_points[1][1]:
            i_p2_gt_i_p1 = False
        i_p2_lte_i_p1 = not i_p2_gt_i_p1
        for ii, point in enumerate(p1_p2_points):
            if ii:
                v_a = p1_p2_points[ii - 1][0]
                v_b = point[0]
                i_a = p1_p2_points[ii - 1][1]
                i_b = point[1]
                # If the voltage or current are heading in a
                # different direction than they are from p1 to p2,
                # break and re-run with low alpha
                v_diff_dir = ((v_p2_gt_v_p1 and v_b <= v_a) or
                              (v_p2_lte_v_p1 and v_b > v_a))
                i_diff_dir = ((i_p2_gt_i_p1 and i_b <= i_a) or
                              (i_p2_lte_i_p1 and i_b > i_a))
                if v_diff_dir or i_diff_dir:
                    break
        else:  # no break
            return p1_p2_points

        # We'll get here only if we hit the "break" above, meaning we
        # need to re-run with low alpha
        p1_p2_points = self.catmull_rom_spline(four_points, num_interp_points,
                                               rerun_with_low_alpha=True)
        return p1_p2_points

    def catmull_rom_chain(self, vi_points_list):
        """Method mostly borrowed from the Wikipedia article on centripetal
           Catmull-Rom splines.

           Calculate centripetal Catmull-Rom for a list of points and
           return the combined curve.

           The input is a list of lists, where each sublist is an [V, I]
           pair.

           The method returns the interpolated curve in the form of a list
           of [V, I] lists. Note that the curve begins with the second
           point in the input list and ends with the second-to-last point.
        """
        interpolated_curve = []
        for first_point_num in range(len(vi_points_list) - 3):
            four_points = [vi_points_list[first_point_num],
                           vi_points_list[first_point_num + 1],
                           vi_points_list[first_point_num + 2],
                           vi_points_list[first_point_num + 3]]
            point1 = vi_points_list[first_point_num + 1]
            point2 = vi_points_list[first_point_num + 2]
            num_interp_points = self.get_spline_num_interp_points(point1,
                                                                  point2)
            points = self.catmull_rom_spline(four_points,
                                             num_interp_points)
            interpolated_curve.extend(points)

        return interpolated_curve

    def get_spline_num_interp_points(self, point1, point2):
        """Method to calculate the desired number of interpolated points
           for a spline interpolation. The objective is to reduce
           unnecessarily granular interpolation between closely-spaced
           points. The algorithm shoots for a resolution equivalent to
           1000x1000 for the whole curve, but with a max of 100 points
           interpolated between any two points.
        """
        max_v = self.given_points[-1][VOLTS_INDEX]
        scaled_v_dist = (point2[0] - point1[0]) / max_v
        max_i = self.given_points[0][AMPS_INDEX]
        scaled_i_dist = (point1[1] - point2[1]) / max_i
        manhattan_dist = scaled_i_dist + scaled_v_dist
        num_interp_points = int(manhattan_dist * 1000)
        if num_interp_points > 100:
            num_interp_points = 100
        elif num_interp_points < 1:
            num_interp_points = 1

        return num_interp_points


#  Main IV Swinger class
#
class IV_Swinger():
    """Main IV Swinger class"""
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods

    # Initializer
    def __init__(self):
        # pylint: disable=too-many-statements

        # Property variables
        self._shutdown_on_exit = True
        self._fine_mode = True
        self._fine_mode_toggle = False
        self._loads_to_skip = 0
        self._root_dir = "/IV_Swinger"
        self._diag_mode = False
        self._headless_mode = True
        self._idle_timeout_seconds = 600
        self._idle_timeout_warning_seconds = 30
        self._dpst_gpio = 4
        self._button_gpio = 5
        self._buzzer_gpio = 18
        self._button_time_for_shutdown = 3
        self._lcd_lines = 2
        self._lcd_disp_chars_per_line = 16
        self._lcd_mem_chars_per_line = 40
        self._lcd_chars_per_scroll = 4
        self._lcd_scroll_delay = 1.2
        self._mcp23017_i2c_addr = 0x20
        self._time_between_measurements = 0.05
        self._samples_per_measurement = 2
        self._max_retries = 0
        self._voc_settle_count = 5
        self._sps = 250
        self._vdiv_r1 = 180000.0  # R1 = 180k
        self._vdiv_r2 = 8200.0    # R2 = 8.2k
        self._vdiv_r3 = 5600.0    # R3 = 5.6k
        self._vdiv_chp = 0
        self._vdiv_chn = 1
        self._amm_op_amp_rf = 82000.0  # Rf = 82k
        self._amm_op_amp_rg = 1500.0   # Rg = 1.5k
        self._amm_shunt_max_volts = 0.075
        self._amm_shunt_max_amps = 10
        self._amm_chp = 2
        self._amm_chn = 3
        self._use_gnuplot = True
        self._plot_colors = []
        self._use_spline_interpolation = True
        self._plot_power = False
        self._plot_ref = False
        self._max_i_ratio = 1.3
        self._max_v_ratio = 1.2
        self._plot_dpi = 100
        self._plot_max_x = None
        self._plot_max_y = None
        self._plot_x_inches = 11.0
        self._plot_y_inches = 8.5
        self._plot_x_scale = 1.0
        self._plot_y_scale = 1.0
        self._plot_title = None
        self._names = None
        self._label_all_iscs = False
        self._label_all_vocs = False
        self._label_all_mpps = False
        self._mpp_watts_only = False
        self._fancy_labels = False
        self._font_name = DEFAULT_FONT
        self._title_fontsize = 14
        self._axislabel_fontsize = 11
        self._ticklabel_fontsize = 9
        self._isclabel_fontsize = 11
        self._voclabel_fontsize = 11
        self._mpplabel_fontsize = 11
        self._legend_fontsize = 9
        self._font_scale = 1.0
        self._point_scale = 1.0
        self._line_scale = 1.0
        self._v_sat = None
        self._i_sat = None
        self._ax1 = None
        self._ax2 = None
        self._gp_font_scale = 1.6
        self._gp_isc_voc_mpp_pointtype = 7
        self._gp_measured_point_color = "red"
        self._gp_measured_pointtype = 6
        self._gp_measured_point_linewidth = 3
        self._gp_interp_linewidth = 6
        self._gp_interp_linetype = 3
        self._gnuplot_command = "gnuplot"
        self._filehandle = None
        self._output_line = None
        self.mp_kwargs = None
        self.logger = None
        self.beeper = None
        self.lock = None
        self.lcd = None
        # exception message queue
        self.exc_queue = queue.Queue()
        self.os_version = platform.platform()
        self.python_version = "{}.{}.{}".format(sys.version_info[0],
                                                sys.version_info[1],
                                                sys.version_info[2])
        try:
            self.matplotlib_version = matplotlib_version
        except NameError:
            self.matplotlib_version = "N/A"
        self.numpy_version = numpy.__version__

    # Properties
    @property
    def shutdown_on_exit(self):  # IVS1
        """Boolean: whether to shut down the Raspberry Pi on an
           exception or not
        """
        return self._shutdown_on_exit

    @shutdown_on_exit.setter
    def shutdown_on_exit(self, value):  # IVS1
        if value not in set([True, False]):
            raise ValueError("shutdown_on_exit must be boolean")
        self._shutdown_on_exit = value

    @property
    def fine_mode(self):  # IVS1
        """FINE mode produces better results but wears out the HALF
           relay faster.  However, with the adaptive algorithm that only
           adds the half steps where the curve is bending, most runs only
           add two extra points in FINE mode.
        """
        return self._fine_mode

    @fine_mode.setter
    def fine_mode(self, value):  # IVS1
        if value not in set([True, False]):
            raise ValueError("fine_mode must be boolean")
        self._fine_mode = value

    @property
    def fine_mode_toggle(self):  # IVS1
        """ If fine_mode_toggle is True, the pushbutton can be used to
           toggle the mode.
        """
        return self._fine_mode_toggle

    @fine_mode_toggle.setter
    def fine_mode_toggle(self, value):  # IVS1
        if value not in set([True, False]):
            raise ValueError("fine_mode_toggle must be boolean")
        self._fine_mode_toggle = value

    @property
    def loads_to_skip(self):  # IVS1
        """If loads_to_skip is non-zero, the first N load_pattern values
           in COARSE_LOAD_LIST or FINE_LOAD_LIST are skipped. This mode is
           for testing with small power supplies that have short-circuit
           protection that triggers when small load values are used.
        """
        return self._loads_to_skip

    @loads_to_skip.setter
    def loads_to_skip(self, value):  # IVS1
        self._loads_to_skip = value

    @property
    def root_dir(self):  # IVS1
        """ Root directory on SD card where results and log files are written
        """
        return self._root_dir

    @root_dir.setter
    def root_dir(self, value):  # IVS1
        if value[0] != "/":
            raise ValueError("root_dir must start with /")
        self._root_dir = value

    @property
    def logs_dir(self):  # IVS1
        """ Directory on SD card where log files are written"""
        logs_dir = os.path.join(self._root_dir, "logs")
        return logs_dir

    @property
    def diag_mode(self):  # IVS1
        """When true, this property causes the test to run in diagnostic mode
        """
        return self._diag_mode

    @diag_mode.setter
    def diag_mode(self, value):  # IVS1
        if value not in set([True, False]):
            raise ValueError("diag_mode must be boolean")
        self._diag_mode = value

    @property
    def headless_mode(self):
        """When true, this property causes the test to run in headless mode
        """
        return self._headless_mode

    @headless_mode.setter
    def headless_mode(self, value):
        if value not in set([True, False]):
            raise ValueError("headless_mode must be boolean")
        self._headless_mode = value

    @property
    def idle_timeout_seconds(self):  # IVS1
        """Amount of idle time in seconds before a shutdown is initiated"""
        return self._idle_timeout_seconds

    @idle_timeout_seconds.setter
    def idle_timeout_seconds(self, value):  # IVS1
        if value < 30:
            raise ValueError("idle_timeout_seconds must be at least 30")
        self._idle_timeout_seconds = value

    @property
    def idle_timeout_warning_seconds(self):  # IVS1
        """Number of seconds before the idle timeout that a warning is
           issued
        """
        return self._idle_timeout_warning_seconds

    @idle_timeout_warning_seconds.setter
    def idle_timeout_warning_seconds(self, value):  # IVS1
        if value > self.idle_timeout_seconds:
            raise ValueError("idle_timeout_warning seconds "
                             "must be greater than idle_timeout_seconds")
        self._idle_timeout_warning_seconds = value

    @property
    def dpst_gpio(self):  # IVS1
        """GPIO pin (BCM numbering) that the DPST is connected to"""
        return self._dpst_gpio

    @dpst_gpio.setter
    def dpst_gpio(self, value):  # IVS1
        self._dpst_gpio = value

    @property
    def button_gpio(self):  # IVS1
        """GPIO pin (BCM numbering) that the pushbutton is connected to"""
        return self._button_gpio

    @button_gpio.setter
    def button_gpio(self, value):  # IVS1
        self._button_gpio = value

    @property
    def buzzer_gpio(self):  # IVS1
        """GPIO pin (BCM numbering) that the piezo buzzer is connected to"""
        return self._buzzer_gpio

    @buzzer_gpio.setter
    def buzzer_gpio(self, value):  # IVS1
        self._buzzer_gpio = value

    @property
    def button_time_for_shutdown(self):  # IVS1
        """Amount of time in seconds that the pushbutton must be held
           down in order for a shutdown to be initiated
        """
        return self._button_time_for_shutdown

    @button_time_for_shutdown.setter
    def button_time_for_shutdown(self, value):  # IVS1
        self._button_time_for_shutdown = value

    @property
    def lcd_lines(self):  # IVS1
        """Number of lines on the LCD"""
        return self._lcd_lines

    @lcd_lines.setter
    def lcd_lines(self, value):  # IVS1
        self._lcd_lines = value

    @property
    def lcd_disp_chars_per_line(self):  # IVS1
        """Number of characters per line on the LCD display"""
        return self._lcd_disp_chars_per_line

    @lcd_disp_chars_per_line.setter
    def lcd_disp_chars_per_line(self, value):  # IVS1
        self._lcd_disp_chars_per_line = value

    @property
    def lcd_mem_chars_per_line(self):  # IVS1
        """Number of characters per LCD line that can be held in memory"""
        return self._lcd_mem_chars_per_line

    @lcd_mem_chars_per_line.setter
    def lcd_mem_chars_per_line(self, value):  # IVS1
        self._lcd_mem_chars_per_line = value

    @property
    def lcd_chars_per_scroll(self):  # IVS1
        """Number of characters to scroll on the LCD when displaying a
           scrolling message. Must be integer divisor of 24
           (1,2,3,4,6,8,12)
        """
        return self._lcd_chars_per_scroll

    @lcd_chars_per_scroll.setter
    def lcd_chars_per_scroll(self, value):  # IVS1
        if value not in set([1, 2, 3, 4, 6, 8, 12]):
            raise ValueError("lcd_chars_per_scroll must "
                             "be integer divisor of 24")
        self._lcd_chars_per_scroll = value

    @property
    def lcd_scroll_delay(self):  # IVS1
        """Time in seconds to delay between each LCD scroll"""
        return self._lcd_scroll_delay

    @lcd_scroll_delay.setter
    def lcd_scroll_delay(self, value):  # IVS1
        self._lcd_scroll_delay = value

    @property
    def mcp23017_i2c_addr(self):  # IVS1
        """Hex I2C address that the MCP23017 is jumpered to"""
        return self._mcp23017_i2c_addr

    @mcp23017_i2c_addr.setter
    def mcp23017_i2c_addr(self, value):  # IVS1
        self._mcp23017_i2c_addr = value

    @property
    def time_between_measurements(self):  # IVS1
        """Time in seconds to delay between taking measurements"""
        return self._time_between_measurements

    @time_between_measurements.setter
    def time_between_measurements(self, value):  # IVS1
        self._time_between_measurements = value

    @property
    def samples_per_measurement(self):  # IVS1
        """Number of samples to take at each measurement point"""
        return self._samples_per_measurement

    @samples_per_measurement.setter
    def samples_per_measurement(self, value):  # IVS1
        self._samples_per_measurement = value

    @property
    def max_retries(self):  # IVS1
        """Number of times to retry failed measurements"""
        return self._max_retries

    @max_retries.setter
    def max_retries(self, value):  # IVS1
        self._max_retries = value

    @property
    def voc_settle_count(self):  # IVS1
        """Number of Voc measurements to keep when determining if the
           value has settled
        """
        return self._voc_settle_count

    @voc_settle_count.setter
    def voc_settle_count(self, value):  # IVS1
        self._voc_settle_count = value

    @property
    def sps(self):  # IVS1
        """Samples per second with which to program the ADC. Must be one
           of: 8, 16, 64, 128, 250, 475, 860
        """
        return self._sps

    @sps.setter
    def sps(self, value):  # IVS1
        if value not in set([8, 16, 64, 128, 250, 475, 860]):
            raise ValueError("illegal sps value")
        self._sps = value

    # Voltage divider
    #
    # The voltage divider consists of 3 resistors rather than the typical 2:
    #
    #  PV+  ---O
    #          |
    #          |
    #          >           o +5V
    #          <  R1       |
    #          >          --- Schottky diode #1
    #          |           A
    #          |           |
    #          o-----------o----> ADC A0 input
    #          |           |
    #          |          --- Schottky diode #2
    #          |           A
    #          |           |
    #          >           o GND
    #          <  R2
    #          >
    #          |           o +5V
    #          |           |
    #          |          --- Schottky diode #3
    #          |           A
    #          |           |
    #          o-----------o----> ADC A1 input
    #          |           |
    #          |          --- Schottky diode #4
    #          >           A
    #          <  R3       |
    #          >           o GND
    #          |
    #          |
    #  PV-  ---O
    #
    # The ADC differential inputs A0 and A1 measure the voltage across
    # resistor R2.  The Schottky diode clamps assure that the voltage seen
    # at the ADC inputs cannot be greater than +5V (plus Vfwd of diode) or
    # less than 0V (minus Vfwd of diode). This protects the ADC inputs. The
    # reason for resistor R3 is to limit the current in the event that the
    # PV is connected backwards.  Without R3, if PV- is > +5V, current would
    # flow through Schottky diode #3 into the +5V rail and there might not
    # be enough load to sink that much current, which could damage the
    # battery pack.
    #
    # The equation for a three-resistor voltage divider where the output is
    # measured across the middle (R2) resistor is:
    #
    #              R2                           R1+R2+R3
    #   Vout = ---------- * Vin    OR    Vin = ---------- * Vout
    #           R1+R2+R3                           R2
    #
    # The ADC measures Vout and we want to know Vin, which is the PV
    # voltage. So we use the second equation.
    #
    @property
    def vdiv_r1(self):
        """Resistance in ohms of voltage divider resistor R1"""
        return self._vdiv_r1

    @vdiv_r1.setter
    def vdiv_r1(self, value):
        self._vdiv_r1 = value

    @property
    def vdiv_r2(self):
        """Resistance in ohms of voltage divider resistor R2"""
        return self._vdiv_r2

    @vdiv_r2.setter
    def vdiv_r2(self, value):
        self._vdiv_r2 = value

    @property
    def vdiv_r3(self):  # IVS1
        """Resistance in ohms of voltage divider resistor R3"""
        return self._vdiv_r3

    @vdiv_r3.setter
    def vdiv_r3(self, value):  # IVS1
        self._vdiv_r3 = value

    @property
    def vdiv_mult(self):  # IVS1
        """Amount that voltage divider Vout is multiplied to determine Vin"""
        vdiv_mult = (self._vdiv_r1 +
                     self._vdiv_r2 +
                     self._vdiv_r3) / self._vdiv_r2
        return vdiv_mult

    @property
    def vdiv_chp(self):  # IVS1
        """ADC channel connected to positive side of the voltage divider"""
        return self._vdiv_chp

    @vdiv_chp.setter
    def vdiv_chp(self, value):  # IVS1
        self._vdiv_chp = value

    @property
    def vdiv_chn(self):  # IVS1
        """ADC channel connected to negative side of the voltage divider"""
        return self._vdiv_chn

    @vdiv_chn.setter
    def vdiv_chn(self, value):  # IVS1
        self._vdiv_chn = value

    # Ammeter
    @property
    def amm_op_amp_rf(self):
        """Resistance in ohms of ammeter op amp resistor Rf"""
        return self._amm_op_amp_rf

    @amm_op_amp_rf.setter
    def amm_op_amp_rf(self, value):
        self._amm_op_amp_rf = value

    @property
    def amm_op_amp_rg(self):
        """Resistance in ohms of ammeter op amp resistor Rg"""
        return self._amm_op_amp_rg

    @amm_op_amp_rg.setter
    def amm_op_amp_rg(self, value):
        self._amm_op_amp_rg = value

    @property
    def amm_op_amp_gain(self):
        """Gain of ammeter op amp circuit"""
        amm_op_amp_gain = 1 + (self._amm_op_amp_rf / self._amm_op_amp_rg)
        return amm_op_amp_gain

    @property
    def amm_shunt_max_volts(self):
        """Maximum voltage across ammeter shunt resistor"""
        return self._amm_shunt_max_volts

    @amm_shunt_max_volts.setter
    def amm_shunt_max_volts(self, value):
        self._amm_shunt_max_volts = value

    @property
    def amm_shunt_max_amps(self):
        """Maximum current through ammeter shunt resistor"""
        return self._amm_shunt_max_amps

    @amm_shunt_max_amps.setter
    def amm_shunt_max_amps(self, value):  # IVS1
        self._amm_shunt_max_amps = value

    @property
    def amm_shunt_resistance(self):
        """Resistance of shunt resistor"""
        amm_shunt_resistance = (self._amm_shunt_max_volts /
                                self._amm_shunt_max_amps)
        return amm_shunt_resistance

    @property
    def amm_chp(self):  # IVS1
        """ADC channel connected to positive side of the ammeter shunt
           resistor
        """
        return self._amm_chp

    @amm_chp.setter
    def amm_chp(self, value):  # IVS1
        self._amm_chp = value

    @property
    def amm_chn(self):  # IVS1
        """ADC channel connected to negative side of the ammeter shunt
           resistor
        """
        return self._amm_chn

    @amm_chn.setter
    def amm_chn(self, value):  # IVS1
        self._amm_chn = value

    @property
    def use_gnuplot(self):
        """If True, gnuplot is used to plot the curve. If False, pyplot
           is used to plot the curve
        """
        return self._use_gnuplot

    @use_gnuplot.setter
    def use_gnuplot(self, value):
        if value not in set([True, False]):
            raise ValueError("use_gnuplot must be boolean")
        self._use_gnuplot = value

    @property
    def plot_colors(self):
        """List of colors to use for plotting multiple curves
        """
        return self._plot_colors

    @plot_colors.setter
    def plot_colors(self, value):
        self._plot_colors = value

    @property
    def use_spline_interpolation(self):
        """If True, spline interpolation is used. If False, linear
           interpolation is used.
        """
        return self._use_spline_interpolation

    @use_spline_interpolation.setter
    def use_spline_interpolation(self, value):
        if value not in set([True, False]):
            raise ValueError("use_spline_interpolation must be boolean")
        self._use_spline_interpolation = value

    @property
    def plot_power(self):
        """If True, power is plotted along with IV curve.
        """
        return self._plot_power

    @plot_power.setter
    def plot_power(self, value):
        if value not in set([True, False]):
            raise ValueError("plot_power must be boolean")
        self._plot_power = value

    @property
    def plot_ref(self):
        """If True, reference curve is plotted along with IV curve.
        """
        return self._plot_ref

    @plot_ref.setter
    def plot_ref(self, value):
        if value not in set([True, False]):
            raise ValueError("plot_ref must be boolean")
        self._plot_ref = value

    @property
    def max_i_ratio(self):
        """Ratio of I-axis range to Isc (or MPP, whichever is greater)
        """
        return self._max_i_ratio

    @max_i_ratio.setter
    def max_i_ratio(self, value):  # IVS1
        self._max_i_ratio = value

    @property
    def max_v_ratio(self):
        """Ratio of V-axis range to Voc
        """
        return self._max_v_ratio

    @max_v_ratio.setter
    def max_v_ratio(self, value):  # IVS1
        self._max_v_ratio = value

    @property
    def plot_dpi(self):
        """Dots per inch of plot
        """
        return self._plot_dpi

    @plot_dpi.setter
    def plot_dpi(self, value):
        self._plot_dpi = value

    @property
    def plot_max_x(self):
        """Max value (range) of X axis
        """
        return self._plot_max_x

    @plot_max_x.setter
    def plot_max_x(self, value):
        self._plot_max_x = value

    @property
    def plot_max_y(self):
        """Max value (range) of Y axis
        """
        return self._plot_max_y

    @plot_max_y.setter
    def plot_max_y(self, value):
        self._plot_max_y = value

    @property
    def plot_x_inches(self):
        """Width of plot in inches
        """
        return self._plot_x_inches

    @plot_x_inches.setter
    def plot_x_inches(self, value):  # IVS1
        self._plot_x_inches = value

    @property
    def plot_y_inches(self):
        """Height of plot in inches
        """
        return self._plot_y_inches

    @plot_y_inches.setter
    def plot_y_inches(self, value):  # IVS1
        self._plot_y_inches = value

    @property
    def plot_x_scale(self):
        """Amount to scale plot width (1.0 is no scaling)
        """
        return self._plot_x_scale

    @plot_x_scale.setter
    def plot_x_scale(self, value):
        self._plot_x_scale = value

    @property
    def plot_y_scale(self):
        """Amount to scale plot height (1.0 is no scaling)
        """
        return self._plot_y_scale

    @plot_y_scale.setter
    def plot_y_scale(self, value):
        self._plot_y_scale = value

    @property
    def plot_title(self):
        """Property to set the plot title"""
        return self._plot_title

    @plot_title.setter
    def plot_title(self, value):
        self._plot_title = value

    @property
    def names(self):
        """Property to set the curve names"""
        return self._names

    @names.setter
    def names(self, value):
        self._names = value

    @property
    def label_all_iscs(self):
        """Property to enable labeling all Isc points with --overlay"""
        return self._label_all_iscs

    @label_all_iscs.setter
    def label_all_iscs(self, value):
        self._label_all_iscs = value

    @property
    def label_all_vocs(self):
        """Property to enable labeling all Voc points with --overlay"""
        return self._label_all_vocs

    @label_all_vocs.setter
    def label_all_vocs(self, value):
        self._label_all_vocs = value

    @property
    def label_all_mpps(self):
        """Property to enable labeling all MPPs with --overlay"""
        return self._label_all_mpps

    @label_all_mpps.setter
    def label_all_mpps(self, value):
        self._label_all_mpps = value

    @property
    def mpp_watts_only(self):
        """Property to enable labeling MPPs with watts only (no V * I)"""
        return self._mpp_watts_only

    @mpp_watts_only.setter
    def mpp_watts_only(self, value):
        self._mpp_watts_only = value

    @property
    def fancy_labels(self):
        """Property to enable fancy labels for Isc, Voc and MPP"""
        return self._fancy_labels

    @fancy_labels.setter
    def fancy_labels(self, value):
        self._fancy_labels = value

    @property
    def font_name(self):
        """Property to set font name (family) for pyplot"""
        return self._font_name

    @font_name.setter
    def font_name(self, value):
        self._font_name = value

    @property
    def title_fontsize(self):
        """Property to set font size of title"""
        return self._title_fontsize

    @title_fontsize.setter
    def title_fontsize(self, value):  # IVS1
        self._title_fontsize = value

    @property
    def axislabel_fontsize(self):
        """Property to set font size of axis labels"""
        return self._axislabel_fontsize

    @axislabel_fontsize.setter
    def axislabel_fontsize(self, value):  # IVS1
        self._axislabel_fontsize = value

    @property
    def ticklabel_fontsize(self):
        """Property to set font size of axis tick labels"""
        return self._ticklabel_fontsize

    @ticklabel_fontsize.setter
    def ticklabel_fontsize(self, value):  # IVS1
        self._ticklabel_fontsize = value

    @property
    def isclabel_fontsize(self):
        """Property to set font size of Isc label"""
        return self._isclabel_fontsize

    @isclabel_fontsize.setter
    def isclabel_fontsize(self, value):  # IVS1
        self._isclabel_fontsize = value

    @property
    def voclabel_fontsize(self):
        """Property to set font size of Voc label"""
        return self._voclabel_fontsize

    @voclabel_fontsize.setter
    def voclabel_fontsize(self, value):  # IVS1
        self._voclabel_fontsize = value

    @property
    def mpplabel_fontsize(self):
        """Property to set font size of MPP label"""
        return self._mpplabel_fontsize

    @mpplabel_fontsize.setter
    def mpplabel_fontsize(self, value):  # IVS1
        self._mpplabel_fontsize = value

    @property
    def legend_fontsize(self):
        """Property to set font size of legend"""
        return self._legend_fontsize

    @legend_fontsize.setter
    def legend_fontsize(self, value):  # IVS1
        self._legend_fontsize = value

    @property
    def font_scale(self):
        """Amount to scale fonts (1.0 is no scaling)
        """
        return self._font_scale

    @font_scale.setter
    def font_scale(self, value):
        self._font_scale = value

    @property
    def point_scale(self):
        """Amount to scale measured points (1.0 is no scaling)
        """
        return self._point_scale

    @point_scale.setter
    def point_scale(self, value):
        self._point_scale = value

    @property
    def line_scale(self):
        """Amount to scale interpolated line (1.0 is no scaling)
        """
        return self._line_scale

    @line_scale.setter
    def line_scale(self, value):
        self._line_scale = value

    @property
    def v_sat(self):
        """Saturation voltage
        """
        return self._v_sat

    @v_sat.setter
    def v_sat(self, value):
        self._v_sat = value

    @property
    def i_sat(self):
        """Saturation current
        """
        return self._i_sat

    @i_sat.setter
    def i_sat(self, value):
        self._i_sat = value

    @property
    def ax1(self):
        """Primary pyplot axes object
        """
        return self._ax1

    @ax1.setter
    def ax1(self, value):
        self._ax1 = value

    @property
    def ax2(self):
        """Primary pyplot axes object
        """
        return self._ax2

    @ax2.setter
    def ax2(self, value):
        self._ax2 = value

    @property
    def gp_font_scale(self):
        """Scaling factor to make gnuplot fonts the same size as pyplot
           fonts
        """
        return self._gp_font_scale

    @gp_font_scale.setter
    def gp_font_scale(self, value):  # IVS1
        self._gp_font_scale = value

    @property
    def gp_isc_voc_mpp_pointtype(self):
        """Gnuplot pointtype to use for Isc, Voc, and MPP points on
           graph
        """
        return self._gp_isc_voc_mpp_pointtype

    @gp_isc_voc_mpp_pointtype.setter
    def gp_isc_voc_mpp_pointtype(self, value):  # IVS1
        self._gp_isc_voc_mpp_pointtype = value

    @property
    def gp_measured_point_color(self):
        """Gnuplot rgb color to use for measured points on graph
        """
        return self._gp_measured_point_color

    @gp_measured_point_color.setter
    def gp_measured_point_color(self, value):  # IVS1
        self._gp_measured_point_color = value

    @property
    def gp_measured_pointtype(self):
        """Gnuplot pointtype to use for measured points on graph
        """
        return self._gp_measured_pointtype

    @gp_measured_pointtype.setter
    def gp_measured_pointtype(self, value):  # IVS1
        self._gp_measured_pointtype = value

    @property
    def gp_measured_point_linewidth(self):
        """Gnuplot linewidth to use for measured points on graph
        """
        return self._gp_measured_point_linewidth

    @gp_measured_point_linewidth.setter
    def gp_measured_point_linewidth(self, value):  # IVS1
        self._gp_measured_point_linewidth = value

    @property
    def gp_interp_linewidth(self):
        """Gnuplot linewidth to use for interpolated curve on graph
        """
        return self._gp_interp_linewidth

    @gp_interp_linewidth.setter
    def gp_interp_linewidth(self, value):  # IVS1
        self._gp_interp_linewidth = value

    @property
    def gp_interp_linetype(self):
        """Gnuplot linetype to use for interpolated curve on graph
        """
        return self._gp_interp_linetype

    @gp_interp_linetype.setter
    def gp_interp_linetype(self, value):  # IVS1
        self._gp_interp_linetype = value

    @property
    def gnuplot_command(self):
        """Gnuplot command (default is "gnuplot")
        """
        return self._gnuplot_command

    @gnuplot_command.setter
    def gnuplot_command(self, value):  # IVS1
        self._gnuplot_command = value

    @property
    def filehandle(self):
        """Filehandle to share between methods
        """
        return self._filehandle

    @filehandle.setter
    def filehandle(self, value):
        self._filehandle = value

    @property
    def output_line(self):
        """Output line string to share between methods
        """
        return self._output_line

    @output_line.setter
    def output_line(self, value):
        self._output_line = value

    # -------------------------------------------------------------------------
    def set_up_gpio(self):  # IVS1
        """Method to set up the GPIO pins"""

        # Set GPIO pin numbering to BCM mode
        GPIO.setmode(GPIO.BCM)

        # Set GPIO pin connected to pushbutton switch to be an input
        GPIO.setup(self.button_gpio, GPIO.IN)

        # Set GPIO pin connected to piezo buzzer to be an output
        GPIO.setup(self.buzzer_gpio, GPIO.OUT)
        GPIO.output(self.buzzer_gpio, False)

        # Check if the pushbutton is pressed now. If it is, then exit
        # the program. The main reason for this is for the case where
        # the script is started automatically at boot, but there is an
        # exception early in the code causing a shutdown. It could be
        # impossible to get out of such a situation. For this reason,
        # the call to set_up_gpio is the first thing that the program
        # does, and this check is the first thing set_up_gpio does.
        if GPIO.input(self.button_gpio) == BUTTON_ON:
            GPIO.output(self.buzzer_gpio, True)
            time.sleep(1)
            GPIO.output(self.buzzer_gpio, False)
            print("BUTTON PRESSED - EXITING IMMEDIATELY")
            GPIO.cleanup()
            sys.exit(-1)

        # Register pushbutton callback method
        GPIO.add_event_detect(self.button_gpio, GPIO.RISING,
                              callback=self.pushbutton_callback,
                              bouncetime=300)

        # Set GPIO pin connected to DPST switch to be an input
        GPIO.setup(self.dpst_gpio, GPIO.IN)

    # Methods

    # -------------------------------------------------------------------------
    def pushbutton_callback(self, channel):  # IVS1
        """Callback method invoked when the pushbutton switch is pressed
        """
        # pylint: disable=unused-argument

        # Filter out phantom presses
        if GPIO.input(self.button_gpio) == BUTTON_OFF:
            return

        # Do the rest after acquiring the lock
        with self.lock:
            self.pushbutton_callback_locked_section()

        return

    # -------------------------------------------------------------------------
    def pushbutton_callback_locked_section(self):  # IVS1
        """Callback method invoked when the pushbutton switch is pressed
        """

        # Reset the LCD just in case it is messed up
        self.reset_lcd()

        # Create the ScrollingMessage object with lock=None so we don't
        # deadlock
        msg_text = ("Hold button {} s\nto shut down"
                    .format(self.button_time_for_shutdown))
        lcd_msg = ScrollingMessage(msg_text, self.lcd, beep=False, lock=None,
                                   exc_queue=self.exc_queue)
        lcd_msg.start()

        # If the button is still pressed, time how long it is pressed - up
        # to button_time_for_shutdown (property) seconds.
        start_time = time.time()
        pressed_time = 0
        while (GPIO.input(self.button_gpio) == BUTTON_ON and
               pressed_time < self.button_time_for_shutdown):
            pressed_time = time.time() - start_time

        # Stop the message
        lcd_msg.stop()

        # If the button was pressed for at least
        # button_time_for_shutdown (property) seconds, print a dying
        # message and shut down the RPi.  Otherwise, print a message
        # that the button was released before the shutdown was initiated
        # and toggle fine_mode.
        if pressed_time >= self.button_time_for_shutdown:
            self.shut_down(lock_held=True)
        else:
            msg_text = ["Button released\nbefore {} seconds"
                        .format(self.button_time_for_shutdown)]
            if self.fine_mode_toggle:
                if self.fine_mode:
                    self.fine_mode = False
                    msg_text.append("**COARSE MODE**")
                else:
                    self.fine_mode = True
                    msg_text.append("**FINE MODE**")
            lcd_msg = ScrollingMessage(msg_text, self.lcd, beep=True,
                                       lock=None, exc_queue=self.exc_queue)
            lcd_msg.start()
            time.sleep(1)
            lcd_msg.stop()

    # -------------------------------------------------------------------------
    def reset_lcd(self):  # IVS1
        """Method to reset the LCD"""
        # Code taken from Adafruit_CharLCD constructor

        self.lcd.write4bits(0x33)  # initialization
        self.lcd.write4bits(0x32)  # initialization
        self.lcd.write4bits(0x28)  # 2 line 5x7 matrix
        self.lcd.write4bits(0x0C)  # turn cursor off 0x0E to enable cursor
        self.lcd.write4bits(0x06)  # shift cursor right

        self.lcd.displaycontrol = (self.lcd.LCD_DISPLAYON |
                                   self.lcd.LCD_CURSOROFF |
                                   self.lcd.LCD_BLINKOFF)

        self.lcd.displayfunction = (self.lcd.LCD_4BITMODE |
                                    self.lcd.LCD_1LINE |
                                    self.lcd.LCD_5x8DOTS |
                                    self.lcd.LCD_2LINE)

        # Initialize to default text direction (for romance languages)
        self.lcd.displaymode = (self.lcd.LCD_ENTRYLEFT |
                                self.lcd.LCD_ENTRYSHIFTDECREMENT)
        self.lcd.write4bits(self.lcd.LCD_ENTRYMODESET |
                            self.lcd.displaymode)  # set entry mode

        self.lcd.clear()

    # -------------------------------------------------------------------------
    def prompt_and_wait_for_dpst_off(self):  # IVS1
        """Method to prompt the user to turn off the DPST switch and
           poll until this occurs.  While polling, the warning pattern is
           sounded.
        """
        # Create warning thread object
        warning_thread = SoundWarning(on_time=0.1, off_time=0.2)

        if GPIO.input(self.dpst_gpio) == DPST_ON:
            self.logger.print_and_log("*" * 58)
            self.logger.print_and_log("Please turn the toggle switch OFF")
            self.logger.print_and_log("*" * 58)

            # start the warning thread
            warning_thread.start()  # start the warning thread

            # display the prompt
            self.lcd.clear()
            self.lcd.message("Turn switch\nOFF now!!")

            # wait for the switch to be turned off
            while GPIO.input(self.dpst_gpio) == DPST_ON:
                time.sleep(0.2)

            # stop the warning thread and clear the message
            warning_thread.stop()
            self.lcd.clear()

    # -------------------------------------------------------------------------
    def read_adc(self, adc, chP=0, chN=1, starting_pga=6144):  # IVS1
        """Wrapper method around the readADCDifferential method.  It
           first uses different PGA gain values until it finds the optimal
           range.  The optimal range is the largest one where the reading
           is greater than 1/3 of the range (or the smallest range if none
           of the larger ranges meets this criterion). Plus we need to
           avoid using a range that is too small to accomodate the
           reading. The assumption is that the ADC is most accurate when
           the reading is near the middle of the range. If a reading is
           slightly less than 1/3 of the range, it will be less than 2/3 of
           the next smaller range and therefore not at risk for exceeding
           that range. Once the optimal range has been determined, it takes
           several readings and returns the average value, in volts.  This
           obviously exploits the assumption for this application that the
           voltage at the ADC is fairly stable.
        """

        # Determine optimal PGA range and then sample voltage at that
        # PGA gain value.  The PGA_LIST has the largest range first and
        # the smallest range last.
        for pga in PGA_LIST:
            if pga > starting_pga:
                continue
            millivolts = adc.readADCDifferential(chP, chN, pga, self.sps)
            millivolt_sum = millivolt_max = millivolt_min = \
                millivolt_avg = millivolts
            if abs(millivolts) > pga / 3 or pga == PGA_LIST[-1]:
                for _ in range(self.samples_per_measurement - 1):
                    millivolts = adc.readADCDifferential(chP, chN,
                                                         pga, self.sps)
                    millivolt_sum += millivolts
                    if millivolts > millivolt_max:
                        millivolt_max = millivolts
                    if millivolts < millivolt_min:
                        millivolt_min = millivolts
                millivolt_avg = millivolt_sum / self.samples_per_measurement
                # percent_in_range = abs((millivolt_avg / pga) * 100)
                break

        percent_error = abs(((millivolt_max - millivolt_min) /
                             millivolt_avg) * 100)

        # If the error is > 5%, force the return value to the min or max
        # - whichever is closer to the average
        if percent_error > 5:
            if (abs(millivolt_max - millivolt_avg) <
                    abs(millivolt_min - millivolt_avg)):
                millivolt_avg = millivolt_max
            else:
                millivolt_avg = millivolt_min

        # A measurement of smaller than +-1mV is assumed to be noise,
        # and the actual voltage is 0
        if abs(millivolt_avg) < 1:
            millivolt_avg = 0

        return millivolt_avg / 1000

    # -------------------------------------------------------------------------
    def read_voc(self, adc):  # IVS1
        """Method to read the current Voc voltage, but return 0 for
           voltages less than 300mV
        """
        voc_volts = self.vdiv_mult * self.read_adc(adc, self.vdiv_chp,
                                                   self.vdiv_chn, 6144)
        if abs(voc_volts) < 0.300:
            voc_volts = 0

        return voc_volts

    # -------------------------------------------------------------------------
    def measure_voc(self, adc, msg_text):  # IVS1
        """Method to continually measure Voc (10 measurements/second).
           Once a stable measurement is achieved, the user is prompted to
           turn the DPST switch on.  Voc measurements continue to be taken
           until this happens (or until the idle timeout time has passed in
           which case the system is shut down).  The msg_text parameter
           should be a string or a list of strings to prompt the user to
           turn on the toggle switch once the Voc value is stable.  The
           reason it isn't hardcoded is so the message that is displayed
           for the first iteration can be different from the message
           displayed for subsequent iterations.  The passed value of
           msg_text gets overridden when the idle timeout is close to
           expiring.  In that case, the number of seconds remaining is
           counted down on the LCD display and when the timer expires the
           system is shut down.  The only way for the user to avoid the
           autoshutdown is to turn on the DPST switch.
        """
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-statements

        # Initialize variables
        voc_volts = 0
        voc_amps = INFINITE_VAL
        voc_watts = 0
        voc_ohms = INFINITE_VAL
        prompt_printed = 0
        voc_volts_history = []
        voc_settled = 0

        # Create LCD message object with passed value of msg_text
        lcd_msg = ScrollingMessage(msg_text, self.lcd, beep=False,
                                   lock=self.lock, exc_queue=self.exc_queue)

        self.logger.print_and_log("Measuring Voc until stable ....")
        self.lcd.clear()
        self.lcd.message("Measuring Voc\nuntil stable ...")

        # Capture time the while loop is entered
        start_time = time.time()

        # Loop until switch is turned on
        while GPIO.input(self.dpst_gpio) == DPST_OFF:

            # Calculate how many seconds we've been in the loop
            loop_entry_time = time.time()
            seconds_in_loop = int(loop_entry_time) - int(start_time)

            # If the timeout has been reached, shut down
            if seconds_in_loop >= self.idle_timeout_seconds:
                lcd_msg.stop()
                self.shut_down(lock_held=False)

            # If the timeout is getting close, override the prompt message
            # with a beeping message containing the number of seconds
            # remaining
            elif seconds_in_loop >= (self.idle_timeout_seconds -
                                     self.idle_timeout_warning_seconds):
                lcd_msg.stop()
                msg_text = ("Auto shutdown\nin {} seconds!!"
                            .format(self.idle_timeout_seconds -
                                    seconds_in_loop))
                lcd_msg = ScrollingMessage(msg_text, self.lcd, beep=True,
                                           lock=self.lock,
                                           exc_queue=self.exc_queue)
                lcd_msg.start()

            # Take Voc measurements
            amm_volts = self.read_adc(adc, self.amm_chp, self.amm_chn, 6144)
            curr_voc_amps = ((amm_volts / self.amm_op_amp_gain) /
                             self.amm_shunt_resistance)
            curr_voc_volts = self.read_voc(adc)
            self.logger.log("Voc Amps: {:.6f}  Voc Volts: {:.6f}"
                            .format(curr_voc_amps, curr_voc_volts))

            # Return to caller now if voltage is negative
            if curr_voc_volts < 0.0:
                lcd_msg.stop()
                return (curr_voc_amps, curr_voc_volts, voc_ohms, voc_watts)

            # Need to check that switch is still off
            if GPIO.input(self.dpst_gpio) == DPST_OFF:
                voc_amps = curr_voc_amps
                voc_volts = curr_voc_volts
                voc_watts = voc_volts * voc_amps

                # Keep a list of the voc_volts values from each
                # iteration.  Only the most recent voc_settle_count
                # (property) values are kept.  If the list has
                # voc_settle_count entries and their standard deviation
                # is less than 0.01, the Voc value is considered
                # "settled", and the user is requested to turn the
                # switch on.  It is possible for the Voc value to become
                # "unsettled" while waiting for the user to flip the
                # switch, however, and in that case a warning is
                # printed.
                voc_volts_history.append(voc_volts)
                # trim to newest voc_settle_count entries
                del voc_volts_history[:-int(self.voc_settle_count)]
                voc_volts_history_std = numpy.std(voc_volts_history)

                if (voc_amps == 0 and
                        len(voc_volts_history) == self.voc_settle_count):
                    if voc_volts_history_std < 0.01:
                        voc_settled = 1
                    else:
                        voc_settled = 0

                if voc_settled and not prompt_printed:
                    if voc_volts <= 0.0:
                        lcd_msg.stop()
                        return (voc_amps, voc_volts, voc_ohms, voc_watts)
                    self.lcd.clear()
                    self.lcd.message("Voc: {:.2f} V".format(voc_volts))
                    time.sleep(1)
                    self.logger.print_and_log("*" * 58)
                    print_str = ("Please turn the toggle switch ON "
                                 "to begin IV curve tracing")
                    self.logger.print_and_log(print_str)
                    self.logger.print_and_log("*" * 58)
                    lcd_msg.start()
                    prompt_printed = 1

            # Rate limit to 10 Voc measurements/second
            elapsed_time = time.time() - loop_entry_time
            if elapsed_time < 0.1:
                time.sleep(0.1 - elapsed_time)

        self.logger.print_and_log(
            "Voc Volts: {:.6f} (std deviation = {:.6f} over {} measurements)"
            .format(voc_volts, voc_volts_history_std, self.voc_settle_count))

        if not voc_settled:
            print_str = ("   ===> WARNING: High Voc standard deviation; "
                         "results may be unreliable")
            self.logger.print_and_log(print_str)
            lcd_msg.stop()
            msg_text = ["==> WARNING:\nHigh Voc standard deviation",
                        "results may be\nunreliable"]
            lcd_msg = ScrollingMessage(msg_text, self.lcd, beep=True,
                                       lock=self.lock,
                                       exc_queue=self.exc_queue)
            lcd_msg.start()
            time.sleep(7)

        lcd_msg.stop()
        return (voc_amps, voc_volts, voc_ohms, voc_watts)

    # -------------------------------------------------------------------------
    def get_data_values_for_load_pattern(self, load_pattern, io_extender,
                                         adc):  # IVS1
        """Method to set the MCP23017 outputs (controlling the relays)
           to the values based on the specified load pattern and to read
           the current and voltage at that point.  Ohms and watts are
           calculated and the four values are returned in a tuple.
        """
        # pylint: disable=too-many-locals

        # Set the relays to the provided pattern
        set_relays_to_pattern(load_pattern, io_extender)

        # Pause for time_between_measurements (property) before taking
        # the voltage and current readings.
        time.sleep(self.time_between_measurements)

        # Take the current reading.  Retry a few times if the current is
        # zero, to attempt to work around failing relays. The retry
        # toggles the load pattern once in the hopes that contact will
        # be made after the toggle (but probably hastening the demise of
        # the relays in the process).
        amm_volts = self.read_adc(adc, self.amm_chp, self.amm_chn, 6144)
        self.logger.log("AMM Volts: {:.6f}".format(amm_volts))
        amps = (amm_volts / self.amm_op_amp_gain) / self.amm_shunt_resistance
        retry_count = 0
        while retry_count < self.max_retries:
            if amps == 0:
                retry_count += 1
                print_str = ("RETRY #{} for load_pattern {:#x}"
                             .format(retry_count, load_pattern))
                self.logger.print_and_log(print_str)
                time.sleep(self.time_between_measurements)
                set_relays_to_pattern(load_pattern, io_extender)
                time.sleep(self.time_between_measurements)
                set_relays_to_pattern(load_pattern, io_extender)
                time.sleep(self.time_between_measurements)
                amm_volts = self.read_adc(adc, self.amm_chp,
                                          self.amm_chn, 6144)
                self.logger.log("AMM Volts: {:.6f}".format(amm_volts))
                amps = ((amm_volts / self.amm_op_amp_gain) /
                        self.amm_shunt_resistance)
            else:
                break

        # Take the voltage reading
        volts = self.vdiv_mult * self.read_adc(adc, self.vdiv_chp,
                                               self.vdiv_chn, 6144)

        # Calculate ohms and watts
        if amps == 0.0:
            ohms = INFINITE_VAL
        else:
            ohms = volts / amps

        watts = volts * amps

        # The relay switching sometimes causes the LCD to get messed
        # up. We should probably have a snubber circuit across every
        # relay coil (in addition to the snubbers across the contacts),
        # but this software workaround will do.  We just reset the LCD
        # display before using it after we've switched one or more
        # relays (and after some time has passed).
        self.reset_lcd()

        # Print current values formatted nicely
        print_amps = ("{:.2f}".format(amps)).rjust(5)
        print_volts = ("{:.2f}".format(volts)).rjust(5)
        print_ohms = ("{:.2f}".format(ohms)).rjust(5)
        print_watts = ("{:.2f}".format(watts)).rjust(6)
        print_str = ("Amps: {}  Volts: {}  Ohms: {}  Watts: {}  "
                     "Load pattern: {}".format(print_amps, print_volts,
                                               print_ohms, print_watts,
                                               format(load_pattern, "#018b")))
        self.logger.print_and_log(print_str)
        lcd_str = ("{} A  {} V\n"
                   "{} R {} W".format(print_amps, print_volts,
                                      print_ohms, print_watts))
        self.lcd.message(lcd_str)

        return (amps, volts, ohms, watts)

    # -------------------------------------------------------------------------
    def open_circuit(self, load_pattern, io_extender):  # IVS1
        """Method to activate the OPEN relay to open the circuit, while
           keeping the other relays as they were. Once the OPEN relay is
           activated (and after a short delay), the other relays are
           inactivated. The purpose of this is to avoid inactivating the
           relays while current is flowing. This completely eliminates any
           arcing on that side of the relay (the Normally Open, "NO" side),
           which is the side without a snubber.
        """
        # Wait a short time
        time.sleep(self.time_between_measurements)

        # Set the OPEN bit in the load_pattern passed in and apply that
        # to the relays
        load_pattern |= OPEN_ONLY
        set_relays_to_pattern(load_pattern, io_extender)

        # Wait a short time
        time.sleep(self.time_between_measurements)

        # Turn off all other relays, leaving only the OPEN relay
        # activated
        set_relays_to_pattern(OPEN_ONLY, io_extender)

        # Wait a short time
        time.sleep(self.time_between_measurements)

    # -------------------------------------------------------------------------
    def get_base_loads(self, none_data_point, voc_volts):  # IVS1
        """Method to determine the "base load".  This is some combo of
           the 50W power resistors to start with before adding the finer
           grained heating coil loads.  The purpose is to center the
           fine-grained points over the knee of the curve, where they do
           the most good.  The method returns a list of the loads that need
           to be activated before the finer grained loads are activated.
        """
        base_loads = BASE_0_OHM

        # The current at the NONE load is basically Isc.  The ratio of
        # Voc to Isc is roughly the resistance at the knee.
        approx_isc = none_data_point[AMPS_INDEX]
        approx_knee_ohms = voc_volts / approx_isc

        # The base load adds to the resistance with no loads selected
        none_ohms = none_data_point[OHMS_INDEX]

        # The ideal base load is the estimated knee load minus the
        # resistance of half of the unit load chain.  Half of the unit
        # load chain is SIX+HALF, which (from empirical data) is 5.6
        # ohms (average 0.86 ohms per load).
        ideal_base_load = approx_knee_ohms - 5.6
        if ideal_base_load < (3 + none_ohms) or approx_isc > TWELVE_MAX_AMPS:
            base_loads = BASE_0_OHM
        elif (ideal_base_load < (6 + none_ohms) or
              approx_isc > THIRTEEN_MAX_AMPS):
            self.logger.print_and_log("Using 3 ohm base load")
            base_loads = BASE_3_OHM
        elif ideal_base_load < (9 + none_ohms):
            self.logger.print_and_log("Using 6 ohm base load")
            base_loads = BASE_6_OHM
        elif ideal_base_load < (12 + none_ohms):
            self.logger.print_and_log("Using 9 ohm base load")
            base_loads = BASE_9_OHM
        elif ideal_base_load < (15 + none_ohms):
            self.logger.print_and_log("Using 12 ohm base load")
            base_loads = BASE_12_OHM
        elif ideal_base_load < (18 + none_ohms):
            self.logger.print_and_log("Using 15 ohm base load")
            base_loads = BASE_15_OHM
        elif ideal_base_load < (21 + none_ohms):
            self.logger.print_and_log("Using 18 ohm base load")
            base_loads = BASE_18_OHM
        else:
            self.logger.print_and_log("Using 21 ohm base load")
            base_loads = BASE_21_OHM

        return base_loads

    # -------------------------------------------------------------------------
    def swing_iv_curve(self, io_extender, adc, voc_volts):  # IVS1
        """Method to cycle through the load values using the relays,
           taking a current and voltage measurement at each point.  The
           results are returned in a list of 4-entry tuples
           (amps,volts,ohms,watts). If the diag_mode property is set, the
           relays are activated individually.  If the fine_mode property is
           set, the load list containing all of the half and full steps is
           used.  This wears out the HALF relay faster than the others, but
           this is mitigated by skipping the half steps on parts of the
           curve that are relatively straight lines.  If the fine_mode
           property is not set, the load list with full steps (starting
           with HALF) is used. An adaptive algorithm is used to determine a
           "base load", i.e. one or more of the power resistors.  See the
           documentation for the get_base_loads method for more
           information. If the measured current is zero when the
           load_pattern is NONE the method returns an empty list.
        """
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-statements

        # Diag mode - activate each relay alone
        if self.diag_mode:
            data_points = [(0, 0, 0, 0)]  # placeholder for Isc
            for load_pattern in DIAG_LOAD_LIST:
                data_point = (
                    self.get_data_values_for_load_pattern(
                        load_pattern, io_extender, adc))
                data_points.append(data_point)
                return data_points

        # Fine vs coarse mode
        if self.fine_mode:
            # FINE mode - better results, but wears out the HALF relay
            # faster
            whole_load_list = FINE_LOAD_LIST
        else:
            whole_load_list = COARSE_LOAD_LIST

        # Remove first N entries if loads_to_skip is non-zero
        load_list = whole_load_list[self.loads_to_skip:]

        data_points_unsorted = [(0, 0, 0, 0)]  # placeholder for Isc
        base_load_pattern = NONE
        prev_load_pattern = 0xa5a5
        for load_pattern in load_list:
            skip_this_one = False
            load_pattern_with_base = load_pattern | base_load_pattern

            # Skip this measurement if the current load pattern is the
            # same as the previous one (which happens when using a
            # base_load_pattern).
            if load_pattern_with_base == prev_load_pattern:
                skip_this_one = True

            # Skip this measurement if we're in FINE mode, and the
            # current load pattern does not include the HALF load, AND
            # the previously measured point is very close to being in
            # line with its two predecessors.  The idea is to avoid the
            # HALF steps (which wear out the relay) if they add no
            # value.  Note that the FINE mode load list is out of order,
            # i.e. the X_AND_A_HALF loads precede the X loads.  So we
            # optionally go backwards by half a step when we determine
            # that the curve is bending, which adds resolution where we
            # need it.  But where the line is straight, we skip the half
            # steps.
            #
            # We'll call the previous three measurements points 1, 2 and
            # 3 (from oldest to newest). To determine if the curve is
            # "bending", we first need to calculate the slopes of the
            # lines through points 1 and 2 and points 2 and 3.  But
            # we're interested in the slopes as they appear visually on
            # a graph that is scaled at approximately the ratio of Voc
            # to Isc.
            #
            #  Factor to scale current (I) values by:
            #    i_scale = Voc/Isc
            #
            #  Scaled (visual) slope of line through points 1 and 2:
            #    m12 = i_scale(i2 - i1)/(v2 - v1)
            #
            #  Scaled (visual) slope of line through points 2 and 3:
            #    m23 = i_scale(i3 - i2)/(v3 - v2)
            #
            # The angular difference between the lines is the difference
            # in the arctangents of their slopes.
            #
            #  rot_degrees = arctan(m12) - arctan(m23)
            #
            # One last factor to account for is the distance between the
            # points on the graph.  If the points are very close
            # together, it's not worth adding a point between them for
            # the same inflection angle as points that are farther
            # apart.  The scaling factor is needed for this calculation
            # too.
            #
            # Distance between points 2 and 3:
            #    d23 = sqrt((v3 - v2)^2 + (i_scale(i3 - i2))^2)
            #
            # The final criterion for skipping the half-step point is:
            #
            # Skip if:
            #    rot_degrees * d23 < 50
            #
            # The threshold of 50 was determined empirically.
            #
            if (self.fine_mode and load_pattern != load_list[0] and
                    (load_pattern & HALF_ONLY == 0) and
                    (len(data_points_unsorted) > 2)):
                data_points_sorted = sorted(data_points_unsorted,
                                            key=lambda dp: dp[OHMS_INDEX])
                i1 = data_points_sorted[-3][AMPS_INDEX]
                v1 = data_points_sorted[-3][VOLTS_INDEX]
                i2 = data_points_sorted[-2][AMPS_INDEX]
                v2 = data_points_sorted[-2][VOLTS_INDEX]
                i3 = data_points_sorted[-1][AMPS_INDEX]
                v3 = data_points_sorted[-1][VOLTS_INDEX]
                # The NONE data point is the closest we have to Isc now
                if data_points_sorted[1][AMPS_INDEX]:
                    i_scale = voc_volts / data_points_sorted[1][AMPS_INDEX]
                else:
                    i_scale = INFINITE_VAL
                m12 = i_scale * (i2 - i1) / (v2 - v1)
                m23 = i_scale * (i3 - i2) / (v3 - v2)
                d23 = math.hypot(v3 - v2, i_scale * (i3 - i2))
                rot_degrees = (math.degrees(math.atan(m12)) -
                               math.degrees(math.atan(m23)))
                weight = abs(rot_degrees) * d23
                print_str = ("m12: {} m23: {} d23: {} Rot degrees: {} "
                             "Weight: {} Load pattern: {}"
                             .format(m12, m23, d23, rot_degrees, weight,
                                     format(load_pattern, "#018b")))
                self.logger.log(print_str)
                if weight < 50:
                    skip_this_one = True
                else:
                    self.logger.log("ADDING HALF STEP POINT")

            # Unless we're skipping this point for one of the reasons
            # above, get its data values and add them to the list
            if not skip_this_one:
                data_point = (
                    self.get_data_values_for_load_pattern(
                        load_pattern_with_base, io_extender, adc))
                prev_load_pattern = load_pattern_with_base
                data_points_unsorted.append(data_point)

            # When the NONE measurement has been taken, determine if one
            # or more base loads are needed, and if so then get the data
            # values for the base load(s).  Set base_load_pattern to the
            # OR of the base loads so the sum of the loads will be
            # included in the pattern used above in the following
            # iterations.
            if load_pattern == NONE:
                if data_point[AMPS_INDEX] == 0:
                    # No current with all loads bypassed - something is
                    # wrong. Return empty list to indicate this to the
                    # caller.
                    return []
                base_loads = self.get_base_loads(data_point, voc_volts)
                if base_loads != BASE_0_OHM:
                    for base_load in base_loads:
                        base_load_pattern |= base_load
                        data_point = (
                            self.get_data_values_for_load_pattern(
                                base_load_pattern, io_extender, adc))
                        prev_load_pattern = base_load_pattern
                        data_points_unsorted.append(data_point)

        # Activate the OPEN relay without changing others, and then
        # deactivate the others
        self.open_circuit(load_pattern, io_extender)

        # Sort the list in order of increasing resistance (needed
        # because the fine mode load list is out of order)
        data_points = sorted(data_points_unsorted,
                             key=lambda dp: dp[OHMS_INDEX])

        return data_points

    # -------------------------------------------------------------------------
    @staticmethod
    def get_max_watt_point_number(data_points):
        """Method to find and return the measured data point number with
           the highest power.  The actual Maximum Power Point (MPP) is most
           likely not exactly at this point, but somewhere between this
           point and one of its neighbors and will be found later via
           interpolation.
        """
        max_watt_point_number = 0

        for data_point_num, data_point in enumerate(data_points):
            if (data_point[WATTS_INDEX] >
                    data_points[max_watt_point_number][WATTS_INDEX]):
                max_watt_point_number = data_point_num

        return max_watt_point_number

    # -------------------------------------------------------------------------
    def extrapolate_isc(self, data_points, max_watt_point_number):  # IVS1
        """Method to extrapolate the Isc value from the first two
           measured data points.
        """
        if len(data_points) > 1:
            i1 = data_points[1][AMPS_INDEX]  # NONE data point
            v1 = data_points[1][VOLTS_INDEX]
        else:
            i1 = 0
            v1 = 0

        if len(data_points) > 2:
            i2 = data_points[2][AMPS_INDEX]  # HALF data point
            v2 = data_points[2][VOLTS_INDEX]
        else:
            i2 = i1
            v2 = v1

        if v2 != v1 and max_watt_point_number > 3:
            # Find y (aka I) intercept of line connecting first two
            # measured points.
            #
            # We all remember the y = mx + b form of a linear
            # equation. y is current, x is voltage, and b is the
            # y-intercept, i.e. Isc.  So:
            #
            #   i = mv + Isc
            #
            # m is slope = rise/run = (i2 - i1)/(v2 - v1)
            #
            # So now:
            #
            #    i = ((i2 - i1)/(v2 - v1)) * v + Isc
            #
            #  Isc = i - ((i2 - i1)/(v2 - v1)) * v
            #
            #  Since this equation is valid for any point (v, i) on the
            #  line, we can substitute i1 and v1 for i and v:
            #
            #  Isc = i1 - ((i2 - i1)/(v2 - v1)) * v1
            #
            isc_amps = i1 - ((i2 - i1) / (v2 - v1)) * v1

            # If the extrapolated value is greater than 2% more than the
            # measured NONE value, it's probaby because there aren't
            # enough sampled points at the beginning of the curve
            # (e.g. if there's a base load, but there is shading).  In
            # that case, just return a value 2% greater than the
            # measured NONE value.
            if isc_amps > 1.02 * i1:
                isc_amps = 1.02 * i1

        else:
            # If the voltages of the first two points are equal (most
            # likely because both are zero - PV isn't connected), the
            # equation above gets a divide-by-zero error so we just set
            # Isc to the value of the first point.  Also if the highest
            # measured power is on one of the first three (or four)
            # points, the knee of the curve is too close to use a linear
            # extrapolation from the first two points since the second
            # point is likely already somewhat over the knee and the
            # calculated Isc will be too high.  So we just set Isc to
            # the value of the first point in that case too.
            isc_amps = i1

        isc_volts = 0
        isc_ohms = 0
        isc_watts = 0
        self.logger.log("Isc Amps: {:.6f}".format(isc_amps))

        return (isc_amps, isc_volts, isc_ohms, isc_watts)

    # -------------------------------------------------------------------------
    def write_gnuplot_file(self, gp_command_filename, data_filenames,
                           img_filename, isc_amps, voc_volts, mpp_amps,
                           mpp_volts):
        """Method to write the gnuplot command file"""
        # pylint: disable=too-many-arguments

        with open(gp_command_filename, "w",
                  encoding="utf-8") as self.filehandle:

            # Set the figure size
            self.set_figure_size()

            # Set output to the plot image filename
            output_line = 'set output "{}"\n'.format(img_filename)
            self.filehandle.write(output_line)

            # Set the key font
            self.set_key_font()

            # Set the title
            self.set_figure_title(data_filenames)

            # Set the X and Y labels for the plot
            self.set_x_label()
            self.set_y_label()

            # Set the X and Y ranges
            max_x = self.set_x_range(voc_volts)
            max_y = self.set_y_range(isc_amps, mpp_amps)

            # Adjust margins
            self.adjust_margins()

            # Display ticks and grid lines on graph
            self.set_x_ticks(max_x)
            self.set_y_ticks(max_y)
            self.display_grid()

            # Plot and label the Isc point(s)
            self.plot_and_label_isc(isc_amps, None, None, None)

            # Plot and label the MPP(s)
            self.plot_and_label_mpp(mpp_amps, mpp_volts, None, None, None)

            # Plot and label the Voc point(s)
            self.plot_and_label_voc(voc_volts, None, None, None)

            # Plot the measured points and the interpolated curves
            self.plot_points_and_curves(data_filenames, mpp_volts)

            # If not in headless mode, open interactive display
            if not self.headless_mode:
                self.open_interactive_display()

    # -------------------------------------------------------------------------
    def plot_with_plotter(self, sd_gp_command_filename,
                          sd_data_point_filenames, sd_img_filename,
                          isc_amps, voc_volts, mpp_amps, mpp_volts):
        """Method to generate the graph with gnuplot or pyplot.

           The following parameters are lists:

              sd_data_point_filenames
              isc_amps
              voc_volts
              mpp_amps
              mpp_volts

           The normal case is that these lists all have a length of 1 and a
           single curve is plotted. Support for larger lists is included
           for external post-processing software that uses this method to
           plot multiple curves (up to 8) on the same graph.
        """
        # pylint: disable=too-many-arguments

        # Set colors
        self.set_plot_colors()

        # Check args
        self.check_plot_with_plotter_args(sd_data_point_filenames,
                                          isc_amps, voc_volts, mpp_amps,
                                          mpp_volts)

        # Call the appropriate plot method
        if self.use_gnuplot:
            self.plot_with_gnuplot(sd_gp_command_filename,
                                   sd_data_point_filenames, sd_img_filename,
                                   isc_amps, voc_volts, mpp_amps, mpp_volts)
        else:
            self.plot_with_pyplot_with_retry(sd_data_point_filenames,
                                             sd_img_filename, isc_amps,
                                             voc_volts, mpp_amps, mpp_volts)

    # -------------------------------------------------------------------------
    def plot_with_gnuplot(self, sd_gp_command_filename,
                          sd_data_point_filenames, sd_img_filename,
                          isc_amps, voc_volts, mpp_amps, mpp_volts):
        """Method to generate the graph with gnuplot.
        """
        # pylint: disable=too-many-arguments

        # Write the gnuplot command file
        self.write_gnuplot_file(sd_gp_command_filename,
                                sd_data_point_filenames, sd_img_filename,
                                isc_amps, voc_volts,
                                mpp_amps, mpp_volts)

        # Execute the gnuplot command file
        if isc_amps and voc_volts:
            subprocess.call([self.gnuplot_command, sd_gp_command_filename])

    # -------------------------------------------------------------------------
    def get_and_log_pyplot_font_names(self):
        """Method to get the list of font names (families) available for pyplot
           plots. The list is returned to the caller (as a string with
           newlines) and is also written to the log file.
        """
        fonts = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
        font_names_str = ""
        for font_name in sorted(fonts):
            font_names_str += "{}\n".format(font_name)
        self.logger.log("Plotting fonts:\n{}".format(font_names_str))
        return font_names_str

    # -------------------------------------------------------------------------
    def set_pyplot_font_name(self):
        """Method to set the font name (family) for pyplot plots"""
        plt.rc('font', family=self.font_name)

    # -------------------------------------------------------------------------
    def plot_with_pyplot(self, sd_data_point_filenames, sd_img_filename,
                         isc_amps, voc_volts, mpp_amps, mpp_volts):
        """Method to generate the graph with pyplot.

           The following parameters are lists:

              sd_data_point_filenames
              isc_amps
              voc_volts
              mpp_amps
              mpp_volts

           The normal case is that these lists all have a length of 1 and a
           single curve is plotted. Support for larger lists is included
           for external post-processing software that uses this method to
           plot multiple curves (up to 8) on the same graph.
        """
        # pylint: disable=too-many-arguments

        # Set the font
        self.set_pyplot_font_name()

        # Set the figure size
        self.set_figure_size()

        # Set the ax1 property
        self.ax1 = plt.gca()

        # Set the title
        self.set_figure_title(sd_data_point_filenames)

        # Set the X and Y labels for the plot
        self.set_x_label()
        self.set_y_label()

        # Set the X and Y ranges
        max_x = self.set_x_range(voc_volts)
        max_y = self.set_y_range(isc_amps, mpp_amps)

        # Display ticks and grid lines on graph
        self.set_x_ticks(max_x)
        self.set_y_ticks(max_y)
        self.display_grid()

        # Plot the measured points and the interpolated curves
        self.plot_points_and_curves(sd_data_point_filenames, mpp_volts)

        # Plot and label Isc, MPP and Voc
        self.plot_labeled_points(isc_amps, mpp_amps, mpp_volts, voc_volts)

        # Shade voltage saturation area
        self.shade_v_sat_area()

        # Shade current saturation area
        self.shade_i_sat_area()

        # Display legend
        self.display_legend()

        # Adjust margins
        self.adjust_margins()

        # Print to the image file
        self.print_to_img_file(sd_img_filename)

        # If not in headless mode, open interactive display
        if not self.headless_mode:
            self.open_interactive_display()

        # Clear the figure in preparation for the next plot
        plt.clf()

    # -------------------------------------------------------------------------
    def plot_with_pyplot_with_retry(self, sd_data_point_filenames,
                                    sd_img_filename, isc_amps, voc_volts,
                                    mpp_amps, mpp_volts):
        """Method to run the plot_with_pyplot method, retrying with the default
           font if it fails due to an unsupported font.
        """
        # pylint: disable=too-many-arguments
        try:
            with warnings.catch_warnings():
                filter_str = r"Glyph \d+ missing from current font"
                warnings.filterwarnings("ignore", filter_str,
                                        RuntimeWarning)
                self.plot_with_pyplot(sd_data_point_filenames, sd_img_filename,
                                      isc_amps, voc_volts, mpp_amps, mpp_volts)
        except RuntimeError as e:
            if str(e) == "TrueType font is missing table":
                plt.clf()
                log_str = "Couldn't create {} with font {}; using default font"
                self.logger.print_and_log(log_str.format(sd_img_filename,
                                                         self.font_name))
                self.font_name = DEFAULT_FONT
                self.plot_with_pyplot(sd_data_point_filenames, sd_img_filename,
                                      isc_amps, voc_volts, mpp_amps, mpp_volts)

    # -------------------------------------------------------------------------
    def plot_labeled_points(self, isc_amps, mpp_amps, mpp_volts, voc_volts):
        """Method to plot and label the Isc, MPP, and Voc points"""

        # Set annotate options
        (xytext_offset, bbox, arrowprops) = self.set_annotate_options()

        # Plot and label the Isc point(s)
        self.plot_and_label_isc(isc_amps, xytext_offset, bbox, arrowprops)

        # Plot and label the MPP(s)
        self.plot_and_label_mpp(mpp_amps, mpp_volts,
                                xytext_offset, bbox, arrowprops)

        # Plot and label the Voc point(s)
        self.plot_and_label_voc(voc_volts, xytext_offset, bbox, arrowprops)

    # -------------------------------------------------------------------------
    def shade_v_sat_area(self):
        """Method to shade the area above the voltage saturation value"""
        if self.v_sat is not None:
            self.ax1.fill_between([self.v_sat, self.plot_max_x],
                                  [self.plot_max_y, self.plot_max_y],
                                  0,
                                  edgecolor="lightgrey",
                                  facecolor="lightgrey")
            fontsize = self.title_fontsize * self.font_scale
            plt.annotate("Max voltage\n exceeded",
                         xy=((9.0 * self.v_sat + self.plot_max_x)/10.0,
                             self.plot_max_y/2.0),
                         fontsize=fontsize,
                         horizontalalignment="left",
                         verticalalignment="bottom")

    # -------------------------------------------------------------------------
    def shade_i_sat_area(self):
        """Method to shade the area above the current saturation value"""

        if self.i_sat is not None:
            self.ax1.fill_between([self.plot_max_x, 0.0],
                                  [self.i_sat, self.i_sat],
                                  self.plot_max_y,
                                  edgecolor="lightgrey",
                                  facecolor="lightgrey")
            fontsize = self.title_fontsize * self.font_scale
            plt.annotate("Max current exceeded",
                         xy=(self.plot_max_x/2.0,
                             (self.plot_max_y + self.i_sat)/2.0),
                         fontsize=fontsize,
                         horizontalalignment="right",
                         verticalalignment="bottom")

    # -------------------------------------------------------------------------
    def set_plot_colors(self):
        """Method to set the colors for plotter curves"""

        self.plot_colors = PLOT_COLORS

    # -------------------------------------------------------------------------
    def check_plot_with_plotter_args(self, sd_data_point_filenames,
                                     isc_amps, voc_volts, mpp_amps,
                                     mpp_volts):
        """Method to check the args passed to the plot_with_gnuplot or
           plot_with_pyplot method
        """
        # pylint: disable=too-many-arguments

        max_len = len(self.plot_colors)
        assert len(sd_data_point_filenames) <= max_len, \
            "Max of {} curves supported".format(max_len)
        assert len(isc_amps) == len(sd_data_point_filenames), \
            "isc_amps list must be same size as sd_data_point_filenames list"
        assert len(voc_volts) == len(sd_data_point_filenames), \
            "voc_volts list must be same size as sd_data_point_filenames list"
        assert len(mpp_amps) == len(sd_data_point_filenames), \
            "mpp_amps list must be same size as sd_data_point_filenames list"
        assert len(mpp_volts) == len(sd_data_point_filenames), \
            "mpp_volts list must be same size as sd_data_point_filenames list"

    # -------------------------------------------------------------------------
    def set_figure_size(self):
        """Method to set the plotter figure size"""

        # Set the figure size to 11 x 8.5 (optionally scaled)
        scaled_x_inches = self.plot_x_inches * self.plot_x_scale
        scaled_y_inches = self.plot_y_inches * self.plot_y_scale
        if self.use_gnuplot:
            self.filehandle.write("set terminal pdf size {},{}\n"
                                  .format(scaled_x_inches, scaled_y_inches))
        else:
            plt.gcf().set_size_inches(scaled_x_inches, scaled_y_inches)

    # -------------------------------------------------------------------------
    def set_figure_title(self, sd_data_point_filenames):
        """Method to set the plotter figure title"""
        if len(sd_data_point_filenames) > 1 and not self.plot_ref:
            run_str = "{} Runs".format(len(sd_data_point_filenames))
        else:
            run_str = (sd_data_point_filenames[0] if not self.plot_ref else
                       sd_data_point_filenames[1])
            date_time_str = DateTimeStr.extract_date_time_str(run_str)
            if date_time_str == "No match":
                run_str += " Run"
            else:
                (date_str,
                 time_str) = DateTimeStr.xlate_date_time_str(date_time_str)
                run_str = "{}@{}".format(date_str, time_str)
        if self.plot_title is None:
            title_str = "IV Swinger Plot for {}".format(run_str)
        else:
            title_str = self.plot_title
        fontsize = self.title_fontsize * self.font_scale
        if self.use_gnuplot:
            if sys.platform == "darwin":
                # On Mac @ sign is lost
                title_str = title_str.replace("@", " at ")
            fontsize *= self.gp_font_scale
            y_offset = self.font_scale - 0.5
            self.filehandle.write('set title "{}" offset 0,{} font ",{}"\n'
                                  .format(title_str, y_offset, fontsize))
        else:
            plt.title(title_str, fontsize=fontsize, y=1.02)

    # -------------------------------------------------------------------------
    def set_x_label(self):
        """Method to set the plotter X axis label"""
        x_label = "Voltage (volts)"
        fontsize = self.axislabel_fontsize * self.font_scale
        if self.use_gnuplot:
            fontsize *= self.gp_font_scale
            y_offset = 1.0 - self.font_scale
            self.filehandle.write('set xlabel "{}" offset 0,{} font ",{}"\n'
                                  .format(x_label, y_offset, fontsize))
        else:
            plt.xlabel(x_label, fontsize=fontsize)

    # -------------------------------------------------------------------------
    def set_y_label(self):
        """Method to set the plotter Y axis label"""
        y_label = "Current (amps)"
        fontsize = self.axislabel_fontsize * self.font_scale
        if self.use_gnuplot:
            fontsize *= self.gp_font_scale
            x_offset = 3.0 * (1.0 - self.font_scale)
            self.filehandle.write('set ylabel "{}" offset 0,{} font ",{}"\n'
                                  .format(y_label, x_offset, fontsize))
        else:
            plt.ylabel(y_label, fontsize=fontsize)

    # -------------------------------------------------------------------------
    def set_x_range(self, voc_volts):
        """Method to set the plotter X axis range. Returns the maximum X
           value
        """
        if self.plot_max_x is not None:
            max_x = self.plot_max_x
        else:
            max_x = 0
            for volts in voc_volts:
                # Round volts
                if volts >= 10.0:
                    # First divide by two and round to 3 s.f.
                    volts_div2 = round(volts/2.0, 1)
                    # Then round that to 2 s.f. and double
                    volts = round(volts_div2, 0) * 2.0
                elif volts >= 1.0:
                    volts_div2 = round(volts/2.0, 2)
                    volts = round(volts_div2, 1) * 2.0
                else:
                    volts_div2 = round(volts/2.0, 3)
                    volts = round(volts_div2, 2) * 2.0
                if volts * self.max_v_ratio > max_x:
                    max_x = volts * self.max_v_ratio
        if max_x > 0:
            self.plot_max_x = max_x
            if self.use_gnuplot:
                output_line = "set xrange [0:{}]\n".format(max_x)
                self.filehandle.write(output_line)
            else:
                plt.xlim(0, max_x)

        self.plot_max_x = max_x
        return max_x

    # -------------------------------------------------------------------------
    def set_y_range(self, isc_amps, mpp_amps):
        """Method to set the plotter Y axis range. Returns the maximum Y
           value
        """
        if self.plot_max_y is not None:
            max_y = self.plot_max_y
        else:
            max_y = 0
            for amps in isc_amps + mpp_amps:
                # Round amps
                if amps >= 10.0:
                    # First divide by five and round to 3 s.f.
                    amps_div5 = round(amps/5.0, 1)
                    # Then round that to 2 s.f. and multiply by five
                    amps = round(amps_div5, 0) * 5.0
                elif amps >= 1.0:
                    amps_div5 = round(amps/5.0, 2)
                    amps = round(amps_div5, 1) * 5.0
                elif amps >= 0.1:
                    amps_div5 = round(amps/5.0, 3)
                    amps = round(amps_div5, 2) * 5.0
                elif amps >= 0.01:
                    amps_div5 = round(amps/5.0, 4)
                    amps = round(amps_div5, 3) * 5.0
                else:
                    amps_div5 = round(amps/5.0, 5)
                    amps = round(amps_div5, 4) * 5.0
                # The isc_amps value is negative when we want to
                # suppress plotting the Isc point. But we still need its
                # magnitude to determine the max_y value, so we use
                # abs().
                if abs(amps) * self.max_i_ratio > max_y:
                    max_y = abs(amps) * self.max_i_ratio
        if max_y > 0:
            self.plot_max_y = max_y
            if self.use_gnuplot:
                output_line = "set yrange [0:{}]\n".format(max_y)
                self.filehandle.write(output_line)
            else:
                plt.ylim(0, max_y)

        self.plot_max_y = max_y
        return max_y

    # -------------------------------------------------------------------------
    def set_x_ticks(self, max_x):
        """Method to set the plotter X-axis ticks"""
        if max_x < 1:
            step = 0.05
        elif max_x < 2:
            step = 0.1
        elif max_x < 4.5:
            step = 0.2
        elif max_x < 9:
            step = 0.5
        elif max_x < 18:
            step = 1.0
        elif max_x < 36:
            step = 2.0
        else:
            step = 4.0
        fontsize = self.ticklabel_fontsize * self.font_scale
        if self.use_gnuplot:
            fontsize *= self.gp_font_scale
            output_line = 'set xtics {} font ",{}"\n'.format(step, fontsize)
            self.filehandle.write(output_line)
        else:
            plt.xticks(numpy.arange(0, max_x, step), fontsize=fontsize)

    # -------------------------------------------------------------------------
    def set_y_ticks(self, max_y):
        """Method to set the plotter Y-axis ticks"""
        if max_y < 0.01:
            step = 0.001
        elif max_y < 0.02:
            step = 0.002
        elif max_y < 0.05:
            step = 0.005
        elif max_y < 0.1:
            step = 0.01
        elif max_y < 0.2:
            step = 0.02
        elif max_y < 0.5:
            step = 0.05
        elif max_y < 1:
            step = 0.1
        elif max_y < 2:
            step = 0.2
        elif max_y < 5:
            step = 0.5
        else:
            step = 1.0
        fontsize = self.ticklabel_fontsize * self.font_scale
        if self.use_gnuplot:
            fontsize *= self.gp_font_scale
            output_line = 'set ytics {} font ",{}"\n'.format(step, fontsize)
            self.filehandle.write(output_line)
        else:
            plt.yticks(numpy.arange(0, max_y, step), fontsize=fontsize)

    # -------------------------------------------------------------------------
    def display_grid(self):
        """Method to display the plotter grid"""
        if self.use_gnuplot:
            output_line = "set grid\n"
            self.filehandle.write(output_line)
        else:
            plt.grid(True)

    # -------------------------------------------------------------------------
    def set_annotate_options(self):
        """Method to set the plotter annotation options (for Isc, Voc,
           and MPP labels)
        """
        if self.fancy_labels:
            xytext_offset = 10
            bbox = dict(boxstyle="round", facecolor="yellow")
            arrowprops = dict(arrowstyle="->")
        else:
            xytext_offset = 0
            bbox = dict(boxstyle="square, pad=0",
                        facecolor="white", edgecolor="white")
            arrowprops = None

        return (xytext_offset, bbox, arrowprops)

    # -------------------------------------------------------------------------
    def plot_and_label_isc(self, isc_amps, xytext_offset, bbox, arrowprops):
        """Method to plot and label/annotate the Isc point(s)"""
        fontsize = self.isclabel_fontsize * self.font_scale
        prev_isc_str_width = 0
        for ii, isc_amp in enumerate(isc_amps):
            if isc_amp >= 10.0:
                isc_str = "Isc = {:.1f} A".format(isc_amp)
            elif isc_amp >= 1.0:
                isc_str = "Isc = {:.2f} A".format(isc_amp)
            else:
                isc_str = "Isc = {:.3f} A".format(isc_amp)
            if self.use_gnuplot:
                gp_isc_str = ' ""'
                if not ii or self.label_all_iscs or self.plot_ref:
                    gp_isc_str = ' "{}"'.format(isc_str)
                self.gnuplot_label_point(gp_isc_str,
                                         0, isc_amp,
                                         1 + ii * 15 * self.font_scale, 1,
                                         fontsize)
            else:
                self.pyplot_add_point(0, isc_amp)
                if not ii or self.label_all_iscs or self.plot_ref:
                    xtext_offset = (xytext_offset + 5 + ii *
                                    int(6.25 * prev_isc_str_width) *
                                    self.font_scale)
                    ytext_offset = xytext_offset + 5
                    pyplot_annotate_point(isc_str, 0, isc_amp,
                                          xtext_offset, ytext_offset,
                                          fontsize, bbox, arrowprops)
            prev_isc_str_width = len(isc_str)

    # -------------------------------------------------------------------------
    def plot_and_label_mpp(self, mpp_amps, mpp_volts,
                           xytext_offset, bbox, arrowprops):
        """Method to plot and label/annotate the MPP(s)"""
        # pylint: disable=too-many-arguments
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-statements

        fontsize = self.mpplabel_fontsize * self.font_scale
        max_mpp_volts = max(mpp_volts)
        for ii, mpp_amp in enumerate(mpp_amps):
            if mpp_volts[ii] >= 10.0:
                mppv_str = "{:.1f}".format(mpp_volts[ii])
            elif mpp_volts[ii] >= 1.0:
                mppv_str = "{:.2f}".format(mpp_volts[ii])
            else:
                mppv_str = "{:.3f}".format(mpp_volts[ii])
            if mpp_amp >= 10.0:
                mppa_str = "{:.1f}".format(mpp_amp)
            elif mpp_amp >= 1.0:
                mppa_str = "{:.2f}".format(mpp_amp)
            else:
                mppa_str = "{:.3f}".format(mpp_amp)
            mpp_volts_x_amps_str = (" ({} * {})"
                                    .format(mppv_str, mppa_str))
            if self.mpp_watts_only:
                mpp_volts_x_amps_str = ""
            mpp_watts = mpp_volts[ii] * mpp_amp
            if mpp_watts >= 100.0:
                mppw_str = "{:.0f}".format(mpp_watts)
            elif mpp_watts >= 10.0:
                mppw_str = "{:.1f}".format(mpp_watts)
            elif mpp_watts >= 1.0:
                mppw_str = "{:.2f}".format(mpp_watts)
            elif mpp_watts >= 0.1:
                mppw_str = "{:.3f}".format(mpp_watts)
            else:
                mppw_str = "{:.4f}".format(mpp_watts)
            mpp_str = "MPP = {} W{}".format(mppw_str, mpp_volts_x_amps_str)
            if self.use_gnuplot:
                gp_mpp_str = ' ""'
                if not ii or self.label_all_mpps or self.plot_ref:
                    gp_mpp_str = ' "{}"'.format(mpp_str)
                self.gnuplot_label_point(gp_mpp_str,
                                         mpp_volts[ii], mpp_amp,
                                         1, 1,
                                         fontsize)
            else:
                self.pyplot_add_point(mpp_volts[ii], mpp_amp)
                if self.label_all_mpps and len(mpp_volts) > 1 or self.plot_ref:
                    # x_off
                    if self.mpp_watts_only:
                        max_x_off = 0.85
                        base_x_off_right = 0.05
                        base_x_off_left = 0.20
                    else:
                        max_x_off = 0.78
                        base_x_off_right = 0.05
                        base_x_off_left = 0.28
                    min_x_off = 0.01
                    inc_x_off = 0.0135
                    if mpp_volts[ii] >= max_mpp_volts * 0.70:
                        x_off = min((mpp_volts[ii]/self.plot_max_x) +
                                    base_x_off_right +
                                    (ii * inc_x_off), max_x_off)
                    else:
                        x_off = max((mpp_volts[ii]/self.plot_max_x) -
                                    base_x_off_left +
                                    (ii * inc_x_off), min_x_off)
                    # y_off
                    base_y_off = 0.72
                    inc_y_off = 0.05
                    y_off = base_y_off - (ii * inc_y_off)
                    pyplot_annotate_point(mpp_str, mpp_volts[ii], mpp_amp,
                                          x_off, y_off,
                                          fontsize, bbox, arrowprops,
                                          textcoords="axes fraction")
                elif ii == 0:
                    x_off, y_off = xytext_offset + 5, xytext_offset + 5
                    pyplot_annotate_point(mpp_str, mpp_volts[ii], mpp_amp,
                                          x_off, y_off,
                                          fontsize, bbox, arrowprops)

    # -------------------------------------------------------------------------
    def plot_and_label_voc(self, voc_volts, xytext_offset, bbox, arrowprops):
        """Method to plot and label/annotate the Voc point(s)"""
        fontsize = self.voclabel_fontsize * self.font_scale
        nn = 0
        if self.label_all_vocs:
            nn = len(voc_volts) - 1
        for ii, voc_volt in enumerate(voc_volts):
            if voc_volt >= 10.0:
                voc_str = "Voc = {:.1f} V".format(voc_volt)
            elif voc_volt >= 1.0:
                voc_str = "Voc = {:.2f} V".format(voc_volt)
            else:
                voc_str = "Voc = {:.3f} V".format(voc_volt)
            if self.use_gnuplot:
                gp_voc_str = ' ""'
                if not ii or self.label_all_vocs or self.plot_ref:
                    gp_voc_str = ' "{}"'.format(voc_str)
                    self.gnuplot_label_point(gp_voc_str,
                                             voc_volt, 0,
                                             1, 1 + ii * 1 * self.font_scale,
                                             fontsize)
            else:
                self.pyplot_add_point(voc_volt, 0)
                if not ii or self.label_all_vocs or self.plot_ref:
                    pyplot_annotate_point(voc_str, voc_volt, 0,
                                          xytext_offset + 5,
                                          (xytext_offset + 5 +
                                           ((nn - ii) * 20 *
                                            self.font_scale)),
                                          fontsize, bbox, arrowprops)

    # -------------------------------------------------------------------------
    def pyplot_add_point(self, x, y):
        """Method to add a point (Isc, Voc, MPP) to the plot
        """
        markersize = DEFAULT_MARKER_POINTSIZE * self.point_scale
        if self.point_scale < 1.0:
            markersize = DEFAULT_MARKER_POINTSIZE
        plt.plot([x], [y],
                 marker="o",
                 color="black",
                 linestyle="none",
                 markersize=markersize,
                 markeredgewidth=1,
                 clip_on=False)

    # -------------------------------------------------------------------------
    def gnuplot_label_point(self, label_str, x, y, xtext, ytext, fontsize):
        """Method to add a label (Isc, Voc, MPP) to the plot
        """
        # pylint: disable=too-many-arguments

        fontsize *= self.gp_font_scale
        output_line = ('set label at {},{}{} point pointtype {} font ",{}" '
                       'offset {},{} front\n'
                       .format(x, y, label_str, self.gp_isc_voc_mpp_pointtype,
                               fontsize, xtext, ytext))
        self.filehandle.write(output_line)

    # -------------------------------------------------------------------------
    def plot_points_and_curves(self, sd_data_point_filenames, mpp_volts):
        """Method to read the data in each data point file and use
           pyplot to plot the measured and interpolated curves
        """
        if self.use_gnuplot:
            (measured_volts,
             measured_amps,
             _,
             interp_volts,
             interp_amps,
             interp_watts) = (0, 0, 0, 0, 0, 0)  # Not used
            self.output_line = "plot "
        for curve_num, df in enumerate(sd_data_point_filenames):
            if not self.use_gnuplot:
                with open(df, "r", encoding="utf-8") as f:
                    # Read points from the file
                    (measured_volts,
                     measured_amps,
                     _,
                     interp_volts,
                     interp_amps,
                     interp_watts) = read_measured_and_interp_points(f)

            # Put measured points label at top of legend
            if not self.use_gnuplot and not curve_num and self.point_scale:
                self.get_measured_points_kwargs()
                self.add_measured_points_label()

            if self.use_gnuplot and curve_num:
                self.output_line += ", "

            # Plot interpolated curve first, so it is "under" the
            # measured points
            self.plot_interp_points(curve_num, df,
                                    sd_data_point_filenames,
                                    interp_volts, interp_amps)

            # Plot measured points and (optionally) power curve (except
            # for reference curve, which is curve_num = 0)
            if not self.plot_ref or curve_num:
                self.plot_measured_points(curve_num, df,
                                          measured_volts, measured_amps)

                # Plot power curve (except for reference curve)
                if self.plot_power and not self.use_gnuplot:
                    # Plot power curve
                    self.plot_power_curve(curve_num, interp_volts,
                                          interp_watts, mpp_volts)

        if self.use_gnuplot:
            self.output_line += "\n"
            self.filehandle.write(self.output_line)

    # -------------------------------------------------------------------------
    def get_measured_points_kwargs(self):
        """Method to fill the kwargs dict shared by the plt.plot calls for both
           the add_measured_points_label() and plot_measured_points()
           methods. The only difference is the -label arg, which is
           added to the dict by add_measured_points_label(), but not by
           plot_measured_points().
        """
        edge = "red"
        if self.line_scale == 0.0:
            # Solid dots if no interpolated curve
            face = edge
        else:
            face = "none"
        markersize = DEFAULT_MARKER_POINTSIZE * self.point_scale
        self.mp_kwargs = {"marker": "o",
                          "linestyle": "none",
                          "markersize": markersize,
                          "markeredgewidth": self.point_scale,
                          "markeredgecolor": edge,
                          "markerfacecolor": face,
                          "clip_on": False}

    # -------------------------------------------------------------------------
    def add_measured_points_label(self):
        """Method to create the legend entry for the measured points
        """
        # Add label to copy of kwargs used by plot_measured_points()
        kwargs = dict(self.mp_kwargs)
        kwargs["label"] = "Measured Points"

        # Dummy "plot" using empty arrays, just creates the label in
        # the legend
        plt.plot([], [], **kwargs)

    # -------------------------------------------------------------------------
    def plot_measured_points(self, curve_num, df,
                             measured_volts, measured_amps):
        """Method to plot the measured points"""
        if self.point_scale == 0.0:
            # Skip plotting points altogether if scale is zero
            return
        measured_name = "Measured Points"
        title_str = 'title "{}" '.format(measured_name)
        if self.use_gnuplot:
            if curve_num:
                title_str = "notitle "
            self.output_line += ('"{}" index 0 {}linecolor rgb "{}" '
                                 'pointtype {} linewidth {}'
                                 .format(df, title_str,
                                         self.gp_measured_point_color,
                                         self.gp_measured_pointtype,
                                         self.gp_measured_point_linewidth))
        else:
            # Plot without label, which was added by
            # add_measured_points_label()
            plt.plot(measured_volts, measured_amps, **self.mp_kwargs)

    # -------------------------------------------------------------------------
    def plot_interp_points(self, curve_num, df, sd_data_point_filenames,
                           interp_volts, interp_amps):
        """Method to plot the interpolated points"""
        # pylint: disable=too-many-arguments
        # pylint: disable=too-many-branches

        if self.line_scale == 0.0:
            # Skip plotting curve altogether if scale is zero
            return
        if self.names is None:
            if len(sd_data_point_filenames) > 1:
                interp_label = df
                date_time_str = DateTimeStr.extract_date_time_str(df)
                if date_time_str != "No match":
                    (date_str,
                     time_str) = DateTimeStr.xlate_date_time_str(date_time_str)
                    interp_label = "{}@{}".format(date_str, time_str)
            else:
                interp_label = "Interpolated IV Curve"
        else:
            interp_label = self.names[curve_num]
        if self.plot_ref:
            if curve_num == 0:
                # Reference curve
                color = "black"
                linestyle = "dashed"
            else:
                # Measured curve
                color = self.plot_colors[0]
                linestyle = "solid"
        else:
            color = self.plot_colors[curve_num]
            linestyle = "solid"
        if self.use_gnuplot:
            if sys.platform == "darwin":
                # On Mac @ sign is lost
                interp_label = interp_label.replace("@", " at ")
            self.output_line += ('"{}" index 1 with lines title "{}" '
                                 'linecolor rgb "{}" linewidth {} linetype {},'
                                 .format(df, interp_label,
                                         color,
                                         (self.gp_interp_linewidth *
                                          self.line_scale),
                                         self.gp_interp_linetype))
        else:
            plt.plot(interp_volts, interp_amps,
                     color=color,
                     linewidth=DEFAULT_LINEWIDTH * self.line_scale,
                     linestyle=linestyle,
                     label=interp_label)

    # -------------------------------------------------------------------------
    def plot_power_curve(self, curve_num, interp_volts, interp_watts,
                         mpp_volts):
        """Method to plot the power curve"""
        name = ""
        # Set secondary Y-axis based on first curve
        if curve_num == 0 or self.plot_ref:
            # Create a X-axis twin (same X axis, different Y axis)
            self.ax2 = self.ax1.twinx()
            # Set ax2 xlim to same as ax1
            self.ax2.set_xlim(self.ax1.get_xlim())
            #
            # Set max ax2 ylim (max_y2) so MPP coincides
            #
            # We want the ratio of the max current (max_y1) to the MPP
            # current to equal the ratio of the max power (max_y2) to the
            # MPP power:
            #
            #    max_y1      max_y2
            #   -------- = ---------
            #   mpp_amps   mpp_watts
            #
            # Solving for max_y2:
            #
            #             max_y1 * mpp_watts
            #   max_y2 = --------------------
            #                  mpp_amps
            #
            # mpp_watts / mpp_amps = mpp_volts, so:
            #
            #   max_y2 = max_y1 * mpp_volts
            #
            max_y1 = self.ax1.get_ylim()[1]
            max_y2 = max_y1 * mpp_volts[curve_num]
            self.ax2.set_ylim(0, max_y2)
            fontsize = self.axislabel_fontsize * self.font_scale
            self.ax2.set_ylabel("Power (watts)", fontsize=fontsize)
            fontsize = self.ticklabel_fontsize * self.font_scale
            for yticklabel in self.ax2.get_yticklabels():
                yticklabel.set_fontsize(fontsize)
            name = "Power Curve"
        # Plot the power curve on ax2
        self.ax2.plot(interp_volts, interp_watts,
                      color="red",
                      linewidth=(DEFAULT_LINEWIDTH * POWER_LINEWIDTH_MULT *
                                 self.line_scale),
                      linestyle="dashed",
                      label=name)
        # Set the current axes object back to ax1
        plt.sca(self.ax1)

    # -------------------------------------------------------------------------
    def set_key_font(self):
        """Method to set the font of the gnuplot key (legend)"""
        fontsize = self.legend_fontsize * self.font_scale * self.gp_font_scale
        output_line = ('set key font ",{}"\n'.format(fontsize))
        self.filehandle.write(output_line)

    # -------------------------------------------------------------------------
    def display_legend(self):
        """Method to display the plotter legend"""
        fontsize = self.legend_fontsize * self.font_scale
        if self.ax2 is None:
            # Normal case
            legend = self.ax1.legend(prop={"size": fontsize},
                                     handlelength=2.7)
        else:
            # Add legend for power curve
            h1, l1 = self.ax1.get_legend_handles_labels()
            h2, l2 = self.ax2.get_legend_handles_labels()
            legend = self.ax1.legend(h1 + h2, l1 + l2, prop={"size": fontsize},
                                     handlelength=2.7)
        # No border
        legend.get_frame().set_linewidth(0.0)

    # -------------------------------------------------------------------------
    def adjust_margins(self):
        """Method to adjust plotter margins"""
        xsize = self.plot_x_inches * self.plot_x_scale
        ysize = self.plot_y_inches * self.plot_y_scale
        margin_width = 0.2 + 0.3 * self.font_scale
        if self.plot_max_y < 0.5:
            lr_margin_add = 0.2
        elif self.plot_max_y < 5:
            lr_margin_add = 0.1
        else:
            lr_margin_add = 0.0
        left_adj = (margin_width + lr_margin_add) / xsize
        right_adj = 1.0 - (margin_width + lr_margin_add) / xsize
        top_adj = 1.0 - margin_width / ysize
        bottom_adj = margin_width / ysize
        if self.use_gnuplot:
            output_line = "set lmargin at screen {}\n".format(left_adj)
            self.filehandle.write(output_line)
            output_line = "set rmargin at screen {}\n".format(right_adj)
            self.filehandle.write(output_line)
            output_line = "set tmargin at screen {}\n".format(top_adj)
            self.filehandle.write(output_line)
            output_line = "set bmargin at screen {}\n".format(bottom_adj)
            self.filehandle.write(output_line)
        else:
            plt.subplots_adjust(left=left_adj, right=right_adj,
                                top=top_adj, bottom=bottom_adj)

    # -------------------------------------------------------------------------
    def print_to_img_file(self, sd_img_filename):
        """Method to print the plot to the image file"""
        plt.savefig(sd_img_filename, dpi=self.plot_dpi)

    # -------------------------------------------------------------------------
    def open_interactive_display(self):
        """Method to open the interactive plotter display"""
        if self.use_gnuplot:
            self.filehandle.write("set terminal wxt size 1200,800\n")
            output_line = "unset output\n"
            self.filehandle.write(output_line)
            self.filehandle.write("replot\n")
            self.filehandle.write("pause -1\n")
        else:
            plt.show()

    # -------------------------------------------------------------------------
    @staticmethod
    def close_plots():
        """Static method to close all plots. This is required on Windows
           before exiting a Tkinter GUI that has used the plotter or
           else it throws some strange errors and hangs on exit.
        """
        plt.close("all")

    # -------------------------------------------------------------------------
    def shut_down(self, lock_held=True):  # IVS1
        """Method to shut down the Raspberry Pi"""

        try:
            if not lock_held:
                self.lock.acquire()
            msg_text = "Shutting down\nnow!!"
            lcd_msg = ScrollingMessage(msg_text, self.lcd, beep=False,
                                       lock=None, exc_queue=self.exc_queue)
            lcd_msg.start()
        finally:
            time.sleep(2)
            os.system("shutdown -h now")
            time.sleep(5)
            lcd_msg.stop()
            self.reset_lcd()

    # -------------------------------------------------------------------------
    def clean_up(self, io_extender, reason_text):  # IVS1
        """Method to clean up on exit, then shut down"""

        self.logger.print_and_log("Cleaning up on exit: {}\n"
                                  .format(reason_text))

        # Turn off all relays
        turn_off_all_relays(io_extender)

        # Need user to turn off the DPST switch
        self.prompt_and_wait_for_dpst_off()

        # Display exit message on LCD
        self.lcd.clear()
        self.lcd.message("IV_Swinger exit:\n{}".format(reason_text))

        # Shut down after 10 seconds if the shutdown_on_exit property is
        # True and the exit is not due to a keyboard interrupt.
        if self.shutdown_on_exit and reason_text != "kbd interrupt":
            time.sleep(5)
            self.lcd.clear()
            self.lcd.message("Shutting down\nin 10 seconds")
            time.sleep(10)
            # Suppress shutdown if pushbutton is pressed
            if GPIO.input(self.button_gpio) == BUTTON_OFF:
                self.shut_down(lock_held=False)
        else:
            # Clean up GPIO
            GPIO.cleanup()

    # -------------------------------------------------------------------------
    def find_usb_drives(self, wait=True, display=False):  # IVS1
        """Method to find all USB drives and return the list. If the
           "wait" arg is set to True and no USB drives are found, prompt
           the user and wait until one is inserted (or time out).
        """
        def find_usb_drives_inner():
            """Local function to find all USB drives and return the list.  USB
               drives look like directories under /media.  But there could
               be directories under /media that are not USB drives.  So
               filter out any that are not mount points.  It's also possible
               that a USB drive is write-protected so filter those out too.
            """
            # Get list of directories under /media (possible USB drives)
            slash_media_dir_glob = "/media/*"
            slash_media_dirs = glob.glob(slash_media_dir_glob)

            # Filter out any that are not actually mount points or are not
            # writeable (and executable, which is necessary to add
            # subdirectories/files).
            usb_drives = []
            for slash_media_dir in slash_media_dirs:
                if (os.path.ismount(slash_media_dir) and
                        os.access(slash_media_dir, os.W_OK | os.X_OK)):
                    # Instead of using os.path.ismount and os.access, could
                    # look in /proc/mounts and check that it is "rw"

                    # Check for duplicates
                    duplicate = False
                    for usb_drive in usb_drives:
                        if os.path.samefile(usb_drive, slash_media_dir):
                            duplicate = True

                    # Add to the list if not a duplicate
                    if not duplicate:
                        usb_drives.append(slash_media_dir)

            return usb_drives

        # Find USB drives
        usb_drives = find_usb_drives_inner()

        # If there are no USB drives, print warning and loop waiting for one
        # to be inserted
        if not usb_drives and wait:
            self.logger.print_and_log("No USB drives!! Insert one "
                                      "or more USB drives now")

            start_time = time.time()

            while True:
                wait_time = int(time.time()) - int(start_time)
                time_left = 30 - wait_time
                if time_left < 0:
                    time_left = 0
                msg_text = ["No USB drives!!\nInsert one or",
                            ("more USB drives\nin next {} sec"
                             .format(time_left))]
                lcd_msg = ScrollingMessage(msg_text, self.lcd, beep=True,
                                           lock=self.lock,
                                           exc_queue=self.exc_queue)
                lcd_msg.start()

                # Sleep for a second
                time.sleep(1)

                # After 30 seconds of polling for a USB drive, time out and
                # display a message that the files will be copied to USB if
                # one is inserted later
                if wait_time > 30:
                    lcd_msg.stop()
                    msg_text = ["Proceeding\nwithout USB",
                                "Results will\nbe kept on SD",
                                "card and copied\nto USB drive",
                                "when one is\navailable"]
                    print_str = ("Proceeding without USB drive. "
                                 "Results will be kept on SD card "
                                 "and copied to USB when one is available")
                    self.logger.print_and_log(print_str)
                    lcd_msg = ScrollingMessage(msg_text, self.lcd, beep=False,
                                               lock=self.lock,
                                               exc_queue=self.exc_queue)
                    lcd_msg.start()
                    time.sleep(10)
                    lcd_msg.stop()
                    break

                # Check again
                usb_drives = find_usb_drives_inner()
                if usb_drives:
                    display = True
                    lcd_msg.stop()
                    break

                lcd_msg.stop()

        if display:
            usb_drives_str = ""
            for usb_drive in usb_drives:
                usb_drives_str += "{} ".format(usb_drive)

            msg_text = ["Found USB drive(s):\n{}".format(usb_drives_str)]
            self.logger.print_and_log("Found USB drive(s): {}"
                                      .format(usb_drives_str))
            lcd_msg = ScrollingMessage(msg_text, self.lcd, beep=False,
                                       lock=self.lock,
                                       exc_queue=self.exc_queue)
            lcd_msg.start()
            time.sleep(5)
            lcd_msg.stop()

        return usb_drives

    # -------------------------------------------------------------------------
    def create_iv_swinger_dirs(self, base_dirs, include_csv=True,
                               include_pdf=True):  # IVS1
        """Method to create the IV_Swinger directories under the
           specified base directories.  Returns the list of IV_swinger
           directories.
        """
        iv_swinger_dirs = []

        # In each of the base directories make the IV_Swinger directory
        # if it doesn't already exist.  Also make the /IV_Swinger/logs,
        # /IV_Swinger/csv and /IV_Swinger/pdf directories. Note that
        # "/IV_Swinger" is the value of the root_dir property and may be
        # overridden,
        for base_dir in base_dirs:
            sub_dirs = [os.path.join(base_dir, self.root_dir),
                        os.path.join(base_dir, self.root_dir, "logs")]
            if include_csv:  # IVS1
                sub_dirs.append(os.path.join(base_dir, self.root_dir, "csv"))
            if include_pdf:  # IVS1
                sub_dirs.append(os.path.join(base_dir, self.root_dir, "pdf"))
            for sub_dir in sub_dirs:
                if not os.path.exists(sub_dir):  # IVS1
                    try:
                        os.makedirs(sub_dir)
                    except OSError:
                        msg_text = ["Failed to make\ndirectory:",
                                    "{}".format(sub_dir)]
                        self.logger.print_and_log("Failed to make "
                                                  "directory: {}"
                                                  .format(sub_dir))
                        if self.lcd is not None:
                            lcd_msg = ScrollingMessage(
                                msg_text,
                                self.lcd,
                                beep=True,
                                lock=self.lock,
                                exc_queue=self.exc_queue)
                            lcd_msg.start()
                            time.sleep(5)
                            lcd_msg.stop()
                        continue

            iv_swinger_dirs.append(sub_dirs[0])

        return iv_swinger_dirs

    # -------------------------------------------------------------------------
    def copy_files_to_usb(self, date_time_str, sd_output_dir,
                          sd_iv_swinger_dir):  # IVS1
        """Method to copy the files from the SD card /IV_Swinger
           directory to the USB drives.  If no USB drive is found (or if
           there are errors writing to all that are), the date/time string
           is added to the file /IV_Swinger/pending_usb_copy.  If one or
           more USB drives is found this time, any files from previous runs
           that were never copied to USB (i.e. those listed in
           /IV_Swinger/pending_usb_copy) are copied now - in addition to
           the files for the current run.
        """
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-statements

        # Update tentative USB drives list
        _usb_drives = self.find_usb_drives(wait=False, display=False)

        # Check space on each drive and remove any from the list that do
        # not have at least 1 million bytes
        usb_drives = []
        for usb_drive in _usb_drives:
            free_bytes = (os.statvfs(usb_drive).f_bfree *
                          os.statvfs(usb_drive).f_bsize)
            if free_bytes > 1000000:
                usb_drives.append(usb_drive)
            else:
                msg_text = ["{}\nis NEARLY FULL!!".format(usb_drive),
                            "Results will not\nbe written to it"]
                lcd_msg = ScrollingMessage(msg_text, self.lcd,
                                           beep=True, lock=self.lock,
                                           exc_queue=self.exc_queue)
                lcd_msg.start()
                time.sleep(7)
                lcd_msg.stop()
            self.logger.print_and_log("{} has {} bytes of free space"
                                      .format(usb_drive, free_bytes))

        usb_drive_successfully_written = False

        if usb_drives:
            # Create IV_Swinger directories on the USB drives
            usb_iv_swinger_dirs = self.create_iv_swinger_dirs(usb_drives)

            # Copy the SD card directory to the directories on the USB
            # drives
            for usb_iv_swinger_dir in usb_iv_swinger_dirs:
                try:
                    # Copy the log file
                    usb_logs_dir = os.path.join(usb_iv_swinger_dir, "logs")
                    self.logger.log("copy: {} to {}"
                                    .format(PrintAndLog.log_file_name,
                                            usb_logs_dir))
                    shutil.copy(PrintAndLog.log_file_name, usb_logs_dir)

                    # Copy the output files
                    usb_output_dir = os.path.join(usb_iv_swinger_dir,
                                                  date_time_str)
                    self.logger.log("copytree: {} to {}"
                                    .format(sd_output_dir, usb_output_dir))
                    shutil.copytree(sd_output_dir, usb_output_dir)

                    # Copy the CSV and PDF files to the /csv and /pdf
                    # directories
                    for file_type in ["csv", "pdf"]:
                        file_glob = os.path.join(sd_output_dir, "*.",
                                                 file_type)
                        files = glob.glob(file_glob)
                        for f in files:
                            usb_file = os.path.join(usb_iv_swinger_dir,
                                                    file_type)
                            self.logger.log("copy: {} to {}"
                                            .format(f, usb_file))
                            shutil.copy(f, usb_file)

                    # Set success flag if we got this far without an
                    # exception for at least one USB drive
                    usb_drive_successfully_written = True

                except (IOError, OSError, shutil.Error) as e:
                    self.logger.print_and_log("({})".format(e))

            # If pending_usb_copy file exists, open it for reading and
            # step through the date_time_str values and use copytree to
            # copy the directory from SD to USB.  Then remove the file.
            filename = os.path.join(sd_iv_swinger_dir, "pending_usb_copy")
            if os.path.isfile(filename):
                try:
                    with open(filename, "r", encoding="utf-8") as f:
                        for my_date_time_str in f.read().splitlines():
                            sd_output_dir = os.path.join(sd_iv_swinger_dir,
                                                         my_date_time_str)
                            for usb_ivs_dir in usb_iv_swinger_dirs:
                                usb_output_dir = os.path.join(usb_ivs_dir,
                                                              my_date_time_str)
                                self.logger.print_and_log(
                                    "copytree: {} to {}"
                                    .format(sd_output_dir, usb_output_dir))
                                shutil.copytree(sd_output_dir, usb_output_dir)
                                for file_type in ["csv", "pdf"]:
                                    file_glob = os.path.join(sd_output_dir,
                                                             "*.", file_type)
                                    files = glob.glob(file_glob)
                                    for f in files:
                                        usb_file = os.path.join(usb_ivs_dir,
                                                                file_type)
                                        self.logger.log("copy: {} to {}"
                                                        .format(f, usb_file))
                                        shutil.copy(f, usb_file)
                    os.remove(filename)
                except (IOError, OSError, shutil.Error) as e:
                    self.logger.print_and_log("({})".format(e))

        if not usb_drive_successfully_written:
            # If no USB drives, append date_time_str to pending_usb_copy
            # file in SD IV_Swinger directory
            filename = os.path.join(sd_iv_swinger_dir, "pending_usb_copy")
            try:
                with open(filename, "a", encoding="utf-8") as f:
                    f.write("{}\n".format(date_time_str))
            except (IOError, OSError) as e:
                self.logger.print_and_log("({})".format(e))

    # -------------------------------------------------------------------------
    def check_for_thread_errors(self):  # IVS1
        """Method to check the exception message queue to see if a
           thread has died, in which case the main thread must exit too.
        """
        try:
            thread_exc = self.exc_queue.get(block=False)
        except queue.Empty:
            pass
        else:
            self.logger.print_and_log("THREAD error: {}".format(thread_exc))
            sys.exit(-1)

    # -------------------------------------------------------------------------
    def run_meat(self, io_extender):  # IVS1
        """Method containing most of run(), run with exception
           handling after io_extender object creation
        """
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-statements

        # Create ADS1115 ADC instance
        adc = Adafruit_ADS1x15.ADS1x15(ic=ADS1115)

        # Turn off all relays
        turn_off_all_relays(io_extender)

        # Find USB drives
        self.find_usb_drives(wait=True, display=False)

        msg_text = ["Turn switch ON",
                    "to begin IV\ncurve tracing"]

        while True:
            # Check exception message queue for thread errors
            self.check_for_thread_errors()

            # Block until lock is acquired, then release it immediately
            with self.lock:
                pass

            # Check the DPST switch state.  If it is ON, ask the user to
            # turn it off and poll it until that happens.
            self.prompt_and_wait_for_dpst_off()

            # Activate each relay once by itself. This is a workaround
            # for a problem of unknown cause where some relays
            # especially near the end of the chain) sometimes fail to
            # stay in the activated position.  This seems to help.
            # prime_relays(io_extender);

            # Continually measure Voc while waiting for the DPST switch
            # to be turned ON
            (voc_amps,
             voc_volts,
             voc_ohms,
             voc_watts) = self.measure_voc(adc, msg_text)

            # Attempt to acquire lock
            got_lock = self.lock.acquire(0)  # non-blocking

            # If the lock is busy (i.e. held by the pushbutton
            # callback), go back the beginning of the main loop and wait
            # until it is free
            if not got_lock:
                continue

            self.lcd.clear()
            self.lcd.message("Voc: {:.2f} V".format(voc_volts))
            time.sleep(0.5)

            if voc_volts < 0.0:
                msg_text = ("Voc is negative!!\n"
                            "DISCONNECT PV *NOW* TO AVOID DAMAGE!!")
                self.logger.print_and_log(msg_text)
                lcd_msg = ScrollingMessage(msg_text, self.lcd,
                                           beep=False, lock=None,
                                           exc_queue=self.exc_queue)
                lcd_msg.start()
                while voc_volts < 0.0:
                    voc_volts = self.read_voc(adc)
                    self.beeper.generate_beep()
                lcd_msg.stop()
                self.lock.release()
                msg_text = ["Turn switch ON",
                            "to begin IV\ncurve tracing"]
                continue
            if voc_volts == 0.0:
                msg_text = "Voc is 0 volts!!\nConnect PV now"
                self.logger.print_and_log(msg_text)
                warning_thread = SoundWarning(on_time=0.1, off_time=10)
                warning_thread.start()
                while voc_volts == 0.0:
                    lcd_msg = ScrollingMessage(msg_text, self.lcd, beep=False,
                                               lock=None,
                                               exc_queue=self.exc_queue)
                    lcd_msg.start()
                    time.sleep(1.0)
                    lcd_msg.stop()
                    # Release the lock to give the pushbutton callback
                    # thread a chance to grab it
                    self.lock.release()
                    time.sleep(0.01)  # yield to callback thread
                    self.check_for_thread_errors()
                    self.lock.acquire()
                    voc_volts = self.read_voc(adc)
                warning_thread.stop()
                self.lock.release()
                msg_text = ["Turn switch ON",
                            "to begin IV\ncurve tracing"]
                continue

            # Form the date/time string used for the directory
            # names.  Note that the date/time is when the DPST
            # switch is turned on.
            date_time_str = DateTimeStr.get_date_time_str()

            # Swing out the IV curve!
            data_points = self.swing_iv_curve(io_extender, adc, voc_volts)

            # If data_points is an empty list it means the load=NONE
            # current measurement was zero. This could be because no
            # light was falling on the panel. Display a message on
            # the LCD and go back to the beginning of the loop.
            if not data_points:
                msg_text = "Isc is 0 amps\nTry again"
                self.logger.print_and_log(msg_text)
                warning_thread = SoundWarning(on_time=0.1, off_time=0.2)
                warning_thread.start()
                lcd_msg = ScrollingMessage(msg_text, self.lcd,
                                           beep=False, lock=None,
                                           exc_queue=self.exc_queue)
                lcd_msg.start()
                time.sleep(3)
                lcd_msg.stop()
                warning_thread.stop()
                self.lock.release()
                msg_text = ["Turn switch ON",
                            "to begin IV\ncurve tracing"]
                continue

            # Release lock
            self.lock.release()

            # Ask user to turn off the DPST switch
            self.prompt_and_wait_for_dpst_off()

            # Turn off all relays
            turn_off_all_relays(io_extender)

            # Clean up LCD after relay switching
            self.reset_lcd()

            # Find the measured point number with the highest power
            max_watt_point_number = (
                IV_Swinger.get_max_watt_point_number(data_points))

            # Extrapolate Isc value and store in first element of
            # data_points list (overwrite placeholder)
            data_points[0] = self.extrapolate_isc(data_points,
                                                  max_watt_point_number)
            isc_amps = data_points[0][AMPS_INDEX]

            # Add Voc values to the end of the data point list
            voc_data_point = (voc_amps, voc_volts, voc_ohms, voc_watts)
            data_points.append(voc_data_point)

            # Create the SD card output directory
            sd_iv_swinger_dirs = self.create_iv_swinger_dirs([""])
            sd_iv_swinger_dir = sd_iv_swinger_dirs[0]  # only one
            sd_output_dir = os.path.join(sd_iv_swinger_dir,
                                         date_time_str)
            os.makedirs(sd_output_dir)

            # Create the leaf file names
            csv_dp_leaf_name = ("data_points_{}.csv"
                                .format(date_time_str))
            gp_command_leaf_name = ("gp_command_file_{}"
                                    .format(date_time_str))
            plt_dp_leaf_name = ("plt_data_points_{}"
                                .format(date_time_str))
            plt_img_leaf_name = ("plt_data_points_{}.pdf"
                                 .format(date_time_str))

            # Get the full-path names of the SD card output files
            sd_csv_data_point_filename = os.path.join(sd_output_dir,
                                                      csv_dp_leaf_name)
            sd_gp_command_filename = os.path.join(sd_output_dir,
                                                  gp_command_leaf_name)
            sd_plt_data_point_filename = os.path.join(sd_output_dir,
                                                      plt_dp_leaf_name)
            sd_plt_img_filename = os.path.join(sd_output_dir,
                                               plt_img_leaf_name)

            # Write the CSV data points to the SD card file
            write_csv_data_points_to_file(sd_csv_data_point_filename,
                                          data_points)

            # Write the plotter data points to the SD card files
            write_plt_data_points_to_file(sd_plt_data_point_filename,
                                          data_points,
                                          new_data_set=False)

            # Create an interpolator object with the data_points
            interpolator = Interpolator(data_points)

            # Get the interpolated data set and MPP
            if self.use_spline_interpolation:
                interp_points = interpolator.spline_interpolated_curve
                interpolated_mpp = interpolator.spline_interpolated_mpp
            else:
                interp_points = interpolator.linear_interpolated_curve
                interpolated_mpp = interpolator.linear_interpolated_mpp

            # Add the interpolated data set to the plotter data
            # point file
            write_plt_data_points_to_file(sd_plt_data_point_filename,
                                          interp_points,
                                          new_data_set=True)

            # Extract the MPP values
            mpp_amps = interpolated_mpp[AMPS_INDEX]
            mpp_volts = interpolated_mpp[VOLTS_INDEX]
            mpp_ohms = interpolated_mpp[OHMS_INDEX]
            mpp_watts = interpolated_mpp[WATTS_INDEX]

            # Print MPP info
            self.logger.print_and_log("==========================")
            print_str = ("Maximum power point (MPP): "
                         "Amps: {:.6f}   Volts: {:.6f}   "
                         "Ohms: {:.6f}   Watts: {:.6f}"
                         .format(mpp_amps, mpp_volts,
                                 mpp_ohms, mpp_watts))
            self.logger.print_and_log(print_str)

            # Display max power on LCD
            self.check_for_thread_errors()
            with self.lock:
                self.lcd.clear()
                self.lcd.message(" Max Power:\n     {:.2f} W"
                                 .format(mpp_watts))
                time.sleep(2)

            if voc_volts != 0.0:
                # Plot with plotter (gnuplot or pyplot)
                self.plot_with_plotter(sd_gp_command_filename
                                       [sd_plt_data_point_filename],
                                       sd_plt_img_filename,
                                       [isc_amps],
                                       [voc_volts],
                                       [mpp_amps],
                                       [mpp_volts],
                                       self.use_spline_interpolation)

            # Copy CSV and PDF files to /IV_Swinger/csv and
            # /IV_Swinger/pdf
            for file_type in ["csv", "pdf"]:
                file_glob = os.path.join(sd_output_dir, "*.", file_type)
                files = glob.glob(file_glob)
                for f in files:
                    shutil.copy(f, os.path.join(sd_iv_swinger_dir,
                                                file_type))

            # Copy files to USB
            self.copy_files_to_usb(date_time_str, sd_output_dir,
                                   sd_iv_swinger_dir)

            # Display message
            outdir_msg = "Output folder:\n{}".format(date_time_str)
            self.logger.print_and_log(outdir_msg)
            self.logger.print_and_log("")
            lcd_msg = ScrollingMessage(outdir_msg, self.lcd, beep=False,
                                       lock=self.lock,
                                       exc_queue=self.exc_queue)
            lcd_msg.start()
            time.sleep(3)
            lcd_msg.stop()
            msg_text = [outdir_msg, "Turn switch ON\nto start again"]

    # -------------------------------------------------------------------------
    def init_other_class_variables(self):  # IVS1
        """Method that initializes class variables in the supporting
           classes based on this class' property values. This method, or an
           equivalent, must be run before the PrintAndLog,
           ScrollingMessage, and BeepGenerator classes are instantiated.
        """

        # Init PrintAndLog class variable(s) from properties
        date_time_str = DateTimeStr.get_date_time_str()
        PrintAndLog.log_file_name = os.path.join(self.logs_dir,
                                                 "log_{}"
                                                 .format(date_time_str))

        # Init ScrollingMessage class variable(s) from properties
        ScrollingMessage.lcd_lines = self.lcd_lines
        ScrollingMessage.lcd_disp_chars_per_line = self.lcd_disp_chars_per_line
        ScrollingMessage.lcd_mem_chars_per_line = self.lcd_mem_chars_per_line
        ScrollingMessage.lcd_chars_per_scroll = self.lcd_chars_per_scroll
        ScrollingMessage.lcd_scroll_delay = self.lcd_scroll_delay

        # Init BeepGenerator class variable(s) from properties
        BeepGenerator.buzzer_gpio = self.buzzer_gpio

    # -------------------------------------------------------------------------
    def run(self):  # IVS1
        """Top-level method to run the IV Swinger"""

        # Init class variables in supporting classes
        self.init_other_class_variables()

        # Create the logger, beeper, lock, and lcd objects
        self.logger = PrintAndLog()
        self.beeper = BeepGenerator()
        self.lock = threading.Lock()
        self.lcd = Adafruit_CharLCD.Adafruit_CharLCD()

        # Set up GPIO pins and reset the LCD
        self.set_up_gpio()
        self.reset_lcd()

        # Create logs directory
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)

        # Print welcome message
        msg_text = "Welcome to\n     IV Swinger!"
        self.logger.print_and_log(msg_text)
        with self.lock:
            self.lcd.message(msg_text)
        time.sleep(3)

        # Create MCP23017 I/O extender instance and set all pins as
        # outputs
        io_extender = (
            Adafruit_MCP230xx.Adafruit_MCP230XX(self.mcp23017_i2c_addr,
                                                MCP23017_PIN_COUNT))
        for pin in range(MCP23017_PIN_COUNT):
            io_extender.config(pin, io_extender.OUTPUT)

        # Run the rest with all exceptions causing a call to the
        # clean_up method
        try:
            self.run_meat(io_extender)
        except SystemExit:
            # explicit calls to exit() - which print their own explanation
            self.clean_up(io_extender, "explicit exit()")
        except KeyboardInterrupt:
            # Ctrl-C
            self.logger.print_and_log("Keyboard interrupt - exiting")
            self.clean_up(io_extender, "kbd interrupt")
        except:
            # Everything else
            self.logger.print_and_log("Unexpected error: {}"
                                      .format(sys.exc_info()[0]))
            self.logger.print_and_log(traceback.format_exc())
            self.clean_up(io_extender, str(sys.exc_info()[0]))
            raise


############
#   Main   #
############
def main():  # IVS1
    """Main function"""
    ivs = IV_Swinger()
    # Override default property values
    ivs.vdiv_r1 = 178900.0  # tweaked based on DMM measurement
    ivs.vdiv_r2 = 8200.0    # tweaked based on DMM measurement
    ivs.vdiv_r3 = 5595.0    # tweaked based on DMM measurement
    ivs.amm_op_amp_rf = 82100.0  # tweaked based on DMM measurement
    ivs.amm_op_amp_rg = 1499.0   # tweaked based on DMM measurement
    ivs.run()


# Boilerplate main() call
if __name__ == "__main__":
    main()  # IVS1
