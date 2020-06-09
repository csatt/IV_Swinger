#!/usr/bin/env python
"""IV Swinger 2 simulation module"""
# pylint: disable=too-many-lines
#
###############################################################################
#
# IV_Swinger2_sim.py: IV Swinger 2 simulation module
#
# Copyright (C) 2020  Chris Satterlee
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
# Current versions of the licensing files, documentation, hardware
# design files, and software can be found at:
#
#    https://github.com/csatt/IV_Swinger
#
###############################################################################
#
# This file contains the Python code that implements the IV Swinger 2
# simulator. Its primary purpose is to facilitate choosing component values
# for scaled versions of the IV Swinger 2 hardware. It generates a simulated
# IV curve based on specified values for the Isc and Voc as well as the values
# of the resistors and capacitors used in the hardware. This makes it very
# easy to visualize the effects of different component values on the
# resolution and range. It also calculates the time that it takes to swing the
# curve and to drain the load capacitors. Component ratings are validated
# against the actual voltage, current and power that they will be required to
# handle.
#
# The simulated IV curve is generic from the following equation:
#
#     I = Isc - A*(exp(B*V)-1)
#
# This equation does not account for series or parallel resistance, and the A
# and B coefficients are chosen such that the MPP current and voltage are at a
# typical ratio of the Isc and Voc, respectively. This results in a fairly
# representative curve that should be adequate to predict the resolution and
# other characteristics of real IV curves with the given Isc and Voc. Of
# course, the shape of the real IV curves will differ depending on actual
# series and parallel resistances, temperature, etc.
#
# The simulator also supports the automated choice of optimal components for a
# given maximum Isc and Voc. The user can then test these component values
# against smaller Isc and Voc values.
#
# This module may be used standalone, or it may be imported.
#
# Most of this module consists of the following classes:
#
#     IV_Swinger2_sim
#     SimulatorDialog
#     SimulatorHelpDialog
#
# The IV_Swinger2_sim class has properties for all of the configurable inputs
# (Isc, Voc, component values, etc). Its simulate() method uses these to
# generate the simulated IV curve in the form of ADC values, i.e. the actual
# "points" that the hardware would measure. Its run() method calls the
# simulate() method and then plots its IV curve. Like a real run, the results
# are saved in a run directory. This includes a configuration file. This makes
# it possible to view the results later with the Results Wizard.
#
# The SimulatorDialog class is the Tkinter/ttk GUI interface to the
# IV_Swinger2_sim class. It is designed so that it may be run as the child of
# any ttk.Frame object (namely a GraphicalUserInterface object from
# IV_Swinger2_gui.py, but not necessarily).
#
# There is also a main() function that is used when the module is run
# standalone. The main() function creates a SimulatorDialog object with a
# basic ttk.Frame object as its parent and runs it.
#
import os
import re
import ttk
import Tkinter as tk
import tkMessageBox as tkmsg
from ScrolledText import ScrolledText as ScrolledText
from Tkconstants import E, W, BOTH, CENTER
import numpy as np
import IV_Swinger2

#################
#   Constants   #
#################
# Default property values (can be overridden)
SIM_ISC_DEFAULT = 9.0
SIM_VOC_DEFAULT = 36.0
B_COEFF_PER_VOC_DEFAULT = 10.0
R1_R2_RF_RG_WATTAGE_DEFAULT = 0.25
LOAD_CAP_UF_DEFAULT = 1000.0  # Single load cap
LOAD_CAP_V_DEFAULT = 100.0  # Max rated voltage
LOAD_CAP_ESR_OHMS_DEFAULT = 0.133  # Single load cap
LOAD_CAP_HEIGHT_MM_DEFAULT = 36.5
LOAD_CAP_MFG_PN_DEFAULT = "108CKS100MRY"
NUM_LOAD_CAPS_DEFAULT = 2
SHUNT_WATTAGE_DEFAULT = 3.0
SHUNT_MFG_PN_DEFAULT = "LVR035L000FE70"
RB_OHMS_DEFAULT = 47.0
RB_WATTAGE_DEFAULT = 5.0
RB_MFG_PN_DEFAULT = "AC05000004709JAC00"
RELAY_TYPE_DEFAULT = "SSR"
EMR_MAX_VOLTS_DEFAULT = 60.0  # 2x spec
SSR_MAX_VOLTS_DEFAULT = 100.0  # Actual from spec
EMR_MAX_AMPS_DEFAULT = 10.0  # Actual from spec (sort of)
SSR_MAX_AMPS_DEFAULT = 30.0  # Assume < 70 ms (from spec)
DONE_CH1_ADC_DEFAULT = 20  # Hardcoded in Arduino sketch
WIRE_OHMS_DEFAULT = 0.010  # Guesstimate of SC path wire resistance
EMR_OHMS_DEFAULT = 0.100  # From Songle spec
SSR_OHMS_DEFAULT = 0.070  # 2x 34 mohms
US_PER_POINT_DEFAULT = 65.0  # Measured value at 2 MHz SPI clk
NUM_SYNTH_POINTS_DEFAULT = 100000
OPT_PCT_HEADROOM_DEFAULT = 30.0
CAP_VOLTAGE_DERATE_PCT_DEFAULT = 80.0
MAX_VDIV_CURRENT_DEFAULT = 0.004
OP_AMP_MAX_DRIVE_CURRENT_DEFAULT = 0.080
OP_AMP_MAX_INPUT_CURRENT_DEFAULT = 0.000000075
TARGET_AMM_OP_AMP_GAIN_DEFAULT = 76.0
TARGET_MAX_SWING_US_DEFAULT = 1000000.0
# Derived
LOAD_CAPS_UF_DEFAULT = LOAD_CAP_UF_DEFAULT * NUM_LOAD_CAPS_DEFAULT
TARGET_BLEED_RC_US_DEFAULT = LOAD_CAPS_UF_DEFAULT * RB_OHMS_DEFAULT

# Other constants (cannot be overridden)
ZERO_OHMS = 0.0001  # Used to prevent divide-by-zero
QTR_WATT_RESISTORS = [ZERO_OHMS,
                      47.0, 56.0, 68.0, 75.0,
                      82.0, 100.0, 120.0, 150.0,
                      180.0, 220.0, 270.0, 330.0,
                      390.0, 470.0, 510.0, 680.0,
                      820.0, 1000.0, 1500.0, 2200.0,
                      3300.0, 3900.0, 4700.0, 5600.0,
                      6800.0, 7500.0, 8200.0, 10000.0,
                      15000.0, 22000.0, 33000.0, 39000.0,
                      47000.0, 56000.0, 68000.0, 75000.0,
                      82000.0, 100000.0, 150000.0, 180000.0]
# Shunt resistors
#   Resistance (ohms), power (W), Mfg PN
SHUNT_RESISTORS = [(0.005, 3.0, "LVR035L000FE70"),
                   (0.010, 3.0, "LVR03R0100FE70"),
                   (0.020, 3.0, "LVR03R0200FE70"),
                   (0.040, 3.0, "13FR040E"),
                   (0.080, 3.0, "LVR03R0800FE70"),
                   (0.100, 3.0, "LVR03R1000FE70"),
                   (0.150, 3.0, "LVR03R1500FE70"),
                   (0.330, 3.0, "UB3C-0R33F1"),
                   (0.500, 3.0, "UB3C-0R5F1"),
                   (1.000, 3.0, "UB3C-1RF1")]
# Load capacitors
#   Capacitance (uF), voltage, ESR, height (mm), Mfg PN
#
# This list must be ordered by increasing voltage (which should also be
# by decreasing capacitance.)
LOAD_CAPACITORS = [(22000.0, 10.0, "Unknown", 37.5, "EEU-HD1A223"),
                   (15000.0, 16.0, "Unknown", 37.0, "16PX15000MEFC18X35.5"),
                   (10000.0, 25.0, "Unknown", 37.0, "UBY1E103MHL"),
                   (6800.0, 35.0, "Unknown", 37.5, "EEU-HD1V682"),
                   (3300.0, 50.0, "Unknown", 37.0, "UVZ1H332MHD"),
                   (2200.0, 63.0, "Unknown", 37.0, "UVZ1J222MHD"),
                   (1500.0, 80.0, "Unknown", 37.0, "EKZN800ELL152MMP1S"),
                   (1000.0, 100.0, 0.133, 36.5, "108CKS100MRY"),
                   (680.0, 160.0, "Unknown", 47.5, "UCY2C681MHD")]
# Bleed resistors
#   Resistance (ohms), power (W), Mfg PN
BLEED_RESISTORS = [(2.0, 5.0, "AC05000002008JAC00"),
                   (3.0, 5.0, "AC05000003008JAC00"),
                   (4.7, 5.0, "AC05000004708JAC00"),
                   (7.5, 5.0, "AC05000007508JAC00"),
                   (15.0, 5.0, "AC05000001509JAC00"),
                   (22.0, 5.0, "AC05000002209JAC00"),
                   (30.0, 5.0, "AC05000003009JAC00"),
                   (47.0, 5.0, "AC05000004709JAC00"),
                   (68.0, 10.0, "SQPW1068RJ")]

# Simulator GUI
SLIDER_LENGTH = 200
MFG_PN_ENTRY_WIDTH = 20

# From IV_Swinger2
INFINITE_VAL = IV_Swinger2.INFINITE_VAL
ADC_MAX = IV_Swinger2.ADC_MAX
APP_NAME = IV_Swinger2.APP_NAME
R1_DEFAULT = IV_Swinger2.R1_DEFAULT
R2_DEFAULT = IV_Swinger2.R2_DEFAULT
RF_DEFAULT = IV_Swinger2.RF_DEFAULT
RG_DEFAULT = IV_Swinger2.RG_DEFAULT
SHUNT_DEFAULT = IV_Swinger2.SHUNT_DEFAULT
RC_SUCCESS = IV_Swinger2.RC_SUCCESS
RC_FAILURE = IV_Swinger2.RC_FAILURE


########################
#   Global functions   #
########################
def index_from_ohms(lookup_ohms):
    """Function to look up the index of a given resistance in
       QTR_WATT_RESISTORS. If the exact resistance is not found, the
       index of the one that is closest (percentage-wise) is
       returned.
    """
    if lookup_ohms < 100.0:
        return 0
    least_err = INFINITE_VAL
    for index, ohms in enumerate(QTR_WATT_RESISTORS):
        if lookup_ohms > ohms:
            err = (lookup_ohms / ohms) - 1.0
        else:
            err = (ohms / lookup_ohms) - 1.0
        if err < least_err:
            least_err = err
            best_index = index
    return best_index


def shunt_index_from_ohms(lookup_ohms):
    """Function to look up the index of a given resistance in
       SHUNT_RESISTORS. If the exact resistance is not found, the
       index of the one that is closest (percentage-wise) is
       returned.
    """
    if lookup_ohms < SHUNT_RESISTORS[0][0]:
        return 0
    least_err = INFINITE_VAL
    for index, (ohms, _, _) in enumerate(SHUNT_RESISTORS):
        if lookup_ohms > ohms:
            err = (lookup_ohms / ohms) - 1.0
        else:
            err = (ohms / lookup_ohms) - 1.0
        if err < least_err:
            least_err = err
            best_index = index
    return best_index


def load_cap_index_from_uf(lookup_uf):
    """Function to look up the index of a given resistance in
       LOAD_CAPACITORS. If the exact capacitance is not found, the
       index of the one that is closest (percentage-wise) is
       returned.
    """
    if lookup_uf < LOAD_CAPACITORS[-1][0]:
        return 0
    least_err = INFINITE_VAL
    for index, (cap_uf, _, _, _, _) in enumerate(LOAD_CAPACITORS):
        if lookup_uf > cap_uf:
            err = (lookup_uf / cap_uf) - 1.0
        else:
            err = (cap_uf / lookup_uf) - 1.0
        if err < least_err:
            least_err = err
            best_index = index
    return best_index


def rb_index_from_ohms(lookup_ohms):
    """Function to look up the index of a given resistance in
       BLEED_RESISTORS. If the exact resistance is not found, the
       index of the one that is closest (percentage-wise) is
       returned.
    """
    if lookup_ohms < BLEED_RESISTORS[0][0]:
        return 0
    least_err = INFINITE_VAL
    for index, (ohms, _, _) in enumerate(BLEED_RESISTORS):
        if lookup_ohms > ohms:
            err = (lookup_ohms / ohms) - 1.0
        else:
            err = (ohms / lookup_ohms) - 1.0
        if err < least_err:
            least_err = err
            best_index = index
    return best_index


def sigfigs(number, figs):
    """Function to convert a numerical value to the given number of
       significant figures and return that as a string
    """
    return "{}".format(float(("{:." + str(figs) + "g}").format(number)))


def shorten_value(value):
    """Function to convert value to k if it is >= 1k. If it is an integral
       number of k, return the integer value, otherwise leave it
       float. Similar for values less than 1k.
    """
    if value >= 1000.0:
        k_value = value / 1000.0
        if k_value == int(k_value):
            return "{}k".format(int(k_value))
        return "{}k".format(k_value)
    else:
        if value == int(value):
            return "{}".format(int(value))
        return "{}".format(value)


def selectall(event):
    """Global function to select all text in a Text or ScrolledText
       widget
    """
    event.widget.tag_add("sel", "1.0", "end")


def get_dialog_width_and_height(dialog):
    """Global function to parse the width and height of a dialog from its
       current geometry
    """
    m = re.match(r"(\d+)x(\d+)", dialog.geometry())
    width = int(m.group(1))
    height = int(m.group(2))
    return width, height


def pseudo_dialog_resize_disable(dialog):
    """Function to effectively disable resizing by setting the minimimum and
       maximum size to the current values. This is a hack that is part
       of the fix for Issue #101.
    """
    dialog.update_idletasks()
    width, height = get_dialog_width_and_height(dialog)
    dialog.minsize(width, height)
    dialog.maxsize(width, height)


def set_dialog_geometry(dialog, min_height=None, max_height=None):
    """Function to set the dialog geometry if the master doesn't have a
       set_dialog_geometry method. Place the dialog at the top of the
       screen, in the middle, on top of other windows.
    """
    dialog.update_idletasks()
    width, _ = get_dialog_width_and_height(dialog)
    if min_height is not None:
        if max_height is None:
            max_height = dialog.winfo_height()
        dialog.minsize(width, min_height)
        dialog.maxsize(width, max_height)
        dialog.geometry("{}x{}+{}+5".format(width, min_height,
                                            (dialog.winfo_screenwidth()/2 -
                                             width/2)))
    else:
        dialog.geometry("+{}+5".format(dialog.winfo_screenwidth()/2 -
                                       width/2))
    dialog.lift()
    dialog.attributes("-topmost", True)
    dialog.after_idle(dialog.attributes, "-topmost", False)
    dialog.update_idletasks()


#################
#   Classes     #
#################

class IV_Swinger2_sim(IV_Swinger2.IV_Swinger2):
    """IV_Swinger2 derived class extended for simulation
    """
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods

    def __init__(self, app_data_dir=None):
        IV_Swinger2.IV_Swinger2.__init__(self)
        # Property variables
        self._sim_isc = SIM_ISC_DEFAULT
        self._sim_voc = SIM_VOC_DEFAULT
        self._b_coeff_per_voc = B_COEFF_PER_VOC_DEFAULT
        self._load_cap_uf = LOAD_CAP_UF_DEFAULT
        self._load_cap_v = LOAD_CAP_V_DEFAULT
        self._load_cap_esr = LOAD_CAP_ESR_OHMS_DEFAULT
        self._load_cap_height_mm = LOAD_CAP_HEIGHT_MM_DEFAULT
        self._load_cap_mfg_pn = LOAD_CAP_MFG_PN_DEFAULT
        self._num_load_caps = NUM_LOAD_CAPS_DEFAULT
        self._shunt_wattage = SHUNT_WATTAGE_DEFAULT
        self._shunt_mfg_pn = SHUNT_MFG_PN_DEFAULT
        self._rb_ohms = RB_OHMS_DEFAULT
        self._rb_wattage = RB_WATTAGE_DEFAULT
        self._rb_mfg_pn = RB_MFG_PN_DEFAULT
        self._relay_type = RELAY_TYPE_DEFAULT
        self._emr_max_volts = EMR_MAX_VOLTS_DEFAULT
        self._ssr_max_volts = SSR_MAX_VOLTS_DEFAULT
        self._emr_max_amps = EMR_MAX_AMPS_DEFAULT
        self._ssr_max_amps = SSR_MAX_AMPS_DEFAULT
        self._done_ch1_adc = DONE_CH1_ADC_DEFAULT
        self._wire_ohms = WIRE_OHMS_DEFAULT
        self._emr_ohms = EMR_OHMS_DEFAULT
        self._ssr_ohms = SSR_OHMS_DEFAULT
        self._us_per_point = US_PER_POINT_DEFAULT
        self._num_synth_points = NUM_SYNTH_POINTS_DEFAULT
        self._opt_pct_headroom = OPT_PCT_HEADROOM_DEFAULT
        self._cap_voltage_derate_pct = CAP_VOLTAGE_DERATE_PCT_DEFAULT
        self._max_vdiv_current = MAX_VDIV_CURRENT_DEFAULT
        self._op_amp_max_drive_current = OP_AMP_MAX_DRIVE_CURRENT_DEFAULT
        self._op_amp_max_input_current = OP_AMP_MAX_INPUT_CURRENT_DEFAULT
        self._target_amm_op_amp_gain = TARGET_AMM_OP_AMP_GAIN_DEFAULT
        self._target_max_swing_us = TARGET_MAX_SWING_US_DEFAULT
        self._target_bleed_rc_us = TARGET_BLEED_RC_US_DEFAULT
        self.adc_pairs = []
        self.swing_time_us = 0
        self.pts_discarded = 0
        self.bleed_pct = 0.0
        self.unbled_volts = 0.0
        self.results_text = ""
        # Create an empty Configuration object
        self.config = IV_Swinger2.Configuration(ivs2=self)
        # Capture a snapshot of the current config
        self.config.get_snapshot()
        # Set the image dimension property from the snapshot
        self.x_pixels = self.config.cfg_snapshot.getint("General", "x pixels")

    # ---------------------------------
    @property
    def sim_isc(self):
        """Simulated Isc
        """
        return self._sim_isc

    @sim_isc.setter
    def sim_isc(self, value):
        self._sim_isc = value

    # ---------------------------------
    @property
    def sim_voc(self):
        """Simulated Voc
        """
        return self._sim_voc

    @sim_voc.setter
    def sim_voc(self, value):
        self._sim_voc = value

    # ---------------------------------
    @property
    def b_coeff_per_voc(self):
        """Value of the generic IV curve equation's B coefficient per volt
           of Voc. A higher value results in a higher voltage at the MPP and
           vice-versa.
        """
        return self._b_coeff_per_voc

    @b_coeff_per_voc.setter
    def b_coeff_per_voc(self, value):
        self._b_coeff_per_voc = value

    # ---------------------------------
    @property
    def load_cap_uf(self):
        """Capacitance of one (of the two) load capacitors
        """
        return self._load_cap_uf

    @load_cap_uf.setter
    def load_cap_uf(self, value):
        self._load_cap_uf = value

    # ---------------------------------
    @property
    def load_cap_v(self):
        """Voltage rating of the load capacitors
        """
        return self._load_cap_v

    @load_cap_v.setter
    def load_cap_v(self, value):
        self._load_cap_v = value

    # ----------------------------------
    @property
    def load_cap_esr(self):
        """Equivalent series resistance of one (of the two) the load capacitors
        """
        if self._load_cap_esr == "Unknown":
            # Super rough estimate - just assume that ESR is inversely
            # proportional to capacitance
            estimated_esr = ((LOAD_CAP_UF_DEFAULT / self.load_cap_uf) *
                             LOAD_CAP_ESR_OHMS_DEFAULT)
            return estimated_esr
        return self._load_cap_esr

    @load_cap_esr.setter
    def load_cap_esr(self, value):
        self._load_cap_esr = value

    # ----------------------------------
    @property
    def load_cap_height_mm(self):
        """Height (in mm) of load caps
        """
        return self._load_cap_height_mm

    @load_cap_height_mm.setter
    def load_cap_height_mm(self, value):
        self._load_cap_height_mm = value

    # ----------------------------------
    @property
    def load_cap_mfg_pn(self):
        """Manufacturer part number of load capacitors
        """
        return self._load_cap_mfg_pn

    @load_cap_mfg_pn.setter
    def load_cap_mfg_pn(self, value):
        self._load_cap_mfg_pn = value

    # ---------------------------------
    @property
    def num_load_caps(self):
        """Number of parallel load capacitors
        """
        return self._num_load_caps

    @num_load_caps.setter
    def num_load_caps(self, value):
        self._num_load_caps = value

    # ---------------------------------
    @property
    def shunt_wattage(self):
        """Rated power in watts of shunt resistor
        """
        return self._shunt_wattage

    @shunt_wattage.setter
    def shunt_wattage(self, value):
        self._shunt_wattage = value

    # ---------------------------------
    @property
    def shunt_mfg_pn(self):
        """Manufacturer part number of shunt resistor
        """
        return self._shunt_mfg_pn

    @shunt_mfg_pn.setter
    def shunt_mfg_pn(self, value):
        self._shunt_mfg_pn = value

    # ---------------------------------
    @property
    def rb_ohms(self):
        """Resistance of the bleed resistor
        """
        return self._rb_ohms

    @rb_ohms.setter
    def rb_ohms(self, value):
        self._rb_ohms = value

    # ---------------------------------
    @property
    def rb_wattage(self):
        """Power rating of the bleed resistor
        """
        return self._rb_wattage

    @rb_wattage.setter
    def rb_wattage(self, value):
        self._rb_wattage = value

    # ---------------------------------
    @property
    def rb_mfg_pn(self):
        """Manufacturer part number of the bleed resistor
        """
        return self._rb_mfg_pn

    @rb_mfg_pn.setter
    def rb_mfg_pn(self, value):
        self._rb_mfg_pn = value

    # ---------------------------------
    @property
    def relay_type(self):
        """Relay type used (EMR or SSR)
        """
        return self._relay_type

    @relay_type.setter
    def relay_type(self, value):
        if value not in set(["EMR", "SSR"]):
            raise ValueError("relay_type must be EMR or SSR")
        self._relay_type = value

    # ---------------------------------
    @property
    def emr_max_volts(self):
        """Max voltage allowed across EMR
        """
        return self._emr_max_volts

    @emr_max_volts.setter
    def emr_max_volts(self, value):
        self._emr_max_volts = value

    # ---------------------------------
    @property
    def ssr_max_volts(self):
        """Max voltage allowed across SSR
        """
        return self._ssr_max_volts

    @ssr_max_volts.setter
    def ssr_max_volts(self, value):
        self._ssr_max_volts = value

    # ---------------------------------
    @property
    def emr_max_amps(self):
        """Max current allowed through EMR
        """
        return self._emr_max_amps

    @emr_max_amps.setter
    def emr_max_amps(self, value):
        self._emr_max_amps = value

    # ---------------------------------
    @property
    def ssr_max_amps(self):
        """Max voltage allowed through SSR
        """
        return self._ssr_max_amps

    @ssr_max_amps.setter
    def ssr_max_amps(self, value):
        self._ssr_max_amps = value

    # ---------------------------------
    @property
    def done_ch1_adc(self):
        """ADC value on the current channel (CH1) at which the Arduino code
           considers the curve "done".
        """
        return self._done_ch1_adc

    @done_ch1_adc.setter
    def done_ch1_adc(self, value):
        self._done_ch1_adc = value

    # ---------------------------------
    @property
    def wire_ohms(self):
        """Estimated resistance of the wires and PCB traces in the "short
           circuit" path.
        """
        return self._wire_ohms

    @wire_ohms.setter
    def wire_ohms(self, value):
        self._wire_ohms = value

    # ---------------------------------
    @property
    def emr_ohms(self):
        """Estimated resistance of the EMR contacts
        """
        return self._emr_ohms

    @emr_ohms.setter
    def emr_ohms(self, value):
        self._emr_ohms = value

    # ---------------------------------
    @property
    def ssr_ohms(self):
        """Estimated on-resistance of the two SSRs in the short-circuit path
        """
        return self._ssr_ohms

    @ssr_ohms.setter
    def ssr_ohms(self, value):
        self._ssr_ohms = value

    # ---------------------------------
    @property
    def us_per_point(self):
        """Time, in microseconds, per I,V measurement
        """
        return self._us_per_point

    @us_per_point.setter
    def us_per_point(self, value):
        self._us_per_point = value

    # ---------------------------------
    @property
    def num_synth_points(self):
        """Number of synthesized points to generate. The larger this number,
           the more accurate the simulation will be, but the longer it
           will take.
        """
        return self._num_synth_points

    @num_synth_points.setter
    def num_synth_points(self, value):
        self._num_synth_points = value

    # ---------------------------------
    @property
    def opt_pct_headroom(self):
        """Percent above the specified Isc and Voc that the components should
           be chosen to handle.
        """
        return self._opt_pct_headroom

    @opt_pct_headroom.setter
    def opt_pct_headroom(self, value):
        self._opt_pct_headroom = value

    # ---------------------------------
    @property
    def cap_voltage_derate_pct(self):
        """Percent of the maximum rated capacitor voltage not to exceed
        """
        return self._cap_voltage_derate_pct

    @cap_voltage_derate_pct.setter
    def cap_voltage_derate_pct(self, value):
        self._cap_voltage_derate_pct = value

    # ---------------------------------
    @property
    def max_vdiv_current(self):
        """Maximum current through R1 and R2 (when choosing optimal values)
        """
        return self._max_vdiv_current

    @max_vdiv_current.setter
    def max_vdiv_current(self, value):
        self._max_vdiv_current = value

    # ---------------------------------
    @property
    def op_amp_max_drive_current(self):
        """Maximum current output of op amps
        """
        return self._op_amp_max_drive_current

    @op_amp_max_drive_current.setter
    def op_amp_max_drive_current(self, value):
        self._op_amp_max_drive_current = value

    # ---------------------------------
    @property
    def op_amp_max_input_current(self):
        """Maximum current input/bias of op amps
        """
        return self._op_amp_max_input_current

    @op_amp_max_input_current.setter
    def op_amp_max_input_current(self, value):
        self._op_amp_max_input_current = value

    # ---------------------------------
    @property
    def target_amm_op_amp_gain(self):
        """Target for ammeter op amp gain
        """
        return self._target_amm_op_amp_gain

    @target_amm_op_amp_gain.setter
    def target_amm_op_amp_gain(self, value):
        self._target_amm_op_amp_gain = value

    # ---------------------------------
    @property
    def target_max_swing_us(self):
        """Target for maximum time in microseconds to swing an IV curve
        """
        return self._target_max_swing_us

    @target_max_swing_us.setter
    def target_max_swing_us(self, value):
        self._target_max_swing_us = value

    # ---------------------------------
    @property
    def target_bleed_rc_us(self):
        """Target for bleed RC time-constant in microseconds
        """
        return self._target_bleed_rc_us

    @target_bleed_rc_us.setter
    def target_bleed_rc_us(self, value):
        self._target_bleed_rc_us = value

    # Derived properties
    # ---------------------------------
    @property
    def relay_ohms(self):
        """Resistance of "on" relay (EMR or SSR)"""
        if self.relay_type == "SSR":
            return self.ssr_ohms
        return self.emr_ohms

    # ---------------------------------
    @property
    def load_caps_ohms(self):
        """Equivalent resistance of the parallel load caps. Returns 0 for
           SSR-based design because short-circuit path does not include
           load caps.
        """
        if self.relay_type == "SSR":
            return 0.0
        return self.load_cap_esr / self.num_load_caps

    # ---------------------------------
    @property
    def load_caps_uf(self):
        """Combined capacitance of the parallel load caps"""
        return self.num_load_caps * self.load_cap_uf

    # ---------------------------------
    @property
    def load_cap_max_volts(self):
        """Maximum voltage allowed across load caps"""
        return self.load_cap_v * (self.cap_voltage_derate_pct/100.0)

    # ---------------------------------
    @property
    def relay_max_volts(self):
        """Maximum voltage allowed across relay (SSR or EMR)"""
        if self.relay_type == "SSR":
            return self.ssr_max_volts
        return self.emr_max_volts

    # ---------------------------------
    @property
    def relay_max_amps(self):
        """Maximum current allowed through relay (SSR or EMR)"""
        if self.relay_type == "SSR":
            return self.ssr_max_amps
        return self.emr_max_amps

    # ---------------------------------
    @property
    def opt_multiplier(self):
        """Multiplier, based on opt_pct_headroom"""
        return 1.0 + self.opt_pct_headroom/100.0

    # ---------------------------------
    @property
    def shunt_watts(self):
        """Shunt power dissipation in watts at Isc"""
        return (self.sim_isc ** 2) * self.amm_shunt_resistance

    # ---------------------------------
    @property
    def shunt_milliwatts(self):
        """Shunt power dissipation in milliwatts at Isc"""
        return 1000.0 * self.shunt_watts

    # ---------------------------------
    @property
    def shunt_pct_rated(self):
        """Shunt power dissipation as a percentage of its rated power"""
        return round(100.0 * self.shunt_watts / self.shunt_wattage, 2)

    # ---------------------------------
    @property
    def vdiv_amps(self):
        """Voltage divider current in amps at Voc"""
        return self.sim_voc / (self.vdiv_r1 + self.vdiv_r2)

    # ---------------------------------
    @property
    def vdiv_milliamps(self):
        """Voltage divider current in mA at Voc"""
        return 1000.0 * self.vdiv_amps

    # ---------------------------------
    @property
    def vdiv_r1_watts(self):
        """Resistor R1 power dissipation in watts at Voc"""
        return (self.vdiv_amps ** 2) * self.vdiv_r1

    # ---------------------------------
    @property
    def vdiv_r1_milliwatts(self):
        """Resistor R1 power dissipation in mW at Voc"""
        return 1000.0 * self.vdiv_r1_watts

    # ---------------------------------
    @property
    def vdiv_r1_pct_rated(self):
        """Resistor R1 power dissipation as a percentage of its rated power"""
        return round(100.0 *
                     self.vdiv_r1_watts / R1_R2_RF_RG_WATTAGE_DEFAULT, 2)

    # ---------------------------------
    @property
    def vdiv_r2_watts(self):
        """Resistor R2 power dissipation in watts at Voc"""
        return (self.vdiv_amps ** 2) * self.vdiv_r2

    # ---------------------------------
    @property
    def vdiv_r2_milliwatts(self):
        """Resistor R2 power dissipation in mW at Voc"""
        return 1000.0 * self.vdiv_r2_watts

    # ---------------------------------
    @property
    def vdiv_r2_pct_rated(self):
        """Resistor R2 power dissipation as a percentage of its rated power"""
        return round(100.0 *
                     self.vdiv_r2_watts / R1_R2_RF_RG_WATTAGE_DEFAULT, 2)

    # ---------------------------------
    @property
    def min_swing_interval(self):
        """Minimum amount of time (in seconds) between IV curves in order not to
           exceed bleed resistor power rating
        """
        load_caps_farads = self.load_caps_uf / 1000000.0
        load_cap_joules = 0.5 * load_caps_farads * self.sim_voc ** 2
        return load_cap_joules / self.rb_wattage

    # Methods
    # -------------------------------------------------------------------------
    def amps_from_volts(self, volts, a_coeff, b_coeff):
        """Method to implement the IV curve function. It may be called with a
           single value for volts and it will return a single value for
           amps. It may also be called with a NumPy array of voltage
           values and it will return a NumPy array of amps.
        """
        return self.sim_isc - a_coeff * np.expm1(b_coeff * volts)

    # -------------------------------------------------------------------------
    def get_b_coeff(self):
        """Method to determine the B coefficient, which is just the value of
           the b_coeff_per_voc property divided by Voc.
        """
        return self.b_coeff_per_voc / self.sim_voc

    # -------------------------------------------------------------------------
    def get_a_coeff(self, b_coeff):
        """Method to determine the A coefficient from the Isc and Voc, given
           the B coefficient. This is simply solving for a_coeff when
           I=0 and V=Voc.
        """
        a_coeff = self.sim_isc / np.expm1(b_coeff * self.sim_voc)
        return a_coeff

    # -------------------------------------------------------------------------
    def simulate(self):
        """Method to synthesize the IV curve from the given Isc and Voc values
           and generate the list of ADC values.
        """
        # pylint: disable=too-many-locals

        self.adc_pairs = []

        b_coeff = self.get_b_coeff()
        a_coeff = self.get_a_coeff(b_coeff)
        short_circuit_ohms = (self.amm_shunt_resistance + self.wire_ohms +
                              self.relay_ohms + self.load_caps_ohms)
        adc_steps_per_volt = ADC_MAX / self.v_sat
        adc_steps_per_amp = ADC_MAX / self.i_sat

        voc_adc = int(round(adc_steps_per_volt * self.sim_voc))

        us_since_prev = 0
        self.swing_time_us = 0
        prev_data_point = (None, None)
        for point in xrange(self.num_synth_points+1):
            # Voltage increment is Voc/#points
            volts = self.sim_voc * float(point) / self.num_synth_points

            # Calculate amps
            amps = self.amps_from_volts(volts, a_coeff, b_coeff)

            # Calculate load resistance
            if amps == 0.0:
                load_ohms = INFINITE_VAL
            else:
                load_ohms = volts / amps

            data_point = (volts, amps)

            # Only include points whose load resistance is greater than the
            # short-circuit resistance
            if load_ohms > short_circuit_ohms:
                delta_t = 0
                ch1_adc = 9999
                if prev_data_point[0]:
                    v1, i1 = prev_data_point
                    v2, i2 = data_point
                    delta_v = v2 - v1
                    i_avg = (i1 + i2) / 2
                    # I_avg = C * delta_v/delta_t
                    delta_t = self.load_caps_uf * delta_v / i_avg  # us
                us_since_prev += delta_t
                self.swing_time_us += delta_t
                if us_since_prev > self.us_per_point:
                    # Convert to integer ADC values
                    ch0_adc = int(round(adc_steps_per_volt * v2))
                    ch1_adc = int(round(adc_steps_per_amp * i2))

                    # Saturate at max
                    if ch0_adc > ADC_MAX:
                        ch0_adc = ADC_MAX
                    if ch1_adc > ADC_MAX:
                        ch1_adc = ADC_MAX

                    # If this is the first point, capture the Isc value
                    # as being equal to its current (as the Arduino
                    # sketch does)
                    if not self.adc_pairs:
                        isc_adc = ch1_adc

                    # Add to adc_pairs list
                    self.adc_pairs.append((ch0_adc, ch1_adc))

                    # Reset inter-point timer
                    us_since_prev = 0

                if ch1_adc <= self.done_ch1_adc:  # End of the curve
                    # Apply discard algorithm
                    self.pts_discarded = self.discard_adc_pairs()
                    # Prepend Isc point
                    self.adc_pairs.insert(0, (0, isc_adc))
                    # Add Voc point
                    self.adc_pairs.append((voc_adc, 0))
                    # Calculate bleed percent
                    self.calculate_bleed_pct()
                    return

                prev_data_point = data_point

    # -------------------------------------------------------------------------
    def discard_adc_pairs(self):
        """Method to emulate the Arduino sketch's discarding of points that are
           too close to their predecessor. The max_iv_points and
           max_discards properties have the same effects as they do in
           the Arduino code. If max_discards is set to 0, no points will
           be discarded (but the curve may end prematurely when the
           max_iv_points limit is reached.)
        """
        # Compute v_scale and i_scale. Similar to Arduino code but much
        # simpler since there is no reason to constrain their sum to 16
        # or less.
        voc_adc = self.adc_pairs[-1][0]
        isc_adc = self.adc_pairs[0][1]
        v_scale = int(round((self.aspect_width * isc_adc)))
        i_scale = int(round((self.aspect_height * voc_adc)))

        # Compute minimum manhattan distance. Same as Arduino code.
        min_manhattan_distance = (((isc_adc * i_scale) +
                                   (voc_adc * v_scale)) /
                                  self.max_iv_points)

        # Step through ADC pairs, discarding those that are too close to
        # their non-discarded predecessor. Same algorithm as Arduino
        # code.
        manhattan_distance = INFINITE_VAL
        num_discarded_pts = 0
        nondiscarded_adc_pairs = []
        pt_num = 0
        for ch0_adc, ch1_adc in self.adc_pairs:
            if pt_num:
                ch0_adc_delta = ch0_adc - nondiscarded_adc_pairs[pt_num-1][0]
                ch1_adc_delta = nondiscarded_adc_pairs[pt_num-1][1] - ch1_adc
                manhattan_distance = ((ch0_adc_delta * v_scale) +
                                      (ch1_adc_delta * i_scale))
            if ((manhattan_distance >= min_manhattan_distance) or
                    (num_discarded_pts >= self.max_discards)):
                # Keep
                nondiscarded_adc_pairs.append((ch0_adc, ch1_adc))
                pt_num += 1
                num_discarded_pts = 0
                if pt_num >= self.max_iv_points:
                    # We're done
                    break
            else:
                # Discard
                num_discarded_pts += 1

        total_discarded = len(self.adc_pairs) - len(nondiscarded_adc_pairs)
        self.adc_pairs = nondiscarded_adc_pairs

        return total_discarded

    # -------------------------------------------------------------------------
    def calculate_bleed_pct(self):
        """Method to calculate the percentage the capacitors will bleed,
           assuming a one-second interval between curves. This takes
           into account the time it takes to swing the curve.
        """
        time_remaining = 1.0 - (self.swing_time_us / 1000000.0)
        if time_remaining <= 0.0:
            self.bleed_pct = 0.0
        else:
            load_caps_farads = self.load_caps_uf / 1000000.0
            vt_over_v0 = np.exp(-time_remaining/(self.rb_ohms *
                                                 load_caps_farads))
            self.bleed_pct = (1.0 - vt_over_v0) * 100.0
            self.unbled_volts = vt_over_v0 * self.sim_voc

    # -------------------------------------------------------------------------
    def choose_optimal_components(self):
        """Method to choose components that work best for the given Isc and Voc
           values. The values chosen will support a maximum Isc that is
           30% (opt_pct_headroom) higher than the given Isc and will
           support a maximum Voc that is 30% higher than the given Voc.
        """
        rc = RC_SUCCESS

        # Choose R1 and R2
        self.choose_optimal_r1_r2()

        # Choose Shunt (must be chosen before Rf and Rg)
        self.choose_optimal_shunt()

        # Choose Rf and Rg
        self.choose_optimal_rf_rg()

        # Choose load cap
        rc = self.choose_optimal_load_caps()

        # Choose Rb
        self.choose_optimal_rb()

        return rc

    # -------------------------------------------------------------------------
    def choose_optimal_r1_r2(self):
        """Method to choose the best values for the R1 and R2 resistors used
           for the voltmeter voltage divider
        """
        ideal_vdiv_ratio = self.adc_vref / (self.sim_voc * self.opt_multiplier)
        least_err = INFINITE_VAL
        for r1_ohms in QTR_WATT_RESISTORS:
            for r2_ohms in QTR_WATT_RESISTORS:
                vdiv_ohms = r1_ohms + r2_ohms
                vdiv_current = self.sim_voc / vdiv_ohms
                if vdiv_current > self.max_vdiv_current:
                    continue
                vdiv_ratio = r2_ohms / vdiv_ohms
                err = ideal_vdiv_ratio - vdiv_ratio
                if err > 0 and err < least_err:
                    self.vdiv_r1 = r1_ohms
                    self.vdiv_r2 = r2_ohms
                    if r1_ohms == ZERO_OHMS:
                        self.vdiv_r1 = 0.0
                    if r2_ohms == ZERO_OHMS:
                        self.vdiv_r2 = 0.0
                    least_err = err

    # -------------------------------------------------------------------------
    def choose_optimal_shunt(self):
        """Method to choose the best value for the shunt resistor used for the
           ammeter
        """
        least_err = INFINITE_VAL
        for ohms, watts, mfg_pn in SHUNT_RESISTORS:
            v_shunt_max = self.sim_isc * self.opt_multiplier * ohms
            err = abs(self.adc_vref - (v_shunt_max *
                                       self.target_amm_op_amp_gain))
            if err < least_err:
                self.amm_shunt_max_volts = self.amm_shunt_max_amps * ohms
                self.shunt_wattage = watts
                self.shunt_mfg_pn = mfg_pn
                least_err = err

    # -------------------------------------------------------------------------
    def choose_optimal_rf_rg(self):
        """Method to choose the best values for the Rf and Rg resistors used
           for the ammeter voltage multiplier
        """
        least_err = INFINITE_VAL
        v_shunt_max = (self.sim_isc * self.opt_multiplier *
                       self.amm_shunt_resistance)
        for rf_ohms in QTR_WATT_RESISTORS:
            for rg_ohms in QTR_WATT_RESISTORS:
                if rg_ohms > rf_ohms:
                    continue
                rf_rg_max_current = self.adc_vref / (rf_ohms + rg_ohms)
                if rf_rg_max_current > self.op_amp_max_drive_current / 200.0:
                    continue
                if rf_rg_max_current < self.op_amp_max_input_current * 500.0:
                    continue
                amm_op_amp_gain = 1.0 + (rf_ohms / rg_ohms)
                err = self.adc_vref - (v_shunt_max * amm_op_amp_gain)
                if err > 0 and err < least_err:
                    self.amm_op_amp_rf = rf_ohms
                    self.amm_op_amp_rg = rg_ohms
                    if rf_ohms == ZERO_OHMS:
                        self.amm_op_amp_rf = 0.0
                    if rg_ohms == ZERO_OHMS:
                        self.amm_op_amp_rg = 0.0
                    least_err = err

    # -------------------------------------------------------------------------
    def choose_optimal_load_caps(self):
        """Method to choose the best value for the load capacitors. This is
           simply the one with the lowest adequate voltage rating which
           will be the highest capacitance possible.
        """
        caps_chosen = False
        cap_min_voltage = self.sim_voc / (self.cap_voltage_derate_pct/100.0)
        for capacitance, voltage, esr, height, mfg_pn in LOAD_CAPACITORS:
            total_capacitance = capacitance * self.num_load_caps
            if voltage >= cap_min_voltage:
                caps_chosen = True
                self.load_cap_uf = capacitance
                self.load_cap_v = voltage
                self.load_cap_esr = esr
                self.load_cap_height_mm = height
                self.load_cap_mfg_pn = mfg_pn
                # Assume minimum Isc is 10% of specified
                min_isc = 0.1 * self.sim_isc
                # Assume Vmpp is 75% of Voc
                v_mpp = self.sim_voc * 0.75
                # Estimate time to MPP and double it
                est_max_swing_us = int(2.0 * total_capacitance *
                                       v_mpp / min_isc)
                if est_max_swing_us < self.target_max_swing_us:
                    break
        if not caps_chosen:
            err_str = "NO LOAD CAPS FOUND WITH SUFFICIENT VOLTAGE"
            self.logger.print_and_log(err_str)
            return RC_FAILURE
        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def choose_optimal_rb(self):
        """Method to choose the best value for the bleed resistor
        """
        least_diff = INFINITE_VAL
        for ohms, watts, mfg_pn in BLEED_RESISTORS:
            bleed_rc_us = self.load_caps_uf * ohms
            diff = abs(bleed_rc_us - self.target_bleed_rc_us)
            if diff < least_diff:
                least_diff = diff
                self.rb_ohms = ohms
                self.rb_wattage = watts
                self.rb_mfg_pn = mfg_pn

    # -------------------------------------------------------------------------
    def set_plot_title(self):
        """Method to set the plot title to indicate that the curve is a
           simulation and to include the component values.
        """
        title_str = "Simulation: "
        title_str += "R1={}, R2={}, Rf={}, Rg={}, Shunt={}, C1=C2={}"
        self.plot_title = title_str.format(shorten_value(self.vdiv_r1),
                                           shorten_value(self.vdiv_r2),
                                           shorten_value(self.amm_op_amp_rf),
                                           shorten_value(self.amm_op_amp_rg),
                                           self.amm_shunt_resistance,
                                           shorten_value(self.load_cap_uf))

    # -------------------------------------------------------------------------
    def display_pdf(self):
        """Method to display the PDF of the simulated curve
        """
        if os.path.exists(self.pdf_filename):
            IV_Swinger2.sys_view_file(self.pdf_filename)

    # -------------------------------------------------------------------------
    def gen_results_text(self):
        """Method to generate the text summarizing the results of a simulation.
        """
        self.results_text = "\nSimulation Results\n\n"
        self.results_text += "{}\n\n".format(self.hdd_output_dir)
        self.results_text += self.gen_isc_voc_vals_text()
        self.results_text += "\n"
        self.results_text += self.gen_component_vals_text()
        self.results_text += "\n"
        self.results_text += self.gen_limits_text()
        self.results_text += "\n"
        self.results_text += self.gen_sim_results_text()
        self.logger.log(self.results_text)

    # -------------------------------------------------------------------------
    def gen_isc_voc_vals_text(self):
        """Method to generate the text listing the Isc and Voc values
        """
        text = "Isc: {} A     Voc: {} V\n".format(self.sim_isc, self.sim_voc)
        return text

    # -------------------------------------------------------------------------
    def gen_component_vals_text(self):
        """Method to generate the text listing the component values
        """
        text = "Component values:\n"
        text += ("  Relay type: {}\n"
                 .format(self.relay_type))
        text += ("  R1: {} ohms, 1/4W\n"
                 .format(shorten_value(self.vdiv_r1)))
        text += ("  R2: {} ohms, 1/4W\n"
                 .format(shorten_value(self.vdiv_r2)))
        text += ("  Rf: {} ohms, 1/4W\n"
                 .format(shorten_value(self.amm_op_amp_rf)))
        text += ("  Rg: {} ohms, 1/4W\n"
                 .format(shorten_value(self.amm_op_amp_rg)))
        text += ("  Shunt: {} ohms, {}W  PN: {}\n"
                 .format(self.amm_shunt_resistance,
                         shorten_value(self.shunt_wattage),
                         self.shunt_mfg_pn))
        text += ("  C1,C2: {} uF, {}V  PN: {}\n"
                 .format(shorten_value(self.load_cap_uf),
                         shorten_value(self.load_cap_v),
                         self.load_cap_mfg_pn))
        text += ("  Rb: {} ohms, {}W  PN: {}\n"
                 .format(shorten_value(self.rb_ohms),
                         shorten_value(self.rb_wattage),
                         self.rb_mfg_pn))
        return text

    # -------------------------------------------------------------------------
    def gen_limits_text(self):
        """Method to generate the text listing the voltage and current limits
        """
        text = "Limits:\n"
        v_max = min(self.v_sat, self.relay_max_volts, self.load_cap_max_volts)
        if v_max == self.load_cap_max_volts:
            v_max_reason = ("({}% of {}V load cap rating)"
                            .format(shorten_value(self.cap_voltage_derate_pct),
                                    shorten_value(self.load_cap_v)))
        elif v_max == self.relay_max_volts:
            v_max_reason = "({} max voltage)".format(self.relay_type)
        else:
            v_max_reason = "(ADC saturation)"
        max_exceeded = ""
        if self.sim_voc > v_max:
            max_exceeded = "     <== EXCEEDED!!"
        text += "  Max voltage: {} V {} {}\n".format(sigfigs(v_max, 4),
                                                     v_max_reason,
                                                     max_exceeded)

        i_max = min(self.i_sat, self.relay_max_amps)
        if i_max == self.relay_max_amps:
            i_max_reason = "({} max current)".format(self.relay_type)
        else:
            i_max_reason = "(ADC saturation)"
        max_exceeded = ""
        if self.sim_isc > i_max:
            max_exceeded = "     <== EXCEEDED!!"
        text += "  Max current: {} A {} {}\n".format(sigfigs(i_max, 4),
                                                     i_max_reason,
                                                     max_exceeded)
        return text

    # -------------------------------------------------------------------------
    def gen_sim_results_text(self):
        """Method to generate the text listing the simulation results
        """
        text = "Simulation data:\n"
        # Swing time
        text += ("  Swing time: {} microseconds\n"
                 .format(int(self.swing_time_us)))
        # Points recorded/discarded
        text += ("  Points recorded: {}\n"
                 .format(int(len(self.adc_pairs))))
        text += ("  Points discarded: {}\n"
                 .format(int(self.pts_discarded)))
        # Bleed percent
        warning = ""
        if self.bleed_pct < 99.0:
            warning = "     <== INSUFFICIENT!!"
        text += ("  Bleed %: {} ({} V @ 1 s) {}\n"
                 .format(sigfigs(self.bleed_pct, 5),
                         sigfigs(self.unbled_volts, 3), warning))
        # Voltage divider power dissipation
        warning = ""
        if self.vdiv_r1_pct_rated > 100.0:
            warning = "     <== TOO MUCH!!"
        text += ("  R1 power: {} mW ({} % rated) {}\n"
                 .format(sigfigs(self.vdiv_r1_milliwatts, 3),
                         sigfigs(self.vdiv_r1_pct_rated, 3), warning))
        warning = ""
        if self.vdiv_r2_pct_rated > 100.0:
            warning = "     <== TOO MUCH!!"
        text += ("  R2 power: {} mW ({} % rated) {}\n"
                 .format(sigfigs(self.vdiv_r2_milliwatts, 3),
                         sigfigs(self.vdiv_r2_pct_rated, 3), warning))
        warning = ""
        if self.shunt_pct_rated > 300.0:
            warning = "     <== TOO MUCH!!"
        elif self.shunt_pct_rated > 100.0:
            warning = "     <== OK (low duty cycle)"
        text += ("  Shunt power: {} mW ({} % rated) {}\n"
                 .format(sigfigs(self.shunt_milliwatts, 3),
                         sigfigs(self.shunt_pct_rated, 3), warning))
        # Rf/Rg current
        v_shunt_isc = self.sim_isc * self.amm_shunt_resistance
        v_op_amp_out = v_shunt_isc * self.amm_op_amp_gain
        rf_rg_amps = v_op_amp_out / (self.amm_op_amp_rf + self.amm_op_amp_rg)
        rf_rg_microamps = rf_rg_amps * 1000000.0
        drive_1_over_x = self.op_amp_max_drive_current / rf_rg_amps
        input_x = rf_rg_amps / self.op_amp_max_input_current
        text += "  Rf,Rg current @ Isc: "
        text += ("{} uA (1/{} op amp drive, {}x op amp input)\n"
                 .format(sigfigs(rf_rg_microamps, 4),
                         int(float(sigfigs(drive_1_over_x, 4))),
                         int(float(sigfigs(input_x, 4)))))
        # Minimum swing interval
        warning = ""
        if self.min_swing_interval > 1.0:
            warning = "     <== WARNING!!"
        text += ("  Min swing interval (Rb wattage): {} seconds {}\n"
                 .format(sigfigs(self.min_swing_interval, 2), warning))
        # Resolution
        adc_steps_per_volt = ADC_MAX / self.v_sat
        adc_steps_per_amp = ADC_MAX / self.i_sat
        voltage_adc_steps = int(round(adc_steps_per_volt * self.sim_voc))
        current_adc_steps = int(round(adc_steps_per_amp * self.sim_isc))
        voltage_adc_pct_utilization = int(round(100.0 * voltage_adc_steps /
                                                ADC_MAX))
        current_adc_pct_utilization = int(round(100.0 * current_adc_steps /
                                                ADC_MAX))
        text += "  Resolution:\n"
        text += ("    ADC steps from 0V to Voc: {} ({}% utilization)\n"
                 .format(voltage_adc_steps, voltage_adc_pct_utilization))
        text += ("    ADC steps from 0A to Isc: {} ({}% utilization)\n"
                 .format(current_adc_steps, current_adc_pct_utilization))
        return text

    # -------------------------------------------------------------------------
    def run(self):
        """Method to run the simulation and plot its IV curve. Like a real run,
           the results are saved in a run directory. This includes a
           configuration file. This makes it possible to view the
           results later with the Results Wizard.
        """
        rc = RC_SUCCESS

        # Create the simulation output directory and generate the CSV
        # file names
        date_time_str = IV_Swinger2.get_date_time_str()
        self.create_hdd_output_dir(date_time_str)
        self.get_csv_filenames(self.hdd_output_dir, date_time_str)

        # Run the simulate() method to generate the adc_pairs list
        self.simulate()

        # Write the ADC pairs to the adc_pairs CSV file
        self.write_adc_pairs_to_csv_file(self.hdd_adc_pairs_csv_filename,
                                         self.adc_pairs)

        # Turn off ADC correction. We want to see the raw simulated
        # results
        self.correct_adc = False

        # Convert the ADC values to volts, amps, watts and ohms and
        # write those to the iv_swinger2 CSV file
        rc = self.process_adc_values()
        if rc != RC_SUCCESS:
            return rc

        # Plot the results. Override the saturation voltage and current
        # to take into account the relay and capacitor limits. The
        # limits are shown regardless of whether the Voc and Isc exceed
        # the limits, however, they won't show if the limit is off the
        # edge of the graph.
        self.set_plot_title()
        v_sat_override = min(self.v_sat, self.relay_max_volts,
                             self.load_cap_max_volts)
        i_sat_override = min(self.i_sat, self.relay_max_amps)
        # Keep "Max current exceeded" from running off the top into the title
        if i_sat_override > 0.9 * self.max_i_ratio * self.sim_isc:
            i_sat_override = None
        self.plot_results(v_sat_override, i_sat_override)

        # Fill results_text
        self.results_text = ""
        self.gen_results_text()

        # Populate the configuration from the simulator properties
        self.config.populate()
        self.config.add_axes_and_title()

        # Save the configuration to the simulation output directory
        self.config.save(self.hdd_output_dir)

        # Restore the master config file from the snapshot
        self.config.save_snapshot()  # restore original

        # Clean up files
        self.clean_up_files(self.hdd_output_dir)

        return rc


# Simulator dialog class
#
class SimulatorDialog(tk.Toplevel):
    """Simulator dialog class. This class is used by the IV_Swinger2_gui
       module's GraphicalUserInterface class, but could be used by any
       ttk.Frame class.
    """
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods

    # Initializer
    def __init__(self, master=None):
        tk.Toplevel.__init__(self, master=master)
        self.master = master
        # Hack: determine if we're running under the IVS2 GUI or
        # standalone
        self.running_under_ivs2_gui = True
        try:
            if self.master.version:
                pass
        except AttributeError:
            self.running_under_ivs2_gui = False
        self.win_sys = self.master.tk.call("tk", "windowingsystem")
        if not self.running_under_ivs2_gui:
            # Doesn't start on top without this (but it breaks mimimize)
            self.update_idletasks()
        self.transient(self.master)  # tie this window to master
        title = "IV Swinger 2 Simulator"
        self.title(title)
        self.grab_set()  # block change of focus to master
        self.focus_set()

        # Initialize the widget handles that need to be accessed by
        # callback methods
        self.isc_amps_slider = None
        self.voc_volts_slider = None

        # Initialize the results tab widget
        self.results_tab = None

        # Create an IV_Swinger2_sim object
        self.ivs2_sim = IV_Swinger2_sim()

        # Create the widget variable objects
        self.create_widget_vars()

        # Initialize the widget variables from the simulator object
        # properties
        self.set_widget_vars_from_props()

        # Create body frame
        body = ttk.Frame(self)

        # Call body method to create body contents
        self.body(body)
        body.pack(fill=BOTH, expand=True)

        # Set the dialog position by calling the master's
        # set_dialog_geometry method. If that method doesn't exist or is
        # incompatible, call our own set_dialog_geometry global function.
        try:
            self.master.set_dialog_geometry(self)
        except (AttributeError, TypeError):
            set_dialog_geometry(self)

        # The dialog is not resizable, so constrain its width and height
        # to their current values.
        pseudo_dialog_resize_disable(self)

        # Register callback for when the dialog is closed
        self.protocol("WM_DELETE_WINDOW", self.done)

        # Map Ctrl-A and Cmd-A (Mac) to select-all for Text widgets
        # (which includes ScrolledText)
        self.master.bind_class("Text", "<Control-a>", selectall)
        self.master.bind_class("Text", "<Command-a>", selectall)

        # Wait for dialog to be closed before returning control
        self.wait_window(self)

    # -------------------------------------------------------------------------
    def create_widget_vars(self):
        """Method to create the widgets' tk StringVar objects
        """
        # Main controls
        self.relay_type = tk.StringVar()
        self.isc_amps = tk.StringVar()
        self.voc_volts = tk.StringVar()
        self.r1_ohms = tk.StringVar()
        self.r1_slider_index = tk.StringVar()
        self.r2_ohms = tk.StringVar()
        self.r2_slider_index = tk.StringVar()
        self.rf_ohms = tk.StringVar()
        self.rf_slider_index = tk.StringVar()
        self.rg_ohms = tk.StringVar()
        self.rg_slider_index = tk.StringVar()
        self.shunt_ohms = tk.StringVar()
        self.shunt_slider_index = tk.StringVar()
        self.shunt_wattage = tk.StringVar()
        self.shunt_mfg_pn = tk.StringVar()
        self.load_cap_uf = tk.StringVar()
        self.load_cap_slider_index = tk.StringVar()
        self.load_cap_v = tk.StringVar()
        self.load_cap_mfg_pn = tk.StringVar()
        self.rb_ohms = tk.StringVar()
        self.rb_slider_index = tk.StringVar()
        self.rb_wattage = tk.StringVar()
        self.rb_mfg_pn = tk.StringVar()

        # Other controls
        self.b_coeff_per_voc = tk.StringVar()
        self.us_per_point = tk.StringVar()
        self.num_synth_points = tk.StringVar()
        self.num_load_caps = tk.StringVar()
        self.done_ch1_adc = tk.StringVar()
        self.wire_ohms = tk.StringVar()
        self.emr_ohms = tk.StringVar()
        self.ssr_ohms = tk.StringVar()
        self.opt_pct_headroom = tk.StringVar()
        self.cap_voltage_derate_pct = tk.StringVar()
        self.max_vdiv_current = tk.StringVar()
        self.op_amp_max_drive_current = tk.StringVar()
        self.op_amp_max_input_current = tk.StringVar()
        self.target_amm_op_amp_gain = tk.StringVar()
        self.target_max_swing_us = tk.StringVar()
        self.target_bleed_rc_us = tk.StringVar()

    # -------------------------------------------------------------------------
    def body(self, master):
        """Method to create body, which is a Notebook (tabbed frames)
        """
        self.nb = ttk.Notebook(master)
        self.main_controls_tab = ttk.Frame(self.nb)
        self.other_controls_tab = ttk.Frame(self.nb)
        self.nb.add(self.main_controls_tab, text="Main Controls")
        self.nb.add(self.other_controls_tab, text="Other Controls")
        self.populate_main_controls_tab()
        self.populate_other_controls_tab()
        self.nb.pack()

    # -------------------------------------------------------------------------
    def populate_main_controls_tab(self):
        """Method to add widgets to the Main Controls tab"""
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-statements

        # Add container box for widgets
        main_controls_widget_box = ttk.Frame(master=self.main_controls_tab,
                                             padding=20)
        master = main_controls_widget_box

        # Add relay type widgets
        (relay_type_label,
         emr_rb,
         ssr_rb) = self.add_relay_type_widgets(master)

        # Add Isc widgets
        (isc_amps_label,
         isc_amps_entry,
         self.isc_amps_slider) = self.add_isc_widgets(master)

        # Add Voc widgets
        (voc_volts_label,
         voc_volts_entry,
         self.voc_volts_slider) = self.add_voc_widgets(master)

        # Add button to choose optimal components
        choose_components_button = self.add_choose_components_button(master)

        # Add R1 widgets
        (r1_ohms_label,
         r1_ohms_entry,
         r1_ohms_slider) = self.add_r1_widgets(master)

        # Add R2 widgets
        (r2_ohms_label,
         r2_ohms_entry,
         r2_ohms_slider) = self.add_r2_widgets(master)

        # Add RF widgets
        (rf_ohms_label,
         rf_ohms_entry,
         rf_ohms_slider) = self.add_rf_widgets(master)

        # Add RG widgets
        (rg_ohms_label,
         rg_ohms_entry,
         rg_ohms_slider) = self.add_rg_widgets(master)

        # Add shunt widgets
        (shunt_ohms_label,
         shunt_ohms_entry,
         shunt_ohms_slider,
         shunt_wattage_entry,
         shunt_wattage_label,
         shunt_mfg_pn_entry,
         shunt_mfg_pn_label) = self.add_shunt_widgets(master)

        # Add load cap widgets
        (load_cap_uf_label,
         load_cap_uf_entry,
         load_cap_uf_slider,
         load_cap_v_entry,
         load_cap_v_label,
         load_cap_mfg_pn_entry,
         load_cap_mfg_pn_label) = self.add_load_cap_widgets(master)

        # Add Rb widgets
        (rb_ohms_label,
         rb_ohms_entry,
         rb_ohms_slider,
         rb_wattage_entry,
         rb_wattage_label,
         rb_mfg_pn_entry,
         rb_mfg_pn_label) = self.add_rb_widgets(master)

        # Help, Restore Defaults and Simulate buttons are not contained
        # in the main_controls_widget_box, but are at the top level of
        # the tab Frame.
        master = self.main_controls_tab

        # Add Help button
        help_button = ttk.Button(master=master,
                                 text="Help", width=8,
                                 command=self.show_simulator_help)

        # Add Restore Defaults button
        restore_cmd = self.restore_component_defaults
        restore_button = ttk.Button(master=master,
                                    text="Restore Defaults",
                                    command=restore_cmd)

        # Add simulate button
        simulate_button = self.add_simulate_button(master=master)

        # Layout
        main_controls_widget_box.grid(column=0, row=0, sticky=W, columnspan=2)
        pady = 8
        row = 0
        relay_type_label.grid(column=0, row=row, sticky=W)
        emr_rb.grid(column=1, row=row, sticky=W)
        ssr_rb.grid(column=2, row=row, sticky=W)
        row += 1
        isc_amps_label.grid(column=0, row=row, sticky=W, pady=pady)
        isc_amps_entry.grid(column=1, row=row, sticky=W, pady=pady)
        self.isc_amps_slider.grid(column=2, row=row, sticky=W, pady=pady)
        row += 1
        voc_volts_label.grid(column=0, row=row, sticky=W, pady=pady)
        voc_volts_entry.grid(column=1, row=row, sticky=W, pady=pady)
        self.voc_volts_slider.grid(column=2, row=row, sticky=W, pady=pady)
        row += 1
        ttk.Label(main_controls_widget_box, text=" ").grid(column=0, row=row)
        row += 1
        ttk.Separator(main_controls_widget_box).grid(row=row, columnspan=9,
                                                     sticky="ew")
        row += 1
        ttk.Label(main_controls_widget_box, text=" ").grid(column=0, row=row)
        row += 1
        choose_components_button.grid(column=0, row=row, sticky=W, pady=pady,
                                      columnspan=3)
        row += 1
        r1_ohms_label.grid(column=0, row=row, sticky=W, pady=pady)
        r1_ohms_entry.grid(column=1, row=row, sticky=W, pady=pady)
        r1_ohms_slider.grid(column=2, row=row, sticky=W, pady=pady)
        row += 1
        r2_ohms_label.grid(column=0, row=row, sticky=W, pady=pady)
        r2_ohms_entry.grid(column=1, row=row, sticky=W, pady=pady)
        r2_ohms_slider.grid(column=2, row=row, sticky=W, pady=pady)
        row += 1
        rf_ohms_label.grid(column=0, row=row, sticky=W, pady=pady)
        rf_ohms_entry.grid(column=1, row=row, sticky=W, pady=pady)
        rf_ohms_slider.grid(column=2, row=row, sticky=W, pady=pady)
        row += 1
        rg_ohms_label.grid(column=0, row=row, sticky=W, pady=pady)
        rg_ohms_entry.grid(column=1, row=row, sticky=W, pady=pady)
        rg_ohms_slider.grid(column=2, row=row, sticky=W, pady=pady)
        row += 1
        shunt_ohms_label.grid(column=0, row=row, sticky=W, pady=pady)
        shunt_ohms_entry.grid(column=1, row=row, sticky=W, pady=pady)
        shunt_ohms_slider.grid(column=2, row=row, sticky=W, pady=pady)
        shunt_wattage_entry.grid(column=3, row=row, sticky=W, pady=pady)
        shunt_wattage_label.grid(column=4, row=row, sticky=W, pady=pady)
        shunt_mfg_pn_entry.grid(column=5, row=row, sticky=W, pady=pady)
        shunt_mfg_pn_label.grid(column=6, row=row, sticky=W, pady=pady)
        row += 1
        load_cap_uf_label.grid(column=0, row=row, sticky=W, pady=pady)
        load_cap_uf_entry.grid(column=1, row=row, sticky=W, pady=pady)
        load_cap_uf_slider.grid(column=2, row=row, sticky=W, pady=pady)
        load_cap_v_entry.grid(column=3, row=row, sticky=W, pady=pady)
        load_cap_v_label.grid(column=4, row=row, sticky=W, pady=pady)
        load_cap_mfg_pn_entry.grid(column=5, row=row, sticky=W, pady=pady)
        load_cap_mfg_pn_label.grid(column=6, row=row, sticky=W, pady=pady)
        row += 1
        rb_ohms_label.grid(column=0, row=row, sticky=W, pady=pady)
        rb_ohms_entry.grid(column=1, row=row, sticky=W, pady=pady)
        rb_ohms_slider.grid(column=2, row=row, sticky=W, pady=pady)
        rb_wattage_entry.grid(column=3, row=row, sticky=W, pady=pady)
        rb_wattage_label.grid(column=4, row=row, sticky=W, pady=pady)
        rb_mfg_pn_entry.grid(column=5, row=row, sticky=W, pady=pady)
        rb_mfg_pn_label.grid(column=6, row=row, sticky=W, pady=pady)
        # End of main_controls_widget_box (row 0 of main_controls_tab)
        row = 2
        help_button.grid(column=0, row=row, sticky=W, pady=pady,
                         columnspan=2)
        restore_button.grid(column=1, row=row, sticky=E)
        row += 1
        simulate_button.grid(column=0, row=row, pady=pady, columnspan=9)

    # -------------------------------------------------------------------------
    def set_widget_vars_from_props(self):
        """Method to set the widget variables from their associated simulator
           object properties
        """
        self.set_relay_isc_and_voc_vars_from_props()
        self.set_r1_r2_rf_and_rg_vars_from_props()
        self.set_shunt_vars_from_props()
        self.set_load_cap_vars_from_props()
        self.set_rb_vars_from_props()
        self.set_other_controls_vars_from_props()

    # -------------------------------------------------------------------------
    def set_relay_isc_and_voc_vars_from_props(self):
        """Method to set the relay_type, isc_amps and voc_volts widget
           variables from their associated simulator object properties
        """
        self.relay_type.set(self.ivs2_sim.relay_type)
        self.isc_amps.set(self.ivs2_sim.sim_isc)
        self.voc_volts.set(self.ivs2_sim.sim_voc)

    # -------------------------------------------------------------------------
    def set_r1_r2_rf_and_rg_vars_from_props(self):
        """Method to set the r1_ohms, r1_slider_index, r2_ohms,
           r2_slider_index, rf_ohms, rf_slider_index, rg_ohms and
           rg_slider_index widget variables from their associated
           simulator object properties
        """
        self.r1_ohms.set(self.ivs2_sim.vdiv_r1)
        self.r1_slider_index.set(index_from_ohms(self.ivs2_sim.vdiv_r1))
        self.r2_ohms.set(self.ivs2_sim.vdiv_r2)
        self.r2_slider_index.set(index_from_ohms(self.ivs2_sim.vdiv_r2))
        self.rf_ohms.set(self.ivs2_sim.amm_op_amp_rf)
        self.rf_slider_index.set(index_from_ohms(self.ivs2_sim.amm_op_amp_rf))
        self.rg_ohms.set(self.ivs2_sim.amm_op_amp_rg)
        self.rg_slider_index.set(index_from_ohms(self.ivs2_sim.amm_op_amp_rg))

    # -------------------------------------------------------------------------
    def set_shunt_vars_from_props(self):
        """Method to set the shunt_ohms, shunt_slider_index, shunt_wattage and
           shunt_mfg_pn widget variables from their associated simulator
           object properties
        """
        shunt_resistance = self.ivs2_sim.amm_shunt_resistance
        self.shunt_ohms.set(shunt_resistance)
        self.shunt_slider_index.set(shunt_index_from_ohms(shunt_resistance))
        self.shunt_wattage.set(self.ivs2_sim.shunt_wattage)
        self.shunt_mfg_pn.set(self.ivs2_sim.shunt_mfg_pn)

    # -------------------------------------------------------------------------
    def set_load_cap_vars_from_props(self):
        """Method to set the load_cap_uf, load_cap_slider_index, load_cap_v and
           load_cap_mfg_pn widget variables from their associated
           simulator object properties
        """
        load_cap_uf = self.ivs2_sim.load_cap_uf
        self.load_cap_uf.set(load_cap_uf)
        # Load cap slider is in opposite order from LOAD_CAPACITORS
        load_cap_index = load_cap_index_from_uf(load_cap_uf)
        load_cap_slider_index = len(LOAD_CAPACITORS) - load_cap_index - 1
        self.load_cap_slider_index.set(load_cap_slider_index)
        self.load_cap_v.set(self.ivs2_sim.load_cap_v)
        self.load_cap_mfg_pn.set(self.ivs2_sim.load_cap_mfg_pn)

    # -------------------------------------------------------------------------
    def set_rb_vars_from_props(self):
        """Method to set the rb_ohms, rb_slider_index, rb_wattage and rb_mfg_pn
           widget variables from their associated simulator object
           properties
        """
        self.rb_ohms.set(self.ivs2_sim.rb_ohms)
        self.rb_slider_index.set(rb_index_from_ohms(self.ivs2_sim.rb_ohms))
        self.rb_wattage.set(self.ivs2_sim.rb_wattage)
        self.rb_mfg_pn.set(self.ivs2_sim.rb_mfg_pn)

    # -------------------------------------------------------------------------
    def set_other_controls_vars_from_props(self):
        """Method to set all of the widget variables for the entries on the
           Other Controls tab from their associated simulator object
           properties
        """
        self.b_coeff_per_voc.set(self.ivs2_sim.b_coeff_per_voc)
        self.us_per_point.set(self.ivs2_sim.us_per_point)
        self.num_synth_points.set(self.ivs2_sim.num_synth_points)
        self.num_load_caps.set(self.ivs2_sim.num_load_caps)
        self.done_ch1_adc.set(self.ivs2_sim.done_ch1_adc)
        self.wire_ohms.set(self.ivs2_sim.wire_ohms)
        self.emr_ohms.set(self.ivs2_sim.emr_ohms)
        self.ssr_ohms.set(self.ivs2_sim.ssr_ohms)
        self.opt_pct_headroom.set(self.ivs2_sim.opt_pct_headroom)
        self.cap_voltage_derate_pct.set(self.ivs2_sim.cap_voltage_derate_pct)
        self.max_vdiv_current.set(self.ivs2_sim.max_vdiv_current)
        prop_val = self.ivs2_sim.op_amp_max_drive_current
        self.op_amp_max_drive_current.set(prop_val)
        prop_val = self.ivs2_sim.op_amp_max_input_current
        self.op_amp_max_input_current.set(prop_val)
        self.target_amm_op_amp_gain.set(self.ivs2_sim.target_amm_op_amp_gain)
        self.target_max_swing_us.set(self.ivs2_sim.target_max_swing_us)
        self.target_bleed_rc_us.set(self.ivs2_sim.target_bleed_rc_us)

    # -------------------------------------------------------------------------
    def add_relay_type_widgets(self, master):
        """Method to add the relay type label and radio buttons"""
        relay_type_label = ttk.Label(master=master,
                                     text="Relay type:")
        emr_rb = ttk.Radiobutton(master=master,
                                 text="EMR",
                                 variable=self.relay_type,
                                 command=self.update_relay_type,
                                 value="EMR")
        ssr_rb = ttk.Radiobutton(master=master,
                                 text="SSR",
                                 variable=self.relay_type,
                                 command=self.update_relay_type,
                                 value="SSR")

        return relay_type_label, emr_rb, ssr_rb

    # -------------------------------------------------------------------------
    def add_isc_widgets(self, master):
        """Method to add the Isc label, entry and slider"""
        # Add scale slider and entry box for Isc. They both use the same
        # variable, so when the slider is moved, the value in the entry box is
        # changed and when the value in the entry box is changed, the slider
        # moves. This allows the user the choice of whether to type in a value
        # or to use the slider.
        isc_amps_label = ttk.Label(master=master,
                                   text="Isc (amps):")
        isc_amps_entry = ttk.Entry(master=master,
                                   width=8,
                                   textvariable=self.isc_amps)
        isc_amps_entry.bind("<Return>", self.isc_and_voc_widget_actions)
        isc_amps_slider = ttk.Scale(master=master,
                                    length=SLIDER_LENGTH,
                                    from_=0.001,
                                    to=self.ivs2_sim.relay_max_amps,
                                    variable=self.isc_amps,
                                    command=self.round_isc_amps)
        isc_amps_slider.bind("<ButtonRelease-1>",
                             self.isc_and_voc_widget_actions)

        return isc_amps_label, isc_amps_entry, isc_amps_slider

    # -------------------------------------------------------------------------
    def add_voc_widgets(self, master):
        """Method to add the Isc label, entry and slider"""
        # Add scale slider and entry box for Voc.
        voc_volts_label = ttk.Label(master=master,
                                    text="Voc (volts):")
        voc_volts_entry = ttk.Entry(master=master,
                                    width=8,
                                    textvariable=self.voc_volts)
        voc_volts_entry.bind("<Return>", self.isc_and_voc_widget_actions)
        voc_volts_slider = ttk.Scale(master=master,
                                     length=SLIDER_LENGTH,
                                     from_=0.001,
                                     to=self.ivs2_sim.relay_max_volts,
                                     variable=self.voc_volts,
                                     command=self.round_voc_volts)
        voc_volts_slider.bind("<ButtonRelease-1>",
                              self.isc_and_voc_widget_actions)

        return voc_volts_label, voc_volts_entry, voc_volts_slider

    # -------------------------------------------------------------------------
    def add_choose_components_button(self, master):
        """Method to add the "Choose Optimal Components" button"""
        button = ttk.Button(master,
                            text="Choose Optimal Components",
                            command=self.choose_components_cmd)
        return button

    # -------------------------------------------------------------------------
    def add_r1_widgets(self, master):
        """Method to add the R1 label, entry and slider"""
        # Add scale slider and entry box for R1. The slider actually
        # chooses an index into the QTR_WATT_RESISTORS list, so the
        # choices are constrained to the real-world values. Similarly,
        # if a value is typed into the entry box, it is converted to the
        # closest value in QTR_WATT_RESISTORS. Each widget updates the
        # other so they are consistent.
        r1_ohms_label = ttk.Label(master=master,
                                  text="R1 (ohms):")
        r1_ohms_entry = ttk.Entry(master=master,
                                  width=8,
                                  textvariable=self.r1_ohms)
        r1_ohms_entry.bind("<Return>", self.r1_r2_rf_and_rg_widget_actions)
        r1_ohms_slider = ttk.Scale(master=master,
                                   length=SLIDER_LENGTH,
                                   from_=0,
                                   to=len(QTR_WATT_RESISTORS)-1,
                                   variable=self.r1_slider_index,
                                   command=self.update_r1_ohms)
        r1_ohms_slider.bind("<ButtonRelease-1>",
                            self.r1_r2_rf_and_rg_widget_actions)

        return r1_ohms_label, r1_ohms_entry, r1_ohms_slider

    # -------------------------------------------------------------------------
    def add_r2_widgets(self, master):
        """Method to add the R2 label, entry and slider"""
        r2_ohms_label = ttk.Label(master=master,
                                  text="R2 (ohms):")
        r2_ohms_entry = ttk.Entry(master=master,
                                  width=8,
                                  textvariable=self.r2_ohms)
        r2_ohms_entry.bind("<Return>", self.r1_r2_rf_and_rg_widget_actions)
        r2_ohms_slider = ttk.Scale(master=master,
                                   length=SLIDER_LENGTH,
                                   from_=0,
                                   to=len(QTR_WATT_RESISTORS)-1,
                                   variable=self.r2_slider_index,
                                   command=self.update_r2_ohms)
        r2_ohms_slider.bind("<ButtonRelease-1>",
                            self.r1_r2_rf_and_rg_widget_actions)

        return r2_ohms_label, r2_ohms_entry, r2_ohms_slider

    # -------------------------------------------------------------------------
    def add_rf_widgets(self, master):
        """Method to add the RF label, entry and slider"""
        rf_ohms_label = ttk.Label(master=master,
                                  text="RF (ohms):")
        rf_ohms_entry = ttk.Entry(master=master,
                                  width=8,
                                  textvariable=self.rf_ohms)
        rf_ohms_entry.bind("<Return>", self.r1_r2_rf_and_rg_widget_actions)
        rf_ohms_slider = ttk.Scale(master=master,
                                   length=SLIDER_LENGTH,
                                   from_=0,
                                   to=len(QTR_WATT_RESISTORS)-1,
                                   variable=self.rf_slider_index,
                                   command=self.update_rf_ohms)
        rf_ohms_slider.bind("<ButtonRelease-1>",
                            self.r1_r2_rf_and_rg_widget_actions)

        return rf_ohms_label, rf_ohms_entry, rf_ohms_slider

    # -------------------------------------------------------------------------
    def add_rg_widgets(self, master):
        """Method to add the RG label, entry and slider"""
        rg_ohms_label = ttk.Label(master=master,
                                  text="RG (ohms):")
        rg_ohms_entry = ttk.Entry(master=master,
                                  width=8,
                                  textvariable=self.rg_ohms)
        rg_ohms_entry.bind("<Return>", self.r1_r2_rf_and_rg_widget_actions)
        rg_ohms_slider = ttk.Scale(master=master,
                                   length=SLIDER_LENGTH,
                                   from_=0,
                                   to=len(QTR_WATT_RESISTORS)-1,
                                   variable=self.rg_slider_index,
                                   command=self.update_rg_ohms)
        rg_ohms_slider.bind("<ButtonRelease-1>",
                            self.r1_r2_rf_and_rg_widget_actions)

        return rg_ohms_label, rg_ohms_entry, rg_ohms_slider

    # -------------------------------------------------------------------------
    def add_shunt_widgets(self, master):
        """Method to add the shunt label, entries and slider"""
        shunt_ohms_label = ttk.Label(master=master,
                                     text="Shunt (ohms):")
        shunt_ohms_entry = ttk.Entry(master=master,
                                     width=8,
                                     textvariable=self.shunt_ohms)
        shunt_ohms_entry.bind("<Return>", self.shunt_ohms_widget_actions)
        shunt_ohms_slider = ttk.Scale(master=master,
                                      length=SLIDER_LENGTH,
                                      from_=0,
                                      to=len(SHUNT_RESISTORS)-1,
                                      variable=self.shunt_slider_index,
                                      command=self.update_shunt_values)
        shunt_ohms_slider.bind("<ButtonRelease-1>",
                               self.shunt_ohms_widget_actions)
        shunt_wattage_entry = ttk.Entry(master=master,
                                        width=6,
                                        textvariable=self.shunt_wattage)
        shunt_wattage_entry.bind("<Return>", self.update_shunt_wattage)
        shunt_wattage_label = ttk.Label(master=master,
                                        text=" W ")
        shunt_mfg_pn_entry = ttk.Entry(master=master,
                                       width=MFG_PN_ENTRY_WIDTH,
                                       textvariable=self.shunt_mfg_pn)
        shunt_mfg_pn_label = ttk.Label(master=master,
                                       text=" (P/N) ")

        return (shunt_ohms_label, shunt_ohms_entry, shunt_ohms_slider,
                shunt_wattage_entry, shunt_wattage_label, shunt_mfg_pn_entry,
                shunt_mfg_pn_label)

    # -------------------------------------------------------------------------
    def add_load_cap_widgets(self, master):
        """Method to add the load_cap label, entries and slider"""
        load_cap_uf_label = ttk.Label(master=master,
                                      text="C1, C2 (uF):")
        load_cap_uf_entry = ttk.Entry(master=master,
                                      width=8,
                                      textvariable=self.load_cap_uf)
        load_cap_uf_entry.bind("<Return>", self.load_cap_widget_actions)
        load_cap_uf_slider = ttk.Scale(master=master,
                                       length=SLIDER_LENGTH,
                                       from_=0,
                                       to=len(LOAD_CAPACITORS)-1,
                                       variable=self.load_cap_slider_index,
                                       command=self.update_load_cap_values)
        load_cap_uf_slider.bind("<ButtonRelease-1>",
                                self.load_cap_widget_actions)
        load_cap_v_entry = ttk.Entry(master=master,
                                     width=6,
                                     textvariable=self.load_cap_v)
        load_cap_v_entry.bind("<Return>", self.update_load_cap_v)
        load_cap_v_label = ttk.Label(master=master,
                                     text=" V ")
        load_cap_mfg_pn_entry = ttk.Entry(master=master,
                                          width=MFG_PN_ENTRY_WIDTH,
                                          textvariable=self.load_cap_mfg_pn)
        load_cap_mfg_pn_label = ttk.Label(master=master,
                                          text=" (P/N) ")

        return (load_cap_uf_label, load_cap_uf_entry, load_cap_uf_slider,
                load_cap_v_entry, load_cap_v_label,
                load_cap_mfg_pn_entry, load_cap_mfg_pn_label)

    # -------------------------------------------------------------------------
    def add_rb_widgets(self, master):
        """Method to add the Rb label, entries and slider"""
        rb_ohms_label = ttk.Label(master=master,
                                  text="Rb (ohms):")
        rb_ohms_entry = ttk.Entry(master=master,
                                  width=8,
                                  textvariable=self.rb_ohms)
        rb_ohms_entry.bind("<Return>", self.rb_widget_actions)
        rb_ohms_slider = ttk.Scale(master=master,
                                   length=SLIDER_LENGTH,
                                   from_=0,
                                   to=len(BLEED_RESISTORS)-1,
                                   variable=self.rb_slider_index,
                                   command=self.update_rb_values)
        rb_ohms_slider.bind("<ButtonRelease-1>", self.rb_widget_actions)
        rb_wattage_entry = ttk.Entry(master=master,
                                     width=6,
                                     textvariable=self.rb_wattage)
        rb_wattage_entry.bind("<Return>", self.update_rb_wattage)
        rb_wattage_label = ttk.Label(master=master,
                                     text=" W ")
        rb_mfg_pn_entry = ttk.Entry(master=master,
                                    width=MFG_PN_ENTRY_WIDTH,
                                    textvariable=self.rb_mfg_pn)
        rb_mfg_pn_label = ttk.Label(master=master,
                                    text=" (P/N) ")

        return (rb_ohms_label, rb_ohms_entry, rb_ohms_slider,
                rb_wattage_entry, rb_wattage_label, rb_mfg_pn_entry,
                rb_mfg_pn_label)

    # -------------------------------------------------------------------------
    def add_simulate_button(self, master):
        """Method to add the "Simulate" button"""
        style = ttk.Style()
        style.configure("simulate_button.TButton",
                        foreground="red",
                        padding=4,
                        font="TkDefaultFont 19 bold italic")
        button = ttk.Button(master,
                            text="Simulate",
                            command=self.simulate_button_actions)
        button["style"] = "simulate_button.TButton"
        return button

    # -------------------------------------------------------------------------
    def restore_component_defaults(self, event=None):
        """Method to restore component values on the Main Controls tab to
           defaults. Note that the relay type, Isc and Voc values are
           not affected.
        """
        # pylint: disable=unused-argument
        self.restore_r1_r2_rf_rg_defaults()
        self.restore_shunt_ohms_defaults()
        self.restore_load_cap_defaults()
        self.restore_rb_defaults()

    # -------------------------------------------------------------------------
    def restore_r1_r2_rf_rg_defaults(self):
        """Method to restore R1, R2, Rf and Rg values on the Main Controls tab
           to defaults.
        """
        self.r1_ohms.set(str(R1_DEFAULT))
        self.r2_ohms.set(str(R2_DEFAULT))
        self.rf_ohms.set(str(RF_DEFAULT))
        self.rg_ohms.set(str(RG_DEFAULT))
        self.r1_r2_rf_and_rg_widget_actions()

    # -------------------------------------------------------------------------
    def restore_shunt_ohms_defaults(self):
        """Method to restore R1, R2, Rf and Rg values on the Main Controls tab
           to defaults.
        """
        self.shunt_ohms.set(str(SHUNT_DEFAULT / 1000000.0))
        self.shunt_wattage.set(SHUNT_WATTAGE_DEFAULT)
        self.shunt_mfg_pn.set(SHUNT_MFG_PN_DEFAULT)
        self.shunt_ohms_widget_actions()

    # -------------------------------------------------------------------------
    def restore_load_cap_defaults(self):
        """Method to restore R1, R2, Rf and Rg values on the Main Controls tab
           to defaults.
        """
        self.load_cap_uf.set(str(LOAD_CAP_UF_DEFAULT))
        self.load_cap_v.set(LOAD_CAP_V_DEFAULT)
        self.load_cap_mfg_pn.set(LOAD_CAP_MFG_PN_DEFAULT)
        self.load_cap_widget_actions()

    # -------------------------------------------------------------------------
    def restore_rb_defaults(self):
        """Method to restore R1, R2, Rf and Rg values on the Main Controls tab
           to defaults.
        """
        self.rb_ohms.set(str(RB_OHMS_DEFAULT))
        self.rb_wattage.set(RB_WATTAGE_DEFAULT)
        self.rb_mfg_pn.set(RB_MFG_PN_DEFAULT)
        self.rb_widget_actions()

    # -------------------------------------------------------------------------
    def show_simulator_help(self):
        """Method to display simulator help"""
        SimulatorHelpDialog(self)

    # -------------------------------------------------------------------------
    def populate_other_controls_tab(self):
        """Method to add widgets to the Other Controls tab"""
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-statements

        # Add container box for widgets
        other_controls_widget_box = ttk.Frame(master=self.other_controls_tab,
                                              padding=20)

        master = other_controls_widget_box

        # Add B coefficient per Voc label and entry widgets
        b_coeff_per_voc_label = ttk.Label(master=master,
                                          text="B coeff per Voc ")
        textvar = self.b_coeff_per_voc
        b_coeff_per_voc_entry = ttk.Entry(master=master,
                                          width=8,
                                          textvariable=textvar)
        b_coeff_per_voc_entry.bind("<Return>", self.other_entries_actions)

        # Add microseconds per point label and entry widgets
        us_per_point_label = ttk.Label(master=master, text="us per point ")
        textvar = self.us_per_point
        us_per_point_entry = ttk.Entry(master=master,
                                       width=8,
                                       textvariable=textvar)
        us_per_point_entry.bind("<Return>", self.other_entries_actions)

        # Add # synthesized points label and entry widgets
        num_synth_points_label = ttk.Label(master=master,
                                           text="# synthesized points ")
        textvar = self.num_synth_points
        num_synth_points_entry = ttk.Entry(master=master,
                                           width=8,
                                           textvariable=textvar)
        num_synth_points_entry.bind("<Return>", self.other_entries_actions)

        # Add # load caps label and entry widgets
        num_load_caps_label = ttk.Label(master=master, text="# load caps ")
        textvar = self.num_load_caps
        num_load_caps_entry = ttk.Entry(master=master,
                                        width=8,
                                        textvariable=textvar)
        num_load_caps_entry.bind("<Return>", self.other_entries_actions)

        # Add done CH1 ADC label and entry widgets
        done_ch1_adc_label = ttk.Label(master=master, text="Done CH1 ADC ")
        textvar = self.done_ch1_adc
        done_ch1_adc_entry = ttk.Entry(master=master,
                                       width=8,
                                       textvariable=textvar)
        done_ch1_adc_entry.bind("<Return>", self.other_entries_actions)

        # Add wire ohms label and entry widgets
        wire_ohms_label = ttk.Label(master=master, text="Wire ohms ")
        textvar = self.wire_ohms
        wire_ohms_entry = ttk.Entry(master=master,
                                    width=8,
                                    textvariable=textvar)
        wire_ohms_entry.bind("<Return>", self.other_entries_actions)

        # Add EMR ohms label and entry widgets
        emr_ohms_label = ttk.Label(master=master, text="EMR ohms ")
        textvar = self.emr_ohms
        emr_ohms_entry = ttk.Entry(master=master,
                                   width=8,
                                   textvariable=textvar)
        emr_ohms_entry.bind("<Return>", self.other_entries_actions)

        # Add SSR ohms label and entry widgets
        ssr_ohms_label = ttk.Label(master=master, text="SSR ohms ")
        textvar = self.ssr_ohms
        ssr_ohms_entry = ttk.Entry(master=master,
                                   width=8,
                                   textvariable=textvar)
        ssr_ohms_entry.bind("<Return>", self.other_entries_actions)

        # Add optimization percent headroom label and entry widgets
        opt_pct_headroom_label = ttk.Label(master=master,
                                           text="Optimization headroom % ")
        textvar = self.opt_pct_headroom
        opt_pct_headroom_entry = ttk.Entry(master=master,
                                           width=8,
                                           textvariable=textvar)
        opt_pct_headroom_entry.bind("<Return>", self.other_entries_actions)

        # Add capacitor voltage derate percent label and entry widgets
        text = "C1,C2 voltage derate % "
        cap_voltage_derate_pct_label = ttk.Label(master=master, text=text)
        textvar = self.cap_voltage_derate_pct
        cap_voltage_derate_pct_entry = ttk.Entry(master=master,
                                                 width=8,
                                                 textvariable=textvar)
        cap_voltage_derate_pct_entry.bind("<Return>",
                                          self.other_entries_actions)

        # Add max voltage divider current label and entry widgets
        max_vdiv_current_label = ttk.Label(master=master,
                                           text="Max R1,R2 current ")
        textvar = self.max_vdiv_current
        max_vdiv_current_entry = ttk.Entry(master=master,
                                           width=8,
                                           textvariable=textvar)
        max_vdiv_current_entry.bind("<Return>", self.other_entries_actions)

        # Add op amp max drive current label and entry widgets
        text = "Op amp max drive current "
        op_amp_max_drive_current_label = ttk.Label(master=master, text=text)
        textvar = self.op_amp_max_drive_current
        op_amp_max_drive_current_entry = ttk.Entry(master=master,
                                                   width=8,
                                                   textvariable=textvar)
        op_amp_max_drive_current_entry.bind("<Return>",
                                            self.other_entries_actions)

        # Add op amp max input current label and entry widgets
        text = "Op amp max input current "
        op_amp_max_input_current_label = ttk.Label(master=master, text=text)
        textvar = self.op_amp_max_input_current
        op_amp_max_input_current_entry = ttk.Entry(master=master,
                                                   width=8,
                                                   textvariable=textvar)
        op_amp_max_input_current_entry.bind("<Return>",
                                            self.other_entries_actions)

        # Add target op amp gain label and entry widgets
        target_amm_op_amp_gain_label = ttk.Label(master=master,
                                                 text="Target gain ")
        textvar = self.target_amm_op_amp_gain
        target_amm_op_amp_gain_entry = ttk.Entry(master=master,
                                                 width=8,
                                                 textvariable=textvar)
        target_amm_op_amp_gain_entry.bind("<Return>",
                                          self.other_entries_actions)

        # Add target max swing microseconds label and entry widgets
        target_max_swing_us_label = ttk.Label(master=master,
                                              text="Target max swing us ")
        textvar = self.target_max_swing_us
        target_max_swing_us_entry = ttk.Entry(master=master,
                                              width=8,
                                              textvariable=textvar)
        target_max_swing_us_entry.bind("<Return>", self.other_entries_actions)

        # Add target bleed RC constant microseconds label and entry widgets
        target_bleed_rc_us_label = ttk.Label(master=master,
                                             text="Target bleed RC us ")
        textvar = self.target_bleed_rc_us
        target_bleed_rc_us_entry = ttk.Entry(master=master,
                                             width=8,
                                             textvariable=textvar)
        target_bleed_rc_us_entry.bind("<Return>", self.other_entries_actions)

        # Add Restore Defaults button
        restore_cmd = self.restore_other_controls_defaults
        restore_button = ttk.Button(master=self.other_controls_tab,
                                    text="Restore Defaults",
                                    command=restore_cmd)
        # Layout
        pady = 8
        other_controls_widget_box.grid(column=0, row=0, sticky=W, columnspan=2)
        pady = 8
        row = 0
        b_coeff_per_voc_label.grid(column=0, row=row, sticky=E)
        b_coeff_per_voc_entry.grid(column=1, row=row, sticky=W)
        row += 1
        us_per_point_label.grid(column=0, row=row, sticky=E)
        us_per_point_entry.grid(column=1, row=row, sticky=W)
        row += 1
        num_synth_points_label.grid(column=0, row=row, sticky=E)
        num_synth_points_entry.grid(column=1, row=row, sticky=W)
        row += 1
        num_load_caps_label.grid(column=0, row=row, sticky=E)
        num_load_caps_entry.grid(column=1, row=row, sticky=W)
        row += 1
        done_ch1_adc_label.grid(column=0, row=row, sticky=E)
        done_ch1_adc_entry.grid(column=1, row=row, sticky=W)
        row += 1
        wire_ohms_label.grid(column=0, row=row, sticky=E)
        wire_ohms_entry.grid(column=1, row=row, sticky=W)
        row += 1
        emr_ohms_label.grid(column=0, row=row, sticky=E)
        emr_ohms_entry.grid(column=1, row=row, sticky=W)
        row += 1
        ssr_ohms_label.grid(column=0, row=row, sticky=E)
        ssr_ohms_entry.grid(column=1, row=row, sticky=W)
        row += 1
        ttk.Label(other_controls_widget_box, text=" ").grid(column=0, row=row)
        row += 1
        ttk.Separator(other_controls_widget_box).grid(row=row, columnspan=9,
                                                      sticky="ew")
        row += 1
        ttk.Label(other_controls_widget_box, text=" ").grid(column=0, row=row)
        row += 1
        opt_pct_headroom_label.grid(column=0, row=row, sticky=E)
        opt_pct_headroom_entry.grid(column=1, row=row, sticky=W)
        row += 1
        cap_voltage_derate_pct_label.grid(column=0, row=row, sticky=E)
        cap_voltage_derate_pct_entry.grid(column=1, row=row, sticky=W)
        row += 1
        max_vdiv_current_label.grid(column=0, row=row, sticky=E)
        max_vdiv_current_entry.grid(column=1, row=row, sticky=W)
        row += 1
        op_amp_max_drive_current_label.grid(column=0, row=row, sticky=E)
        op_amp_max_drive_current_entry.grid(column=1, row=row, sticky=W)
        row += 1
        op_amp_max_input_current_label.grid(column=0, row=row, sticky=E)
        op_amp_max_input_current_entry.grid(column=1, row=row, sticky=W)
        row += 1
        target_amm_op_amp_gain_label.grid(column=0, row=row, sticky=E)
        target_amm_op_amp_gain_entry.grid(column=1, row=row, sticky=W)
        row += 1
        target_max_swing_us_label.grid(column=0, row=row, sticky=E)
        target_max_swing_us_entry.grid(column=1, row=row, sticky=W)
        row += 1
        target_bleed_rc_us_label.grid(column=0, row=row, sticky=E)
        target_bleed_rc_us_entry.grid(column=1, row=row, sticky=W)

        restore_button.grid(column=1, row=2, sticky=W,
                            pady=pady, columnspan=2)

    # -------------------------------------------------------------------------
    def other_entries_actions(self, event=None):
        """Callback method that sets simulator properties to the values in the
           entries on the Other Controls tab
        """
        # pylint: disable=unused-argument
        widget_get_val = float(self.b_coeff_per_voc.get())
        self.ivs2_sim.b_coeff_per_voc = widget_get_val
        widget_get_val = float(self.us_per_point.get())
        self.ivs2_sim.us_per_point = widget_get_val
        widget_get_val = int(self.num_synth_points.get())
        self.ivs2_sim.num_synth_points = widget_get_val
        widget_get_val = float(self.num_load_caps.get())
        self.ivs2_sim.num_load_caps = widget_get_val
        widget_get_val = float(self.done_ch1_adc.get())
        self.ivs2_sim.done_ch1_adc = widget_get_val
        widget_get_val = float(self.wire_ohms.get())
        self.ivs2_sim.wire_ohms = widget_get_val
        widget_get_val = float(self.emr_ohms.get())
        self.ivs2_sim.emr_ohms = widget_get_val
        widget_get_val = float(self.ssr_ohms.get())
        self.ivs2_sim.ssr_ohms = widget_get_val
        widget_get_val = float(self.opt_pct_headroom.get())
        self.ivs2_sim.opt_pct_headroom = widget_get_val
        widget_get_val = float(self.cap_voltage_derate_pct.get())
        self.ivs2_sim.cap_voltage_derate_pct = widget_get_val
        widget_get_val = float(self.max_vdiv_current.get())
        self.ivs2_sim.max_vdiv_current = widget_get_val
        widget_get_val = float(self.op_amp_max_drive_current.get())
        self.ivs2_sim.op_amp_max_drive_current = widget_get_val
        widget_get_val = float(self.op_amp_max_input_current.get())
        self.ivs2_sim.op_amp_max_input_current = widget_get_val
        widget_get_val = float(self.target_amm_op_amp_gain.get())
        self.ivs2_sim.target_amm_op_amp_gain = widget_get_val
        widget_get_val = float(self.target_max_swing_us.get())
        self.ivs2_sim.target_max_swing_us = widget_get_val
        widget_get_val = float(self.target_bleed_rc_us.get())
        self.ivs2_sim.target_bleed_rc_us = widget_get_val

    # -------------------------------------------------------------------------
    def restore_other_controls_defaults(self, event=None):
        """Method to restore Other Controls tab values to defaults"""
        # pylint: disable=unused-argument
        self.b_coeff_per_voc.set(str(B_COEFF_PER_VOC_DEFAULT))
        self.us_per_point.set(str(US_PER_POINT_DEFAULT))
        self.num_synth_points.set(str(NUM_SYNTH_POINTS_DEFAULT))
        self.num_load_caps.set(str(NUM_LOAD_CAPS_DEFAULT))
        self.done_ch1_adc.set(str(DONE_CH1_ADC_DEFAULT))
        self.wire_ohms.set(str(WIRE_OHMS_DEFAULT))
        self.emr_ohms.set(str(EMR_OHMS_DEFAULT))
        self.ssr_ohms.set(str(SSR_OHMS_DEFAULT))
        self.opt_pct_headroom.set(str(OPT_PCT_HEADROOM_DEFAULT))
        self.cap_voltage_derate_pct.set(str(CAP_VOLTAGE_DERATE_PCT_DEFAULT))
        self.max_vdiv_current.set(str(MAX_VDIV_CURRENT_DEFAULT))
        widget_set_val = str(OP_AMP_MAX_DRIVE_CURRENT_DEFAULT)
        self.op_amp_max_drive_current.set(widget_set_val)
        widget_set_val = str(OP_AMP_MAX_INPUT_CURRENT_DEFAULT)
        self.op_amp_max_input_current.set(widget_set_val)
        self.target_amm_op_amp_gain.set(str(TARGET_AMM_OP_AMP_GAIN_DEFAULT))
        self.target_max_swing_us.set(str(TARGET_MAX_SWING_US_DEFAULT))
        self.target_bleed_rc_us.set(str(TARGET_BLEED_RC_US_DEFAULT))
        self.other_entries_actions()

    # -------------------------------------------------------------------------
    def populate_results_tab(self):
        """Method to add widgets to the Results tab"""

        # Add container box for ScrolledText widget
        results_widget_box = ttk.Frame(master=self.results_tab, padding=20)

        # Results ScrolledText widget
        font = "Arial"
        results_text = ScrolledText(results_widget_box, height=35,
                                    borderwidth=10)
        results_text.tag_configure("body_tag", font=font)
        results_text.tag_configure("heading_tag", font=font, underline=True)
        results_text.insert("end", self.ivs2_sim.results_text, ("body_tag"))
        results_text.pack(fill=BOTH, expand=True)

        # Layout
        results_widget_box.grid(column=0, row=0, sticky=W, columnspan=2)
        results_text.pack(fill=BOTH, expand=True)

    # -------------------------------------------------------------------------
    def update_relay_type(self, event=None):
        """Callback method to update the relay type when the user changes the
           value using the radio buttons.
        """
        # pylint: disable=unused-argument
        self.ivs2_sim.relay_type = self.relay_type.get()
        self.isc_amps_slider["to"] = self.ivs2_sim.relay_max_amps
        self.voc_volts_slider["to"] = self.ivs2_sim.relay_max_volts

    # -------------------------------------------------------------------------
    def update_shunt_wattage(self, event=None):
        """Callback method to update the shunt wattage when the user changes
           the value in the entry. If the resistance is included in
           SHUNT_RESISTORS but the wattage is different, the
           manufacturer partnumber is set to "Unknown".
        """
        # pylint: disable=unused-argument
        self.validate_shunt()
        self.ivs2_sim.shunt_wattage = float(self.shunt_wattage.get())
        shunt_resistance = self.ivs2_sim.amm_shunt_resistance
        shunt_index = shunt_index_from_ohms(shunt_resistance)
        if shunt_resistance in [shunt[0] for shunt in SHUNT_RESISTORS]:
            if self.ivs2_sim.shunt_wattage == SHUNT_RESISTORS[shunt_index][1]:
                self.ivs2_sim.shunt_mfg_pn = SHUNT_RESISTORS[shunt_index][2]
                self.shunt_mfg_pn.set(self.ivs2_sim.shunt_mfg_pn)
            else:
                self.ivs2_sim.shunt_mfg_pn = "Unknown"
                self.shunt_mfg_pn.set("Unknown")

    # -------------------------------------------------------------------------
    def update_load_cap_v(self, event=None):
        """Callback method to update the load cap voltage when the user changes
           the value in the entry. If the capacitance is included in
           LOAD_CAPACITORS but the voltage is different, the
           manufacturer partnumber is set to "Unknown".
        """
        # pylint: disable=unused-argument
        self.validate_load_cap()
        self.ivs2_sim.load_cap_v = float(self.load_cap_v.get())
        load_cap_uf = self.ivs2_sim.load_cap_uf
        index = load_cap_index_from_uf(load_cap_uf)
        if load_cap_uf in [load_cap[0] for load_cap in LOAD_CAPACITORS]:
            if self.ivs2_sim.load_cap_v == LOAD_CAPACITORS[index][1]:
                self.ivs2_sim.load_cap_mfg_pn = LOAD_CAPACITORS[index][4]
                self.load_cap_mfg_pn.set(self.ivs2_sim.load_cap_mfg_pn)
            else:
                self.ivs2_sim.load_cap_mfg_pn = "Unknown"
                self.load_cap_mfg_pn.set("Unknown")

    # -------------------------------------------------------------------------
    def update_rb_wattage(self, event=None):
        """Callback method to update the Rb wattage when the user changes the
           value in the entry. If the resistance is included in
           BLEED_RESISTORS but the wattage is different, the
           manufacturer partnumber is set to "Unknown".
        """
        # pylint: disable=unused-argument
        self.validate_rb()
        self.ivs2_sim.rb_wattage = float(self.rb_wattage.get())
        rb_resistance = self.ivs2_sim.rb_ohms
        rb_index = rb_index_from_ohms(rb_resistance)
        if rb_resistance in [rb[0] for rb in BLEED_RESISTORS]:
            if self.ivs2_sim.rb_wattage == BLEED_RESISTORS[rb_index][1]:
                self.ivs2_sim.rb_mfg_pn = BLEED_RESISTORS[rb_index][2]
                self.rb_mfg_pn.set(self.ivs2_sim.rb_mfg_pn)
            else:
                self.ivs2_sim.rb_mfg_pn = "Unknown"
                self.rb_mfg_pn.set("Unknown")

    # -------------------------------------------------------------------------
    def update_all_widgets(self, event=None):
        """Method to update all of the widgets and their associated properties
        """
        # Relay type, Isc, Voc
        self.isc_and_voc_widget_actions(event)
        # R1, R2, Rf, Rg
        self.r1_r2_rf_and_rg_widget_actions(event)
        # Shunt
        self.shunt_ohms_widget_actions(event)
        # Load caps
        self.load_cap_widget_actions(event)
        # Rb
        self.rb_widget_actions(event)
        # All values on Other Controls tab
        self.other_entries_actions(event)

    # -------------------------------------------------------------------------
    def isc_and_voc_widget_actions(self, event=None):
        """Callback method for the Isc and Voc entries and sliders. Update the
           relay_type, sim_isc and sim_voc simulator properties based on
           the widget values
        """
        # pylint: disable=unused-argument
        self.ivs2_sim.relay_type = self.relay_type.get()
        self.validate_isc_and_voc()
        self.ivs2_sim.sim_isc = float(self.isc_amps.get())
        self.ivs2_sim.sim_voc = float(self.voc_volts.get())

    # -------------------------------------------------------------------------
    def choose_components_cmd(self, event=None):
        """Callback method for the choose optimal components button.
        """
        # pylint: disable=unused-argument

        # First make sure Isc, Voc and values in entries on the "Other
        # Controls" tab are captured (in case user did not hit Return)
        self.isc_and_voc_widget_actions()
        self.other_entries_actions()

        # Call simulator method
        rc = self.ivs2_sim.choose_optimal_components()
        if rc != RC_SUCCESS:
            err_msg = "Oops. Something went wrong\n"
            err_msg += "See log file for details."
            tkmsg.showerror(message=err_msg)
            IV_Swinger2.sys_view_file(self.ivs2_sim.logger.log_file_name)
            return

        # Update widgets with new values
        self.set_widget_vars_from_props()

    # -------------------------------------------------------------------------
    def r1_r2_rf_and_rg_widget_actions(self, event=None):
        """Callback method for the R1, R2, Rf and Rg entries and sliders.
           First validate the values. Then update the vdiv_r1, vdiv_r2,
           amm_op_amp_rf and amm_op_amp_rg simulator properties based on
           the widget values. The slider index variables are also
           updated to agree.
        """
        # pylint: disable=unused-argument
        # R1, R2, Rf, Rg
        self.validate_r1_r2_rf_and_rg()
        self.ivs2_sim.vdiv_r1 = float(self.r1_ohms.get())
        self.ivs2_sim.vdiv_r2 = float(self.r2_ohms.get())
        self.ivs2_sim.amm_op_amp_rf = float(self.rf_ohms.get())
        self.ivs2_sim.amm_op_amp_rg = float(self.rg_ohms.get())
        self.r1_slider_index.set(index_from_ohms(self.ivs2_sim.vdiv_r1))
        self.r2_slider_index.set(index_from_ohms(self.ivs2_sim.vdiv_r2))
        self.rf_slider_index.set(index_from_ohms(self.ivs2_sim.amm_op_amp_rf))
        self.rg_slider_index.set(index_from_ohms(self.ivs2_sim.amm_op_amp_rg))

    # -------------------------------------------------------------------------
    def shunt_ohms_widget_actions(self, event=None):
        """Callback method for the shunt ohms entry and slider. The shunt
           resistance simulator property is updated based on the widget
           values. The slider index variable is also updated to
           agree. Additionally, if there is a shunt with the specified
           resistance in the SHUNT_RESISTORS list, its wattage and
           manufacturer part number are used to set the associated
           simulator properties, and their entry widget variables are
           set accordingly.
        """
        # pylint: disable=unused-argument
        shunt_resistance_changed = False
        if self.ivs2_sim.amm_shunt_resistance != float(self.shunt_ohms.get()):
            shunt_resistance_changed = True
        self.validate_shunt()
        self.ivs2_sim.amm_shunt_max_volts = (self.ivs2_sim.amm_shunt_max_amps *
                                             float(self.shunt_ohms.get()))
        shunt_resistance = self.ivs2_sim.amm_shunt_resistance
        shunt_index = shunt_index_from_ohms(shunt_resistance)
        self.shunt_slider_index.set(shunt_index)
        if shunt_resistance in [shunt[0] for shunt in SHUNT_RESISTORS]:
            self.ivs2_sim.shunt_wattage = SHUNT_RESISTORS[shunt_index][1]
            self.ivs2_sim.shunt_mfg_pn = SHUNT_RESISTORS[shunt_index][2]
            self.shunt_wattage.set(self.ivs2_sim.shunt_wattage)
            self.shunt_mfg_pn.set(self.ivs2_sim.shunt_mfg_pn)
        elif shunt_resistance_changed:
            self.ivs2_sim.shunt_mfg_pn = "Unknown"
            self.shunt_mfg_pn.set("Unknown")
        else:
            self.ivs2_sim.shunt_mfg_pn = self.shunt_mfg_pn.get()

    # -------------------------------------------------------------------------
    def load_cap_widget_actions(self, event=None):
        """Callback method for the load capacitor entry and slider. The load
           capacitance simulator property is updated based on the widget
           values. The slider index variable is also updated to
           agree. Additionally, if there is a capacitor with the
           specified capacitance in the LOAD_CAPACITORS list, its
           voltage and manufacturer part number are used to set the
           associated simulator properties, and their entry widget
           variables are set accordingly.

           Finally, an appropriate bleed resistor is chosen. This choice
           can be overridden by the user. But the idea is that in most
           cases, the bleed resistor choice should be based on the load
           capacitance and the user shouldn't have to make this choice
           even if they are manually choosing the other components.
        """
        # pylint: disable=unused-argument
        load_capacitance_changed = False
        if self.ivs2_sim.load_cap_uf != float(self.load_cap_uf.get()):
            load_capacitance_changed = True
        self.ivs2_sim.load_cap_uf = float(self.load_cap_uf.get())
        load_cap_index = load_cap_index_from_uf(self.ivs2_sim.load_cap_uf)
        # Load cap slider is in opposite order from LOAD_CAPACITORS
        self.load_cap_slider_index.set(len(LOAD_CAPACITORS)-load_cap_index-1)
        if self.ivs2_sim.load_cap_uf in [cap[0] for cap in LOAD_CAPACITORS]:
            self.ivs2_sim.load_cap_v = LOAD_CAPACITORS[load_cap_index][1]
            self.ivs2_sim.load_cap_mfg_pn = LOAD_CAPACITORS[load_cap_index][4]
            self.load_cap_v.set(self.ivs2_sim.load_cap_v)
            self.load_cap_mfg_pn.set(self.ivs2_sim.load_cap_mfg_pn)
        elif load_capacitance_changed:
            self.ivs2_sim.load_cap_mfg_pn = "Unknown"
            self.load_cap_mfg_pn.set("Unknown")
        else:
            self.ivs2_sim.load_cap_mfg_pn = self.load_cap_mfg_pn.get()
        if load_capacitance_changed:
            # Choose the bleed resistor that best matches the load
            # capacitance
            self.ivs2_sim.choose_optimal_rb()
            self.set_rb_vars_from_props()

    # -------------------------------------------------------------------------
    def rb_widget_actions(self, event=None):
        """Callback method for the Rb ohms entry and slider. The Rb ohms
           simulator property is updated based on the widget values. The
           slider index variable is also updated to agree. Additionally,
           if there is a bleed resistor with the specified resistance in
           the BLEED_RESISTORS list, its wattage and manufacturer part
           number are used to set the associated simulator properties,
           and their entry widget variables are set accordingly.

        """
        # pylint: disable=unused-argument
        rb_ohms_changed = False
        if self.ivs2_sim.rb_ohms != float(self.rb_ohms.get()):
            rb_ohms_changed = True
        self.validate_rb()
        self.ivs2_sim.rb_ohms = float(self.rb_ohms.get())
        rb_index = rb_index_from_ohms(self.ivs2_sim.rb_ohms)
        self.rb_slider_index.set(rb_index)
        if self.ivs2_sim.rb_ohms in [rb[0] for rb in BLEED_RESISTORS]:
            self.ivs2_sim.rb_wattage = BLEED_RESISTORS[rb_index][1]
            self.ivs2_sim.rb_mfg_pn = BLEED_RESISTORS[rb_index][2]
            self.rb_wattage.set(self.ivs2_sim.rb_wattage)
            self.rb_mfg_pn.set(self.ivs2_sim.rb_mfg_pn)
        elif rb_ohms_changed:
            self.ivs2_sim.rb_mfg_pn = "Unknown"
            self.rb_mfg_pn.set("Unknown")
        else:
            self.ivs2_sim.rb_mfg_pn = self.rb_mfg_pn.get()

    # -------------------------------------------------------------------------
    def validate_isc_and_voc(self):
        """Method to check that the Isc and Voc values entered are legal and
           convert integers to floats.
        """
        try:
            isc_amps = float(self.isc_amps.get())
            if isc_amps <= 0.0 or isc_amps > self.ivs2_sim.relay_max_amps:
                raise ValueError
            self.isc_amps.set(isc_amps)
        except ValueError:
            self.isc_amps.set(self.ivs2_sim.sim_isc)
            err_msg = "Invalid value for Isc amps.\n"
            err_msg += "Must be positive number, no greater\n"
            err_msg += ("than relay limit of {}"
                        .format(self.ivs2_sim.relay_max_amps))
            tkmsg.showerror(message=err_msg)
        # Voc
        try:
            voc_volts = float(self.voc_volts.get())
            if voc_volts <= 0.0 or voc_volts > self.ivs2_sim.relay_max_volts:
                raise ValueError
            self.voc_volts.set(voc_volts)
        except ValueError:
            self.voc_volts.set(self.ivs2_sim.sim_voc)
            err_msg = "Invalid value for Voc volts.\n"
            err_msg += "Must be positive number, no greater\n"
            err_msg += ("than relay limit of {}"
                        .format(self.ivs2_sim.relay_max_volts))
            tkmsg.showerror(message=err_msg)

    # -------------------------------------------------------------------------
    def validate_r1_r2_rf_and_rg(self):
        """Method to check that the R1, R2, Rf and Rg values entered are legal
           and convert integers to floats.
        """
        # R1
        try:
            r1_ohms = float(self.r1_ohms.get())
            if r1_ohms < 0.0:
                raise ValueError
            self.r1_ohms.set(r1_ohms)
        except ValueError:
            self.r1_ohms.set(self.ivs2_sim.vdiv_r1)
            err_msg = "Invalid value for R1 ohms.\n"
            err_msg += "Must be number, zero or larger."
            tkmsg.showerror(message=err_msg)
        # R2
        try:
            r2_ohms = float(self.r2_ohms.get())
            if r2_ohms <= 0.0:
                raise ValueError
            self.r2_ohms.set(r2_ohms)
        except ValueError:
            self.r2_ohms.set(self.ivs2_sim.vdiv_r2)
            err_msg = "Invalid value for R2 ohms.\n"
            err_msg += "Must be positive number."
            tkmsg.showerror(message=err_msg)
        # RF
        try:
            rf_ohms = float(self.rf_ohms.get())
            if rf_ohms < 0.0:
                raise ValueError
            self.rf_ohms.set(rf_ohms)
        except ValueError:
            self.rf_ohms.set(self.ivs2_sim.amm_op_amp_rf)
            err_msg = "Invalid value for Rf ohms.\n"
            err_msg += "Must be number, zero or larger."
            tkmsg.showerror(message=err_msg)
        # RG
        try:
            rg_ohms = float(self.rg_ohms.get())
            if rg_ohms <= 0.0:
                raise ValueError
            self.rg_ohms.set(rg_ohms)
        except ValueError:
            self.rg_ohms.set(self.ivs2_sim.amm_op_amp_rg)
            err_msg = "Invalid value for Rg ohms.\n"
            err_msg += "Must be positive number."
            tkmsg.showerror(message=err_msg)

    # -------------------------------------------------------------------------
    def validate_shunt(self):
        """Method to check that the shunt values entered are legal and convert
           integers to floats.
        """
        try:
            shunt_ohms = float(self.shunt_ohms.get())
            if shunt_ohms < 0.0:
                raise ValueError
            self.shunt_ohms.set(shunt_ohms)
        except ValueError:
            self.shunt_ohms.set(self.ivs2_sim.amm_shunt_resistance)
            err_msg = "Invalid value for shunt ohms.\n"
            err_msg += "Must be number, zero or larger."
            tkmsg.showerror(message=err_msg)
        try:
            shunt_wattage = float(self.shunt_wattage.get())
            if shunt_wattage < 0.0:
                raise ValueError
            self.shunt_wattage.set(shunt_wattage)
        except ValueError:
            self.shunt_wattage.set(self.ivs2_sim.shunt_wattage)
            err_msg = "Invalid value for shunt wattage.\n"
            err_msg += "Must be number, zero or larger."
            tkmsg.showerror(message=err_msg)

    # -------------------------------------------------------------------------
    def validate_load_cap(self):
        """Method to check that the load cap values entered are legal and
           convert integers to floats.
        """
        try:
            load_cap_uf = float(self.load_cap_uf.get())
            if load_cap_uf < 0.0:
                raise ValueError
            self.load_cap_uf.set(load_cap_uf)
        except ValueError:
            self.load_cap_uf.set(self.ivs2_sim.load_cap_uf)
            err_msg = "Invalid value for load capacitance.\n"
            err_msg += "Must be number, zero or larger."
            tkmsg.showerror(message=err_msg)
        try:
            load_cap_v = float(self.load_cap_v.get())
            if load_cap_v < 0.0:
                raise ValueError
            self.load_cap_v.set(load_cap_v)
        except ValueError:
            self.load_cap_v.set(self.ivs2_sim.load_cap_v)
            err_msg = "Invalid value for load cap voltage.\n"
            err_msg += "Must be number, zero or larger."
            tkmsg.showerror(message=err_msg)

    # -------------------------------------------------------------------------
    def validate_rb(self):
        """Method to check that the Rb values entered are legal and convert
           integers to floats.
        """
        try:
            rb_ohms = float(self.rb_ohms.get())
            if rb_ohms < 0.0:
                raise ValueError
            self.rb_ohms.set(rb_ohms)
        except ValueError:
            self.rb_ohms.set(self.ivs2_sim.rb_ohms)
            err_msg = "Invalid value for Rb ohms.\n"
            err_msg += "Must be number, zero or larger."
            tkmsg.showerror(message=err_msg)
        try:
            rb_wattage = float(self.rb_wattage.get())
            if rb_wattage < 0.0:
                raise ValueError
            self.rb_wattage.set(rb_wattage)
        except ValueError:
            self.rb_wattage.set(self.ivs2_sim.rb_wattage)
            err_msg = "Invalid value for Rb wattage.\n"
            err_msg += "Must be number, zero or larger."
            tkmsg.showerror(message=err_msg)

    # -------------------------------------------------------------------------
    def round_isc_amps(self, event=None):
        """Callback method to emulate a resolution of 0.5 for Isc slider (no
           resolution option in ttk Scale class)
        """
        # pylint: disable=unused-argument
        new_val = round(2.0*float(self.isc_amps.get()))/2.0
        if new_val == 0.0:
            new_val = 0.001
        self.isc_amps.set(str(new_val))

    # -------------------------------------------------------------------------
    def round_voc_volts(self, event=None):
        """Callback method to emulate a resolution of 0.5 for Voc slider (no
           resolution option in ttk Scale class)
        """
        # pylint: disable=unused-argument
        new_val = round(2.0*float(self.voc_volts.get()))/2.0
        if new_val == 0.0:
            new_val = 0.001
        self.voc_volts.set(str(new_val))

    # -------------------------------------------------------------------------
    def update_r1_ohms(self, event=None):
        """Callback method to update the r1_ohms widget variable based on the
           slider index widget variable. The simulator property is not
           updated by this method.
        """
        # pylint: disable=unused-argument
        slider_index = int(float(self.r1_slider_index.get()))
        self.r1_ohms.set(str(QTR_WATT_RESISTORS[slider_index]))

    # -------------------------------------------------------------------------
    def update_r2_ohms(self, event=None):
        """Callback method to update the r2_ohms widget variable based on the
           slider index widget variable. The simulator property is not
           updated by this method.
        """
        # pylint: disable=unused-argument
        slider_index = int(float(self.r2_slider_index.get()))
        self.r2_ohms.set(str(QTR_WATT_RESISTORS[slider_index]))

    # -------------------------------------------------------------------------
    def update_rf_ohms(self, event=None):
        """Callback method to update the rf_ohms widget variable based on the
           slider index widget variable. The simulator property is not
           updated by this method.
        """
        # pylint: disable=unused-argument
        slider_index = int(float(self.rf_slider_index.get()))
        self.rf_ohms.set(str(QTR_WATT_RESISTORS[slider_index]))

    # -------------------------------------------------------------------------
    def update_rg_ohms(self, event=None):
        """Callback method to update the rg_ohms widget variable based on the
           slider index widget variable. The simulator property is not
           updated by this method.
        """
        # pylint: disable=unused-argument
        slider_index = int(float(self.rg_slider_index.get()))
        self.rg_ohms.set(str(QTR_WATT_RESISTORS[slider_index]))

    # -------------------------------------------------------------------------
    def update_shunt_values(self, event=None):
        """Callback method to update the shunt_ohms, shunt_wattage and
           shunt_mfg_pn widget variables based on the slider index
           widget variable. The simulator properties are not updated by
           this method.
        """
        # pylint: disable=unused-argument
        slider_index = int(float(self.shunt_slider_index.get()))
        self.shunt_ohms.set(str(SHUNT_RESISTORS[slider_index][0]))
        self.shunt_wattage.set(str(SHUNT_RESISTORS[slider_index][1]))
        self.shunt_mfg_pn.set(str(SHUNT_RESISTORS[slider_index][2]))

    # -------------------------------------------------------------------------
    def update_load_cap_values(self, event=None):
        """Callback method to update the load_cap_uf, load_cap_v and
           load_cap_mfg_pn widget variables based on the slider index
           widget variable. The simulator properties are not updated by
           this method.
        """
        # pylint: disable=unused-argument
        # Load cap slider is in opposite order from LOAD_CAPACITORS
        load_cap_index = -1 - int(float(self.load_cap_slider_index.get()))
        self.load_cap_uf.set(str(LOAD_CAPACITORS[load_cap_index][0]))
        self.load_cap_v.set(str(LOAD_CAPACITORS[load_cap_index][1]))
        self.load_cap_mfg_pn.set(str(LOAD_CAPACITORS[load_cap_index][4]))

    # -------------------------------------------------------------------------
    def update_rb_values(self, event=None):
        """Callback method to update the rb_ohms, rb_wattage and rb_mfg_pn
           widget variables based on the slider index widget
           variable. The simulator properties are not updated by this
           method.
        """
        # pylint: disable=unused-argument
        slider_index = int(float(self.rb_slider_index.get()))
        self.rb_ohms.set(str(BLEED_RESISTORS[slider_index][0]))
        self.rb_wattage.set(str(BLEED_RESISTORS[slider_index][1]))
        self.rb_mfg_pn.set(str(BLEED_RESISTORS[slider_index][2]))

    # -------------------------------------------------------------------------
    def add_results_tab(self):
        """Method to add the results tab and populate it with the results from
           the simulation. If a results tab already exists, it is first
           destroyed so the new one will have the updated results.
        """
        if self.results_tab is not None:
            self.results_tab.destroy()
        self.results_tab = ttk.Frame(self.nb)
        self.nb.add(self.results_tab, text="Results")
        self.populate_results_tab()

    # -------------------------------------------------------------------------
    def simulate_button_actions(self, event=None):
        """Callback method for the simulate button.
        """
        # pylint: disable=unused-argument

        # First update all of the widgets in case the user typed new
        # values into the Entry widgets but did not hit Return.
        self.update_all_widgets()

        # Run the simulation
        rc = self.ivs2_sim.run()
        if rc != RC_SUCCESS:
            err_msg = "Oops. Something went wrong\n"
            err_msg += "See log file for details."
            tkmsg.showerror(message=err_msg)
            IV_Swinger2.sys_view_file(self.ivs2_sim.logger.log_file_name)
            if self.results_tab is not None:
                self.results_tab.destroy()
            return

        # Display the image using the master object's display_img()
        # method if there is one. Otherwise just display the PDF.
        try:
            self.master.display_img(self.ivs2_sim.current_img)
        except (AttributeError, TypeError):
            self.ivs2_sim.display_pdf()

        # Add (or destroy and re-add) tab with results
        self.add_results_tab()

    # -------------------------------------------------------------------------
    def done(self, event=None):
        """Method called when simulator dialog is closed
        """
        # pylint: disable=unused-argument

        # Log changes to the configuration (should be none)
        self.ivs2_sim.config.log_cfg_diffs()

        # Bye, bye
        self.destroy()


# Global help dialog class
#
class SimulatorHelpDialog(tk.Toplevel):
    """Help dialog class for the simulator
    """
    # Initializer
    def __init__(self, master=None):
        tk.Toplevel.__init__(self, master=master)
        self.master = master
        self.win_sys = self.master.tk.call("tk", "windowingsystem")
        self.transient(self.master)  # tie this window to master
        title = "IV Swinger 2 Simulator Help"
        self.title(title)
        self.grab_set()  # block change of focus to master
        self.focus_set()

        # Create body frame
        body = ttk.Frame(self)

        # Call body method to create body contents
        self.body(body)
        body.pack(fill=BOTH, expand=True)

        # Set the dialog geometry
        set_dialog_geometry(self, 360, 2000)

        # Map Ctrl-A and Cmd-A (Mac) to select-all for Text widgets
        # (which includes ScrolledText)
        self.master.bind_class("Text", "<Control-a>", selectall)
        self.master.bind_class("Text", "<Command-a>", selectall)

        # Wait for dialog to be closed before returning control
        self.wait_window(self)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Method to create the dialog body, which is just a ScrolledText
           widget
        """
        help_headings = []
        help_text = []
        title_text = "IV Swinger 2 Simulator Help"
        help_text_intro = """

The purpose of the IV Swinger 2 simulator is to determine the suitability of
the components (resistors, capacitors, relays) for IV curves with a given Isc
and Voc. The standard components work well for most commercial rooftop PV
modules, and this tool can be used to demonstrate that. It also can help
choose alternate components for PV modules that have Isc and/or Voc values
that do not work well with the standard components. In addition to
quantitative results, simulated curves are generated which allow for a more
qualitative/visual assessment.
"""
        help_headings.append("""
Main Controls Tab""")
        help_text.append("""
Quick start: click on the "Simulate" button. This will run a simulation using
the default components with nominal values for Isc and Voc. The simulated IV
curve is displayed and quantitative results are listed on the "Results" tab.

Now you can start changing things to see the effects. Try setting the Isc and
Voc values to the -maximum- expected values for the PV modules you are
interested in and run the simulation. Then try clicking on the "Choose Optimal
Components" button and re-run the simulation; you should be able to see the
improvement. Now, with the new component values you can try Isc and Voc values
for different PV modules or irradiance or temperature conditions. You may need
to re-run the component optimization with different Isc and Voc values to find
components that work acceptably for all cases you are interested in. You may
also discover that you need to build more than one IV Swinger 2 to meet your
needs.

You may also manually change the component values. The sliders have presets at
real-world values. The R1, R2, Rf and Rg resistors are 1/4 W 1% resistors that
are included in the recommended set. The shunt resistor, C1 and C2 capacitors
and bleed resistor (Rb) are all components available from DigiKey and
others. The manufacturer part number (P/N) is listed to facilitate ordering.
""")
        help_headings.append("""
Other Controls Tab""")
        help_text.append("""
This tab has other adjustable values used for the simulation (above the line)
and optimization (below the line). You should not have to change any of these
values. Their only documentation is in comments in the IV_Swinger2_sim.py
Python file.
""")
        help_headings.append("""
Results Tab""")
        help_text.append("""
This tab exists only after a simulation has been run. It lists the Isc and Voc
values, the component values used, the voltage and current limits for the
configuration, and several quantitative results from the simulation. There may
be annotations with warnings if any of the results are out of their desired
ranges.
""")
        help_headings.append("""
Using the Results Wizard""")
        help_text.append("""
All simulation results are saved. You may use the Results Wizard button in the
main GUI to look at past simulations and potentially modify them with
different preferences. You must first close the simulator dialog.
""")
        help_headings.append("""
Changing Preferences""")
        help_text.append("""
All simulations are run using default preferences regardless of what you may
have changed them to. It should be noted that the simulator does NOT apply the
ADC corrections that are enabled by default for real IV curves. This is so you
can see the raw results without any of the post-processing that can hide their
flaws.

AFTER a simulation has been run, you may use the Results Wizard to change
Plotting preferences for that run (including the ability to apply the ADC
corrections.)  With the run selected in the Results Wizard dialog, click on
the Preferences button in the main GUI. Changes are visible immediately. Click
on "Cancel" to revert to the simulation defaults (do not use the Restore
Defaults button). Click on "OK" to save the modified results.
""")
        help_headings.append("""
Notes""")
        help_text.append("""
The simulated IV curve is generic from the following equation:

    I = Isc - A*(exp(B*V)-1)

This equation does not account for series or parallel resistance, and the A
and B coefficients are chosen such that the MPP current and voltage are at a
typical ratio of the Isc and Voc, respectively. This results in a fairly
representative curve that should be adequate to predict the resolution and
other characteristics of real IV curves with the given Isc and Voc. Of course,
the actual shape of the real IV curves will differ depending on actual series
and parallel resistances, temperature, etc.
""")
        font = "Arial"
        self.text = ScrolledText(master, height=1, borderwidth=10)
        self.text.tag_configure("title_tag", font=font, underline=True,
                                justify=CENTER)
        self.text.tag_configure("heading_tag", font=font, underline=True)
        self.text.tag_configure("body_tag", font=font)
        self.text.insert("end", title_text, ("title_tag"))
        self.text.insert("end", help_text_intro, ("body_tag"))
        for ii, help_heading in enumerate(help_headings):
            self.text.insert("end", help_heading, ("heading_tag"))
            self.text.insert("end", help_text[ii], ("body_tag"))
        self.text.pack(fill=BOTH, expand=True)


############
#   Main   #
############
def main():
    """Main function"""
    main_frame = ttk.Frame()
    main_frame.grid()
    SimulatorDialog(main_frame)


# Boilerplate main() call
if __name__ == '__main__':
    main()
