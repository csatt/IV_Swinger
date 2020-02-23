#!/usr/bin/env python
"""IV Swinger 2 GUI application module"""
# pylint: disable=too-many-lines
#
###############################################################################
#
# IV_Swinger2_gui.py: IV Swinger 2 GUI application module
#
# Copyright (C) 2017,2018,2019,2020  Chris Satterlee
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
# graphical user interface (GUI) application.  This program runs on an
# external "host", which is most likely a Windows or Mac laptop
# computer.  But the host computer can be anything that is capable of
# running Python and supports the Tkinter/ttk GUI toolkit (which is
# built into Python).
#
# This module sits on top of (i.e. imports) the IV_Swinger2 module,
# which provides the API for controlling the IV Swinger 2 hardware (via
# the on-board software that runs on the Arduino). The IV_Swinger2
# module also provides support for saving and restoring configuration
# options, for plotting the results, and for logging debug information.
#
# The GUI is implemented using Tkinter/ttk. This is the themed
# cross-platform GUI toolkit that is included in the standard Python
# distribution.
#
# The classes in this module are:
#
#   GraphicalUserInterface()
#
#      This is the top-level class. It is derived from the ttk.Frame
#      class.  All other classes are instantiated by this class or by
#      one of the classes it instantiates.
#
#   GraphicalUserInterfaceProps()
#
#      This class contains the properties for the
#      GraphicalUserInterface() class.  It is only needed because
#      properties don't work for classes that are not derived from the
#      "object" class (and ttk.Frame is not).
#
#   Configuration()
#
#      This class extends the IV_Swinger2 Configuration() class, adding
#      the looping controls.
#
#   ImgSizeCombo(), ResultsWizard(), MenuBar(),
#   Dialog(), GlobalHelpDialog(), CalibrationHelpDialog(),
#   AdvSsrCurrentCalHelpDialog(), AdvEmrCurrentCalHelpDialog(),
#   AdvVoltageCalHelpDialog DownlevelArduinoSketchDialog(),
#   ResistorValuesDialog(), BiasBatteryDialog(), PreferencesDialog(),
#   PlottingProps(), PlottingHelpDialog(), SpiClkCombo(),
#   LoopingHelpDialog(), ArduinoHelpDialog(), OverlayHelpDialog(),
#   ImagePane(), GoStopButton(), PlotPower(), LockAxes(), LoopMode(),
#   LoopRateLimit(), LoopSaveResults()
#
#      These classes are the "widgets" of the GUI.  Most are very simple
#      (buttons, menus, basic dialogs, etc). The ResultsWizard() and
#      PreferencesDialog() are more complex dialogs.
#
import datetime as dt
import os
import re
try:
    # Mac/Unix only
    import resource  # pylint: disable=import-error
except ImportError:
    # Used only for memory leak debug, so just skip import on Windows
    pass
import shutil
import sys
import tempfile
import ttk
import Tkinter as tk
import tkFileDialog
import tkFont
import tkMessageBox as tkmsg
import traceback
from ScrolledText import ScrolledText as ScrolledText
from Tkconstants import N, S, E, W, LEFT, RIGHT, HORIZONTAL, Y, BOTH
from inspect import currentframe, getframeinfo
from send2trash import send2trash
from PIL import Image, ImageTk
from Tooltip import Tooltip
import myTkSimpleDialog as tksd
import IV_Swinger2

#################
#   Constants   #
#################
# From IV_Swinger2
APP_NAME = IV_Swinger2.APP_NAME
RC_SUCCESS = IV_Swinger2.RC_SUCCESS
RC_FAILURE = IV_Swinger2.RC_FAILURE
RC_BAUD_MISMATCH = IV_Swinger2.RC_BAUD_MISMATCH
RC_TIMEOUT = IV_Swinger2.RC_TIMEOUT
RC_SERIAL_EXCEPTION = IV_Swinger2.RC_SERIAL_EXCEPTION
RC_ZERO_VOC = IV_Swinger2.RC_ZERO_VOC
RC_ZERO_ISC = IV_Swinger2.RC_ZERO_ISC
RC_ISC_TIMEOUT = IV_Swinger2.RC_ISC_TIMEOUT
RC_NO_POINTS = IV_Swinger2.RC_NO_POINTS
RC_SSR_HOT = IV_Swinger2.RC_SSR_HOT
CFG_STRING = IV_Swinger2.CFG_STRING
CFG_FLOAT = IV_Swinger2.CFG_FLOAT
CFG_INT = IV_Swinger2.CFG_INT
CFG_BOOLEAN = IV_Swinger2.CFG_BOOLEAN
SKETCH_VER_LT = IV_Swinger2.SKETCH_VER_LT
SKETCH_VER_EQ = IV_Swinger2.SKETCH_VER_EQ
SKETCH_VER_GT = IV_Swinger2.SKETCH_VER_GT
SKETCH_VER_ERR = IV_Swinger2.SKETCH_VER_ERR
LATEST_SKETCH_VER = IV_Swinger2.LATEST_SKETCH_VER
SPI_CLOCK_DIV4 = IV_Swinger2.SPI_CLOCK_DIV4
SPI_CLOCK_DIV16 = IV_Swinger2.SPI_CLOCK_DIV16
SPI_CLOCK_DIV64 = IV_Swinger2.SPI_CLOCK_DIV64
SPI_CLOCK_DIV128 = IV_Swinger2.SPI_CLOCK_DIV128
SPI_CLOCK_DIV2 = IV_Swinger2.SPI_CLOCK_DIV2
SPI_CLOCK_DIV8 = IV_Swinger2.SPI_CLOCK_DIV8
SPI_CLOCK_DIV32 = IV_Swinger2.SPI_CLOCK_DIV32
FONT_SCALE_DEFAULT = IV_Swinger2.FONT_SCALE_DEFAULT
LINE_SCALE_DEFAULT = IV_Swinger2.LINE_SCALE_DEFAULT
POINT_SCALE_DEFAULT = IV_Swinger2.POINT_SCALE_DEFAULT
SERIES_RES_COMP_DEFAULT = IV_Swinger2.SERIES_RES_COMP_DEFAULT
BIAS_SERIES_RES_COMP_DEFAULT = IV_Swinger2.BIAS_SERIES_RES_COMP_DEFAULT
SPI_CLK_DEFAULT = IV_Swinger2.SPI_CLK_DEFAULT
MAX_IV_POINTS_DEFAULT = IV_Swinger2.MAX_IV_POINTS_DEFAULT
MIN_ISC_ADC_DEFAULT = IV_Swinger2.MIN_ISC_ADC_DEFAULT
MAX_ISC_POLL_DEFAULT = IV_Swinger2.MAX_ISC_POLL_DEFAULT
ISC_STABLE_DEFAULT = IV_Swinger2.ISC_STABLE_DEFAULT
MAX_DISCARDS_DEFAULT = IV_Swinger2.MAX_DISCARDS_DEFAULT
ASPECT_HEIGHT_DEFAULT = IV_Swinger2.ASPECT_HEIGHT_DEFAULT
ASPECT_WIDTH_DEFAULT = IV_Swinger2.ASPECT_WIDTH_DEFAULT
ARDUINO_MAX_INT = IV_Swinger2.ARDUINO_MAX_INT
MAX_IV_POINTS_MAX = IV_Swinger2.MAX_IV_POINTS_MAX
ADC_MAX = IV_Swinger2.ADC_MAX
MAX_ASPECT = IV_Swinger2.MAX_ASPECT
V_CAL_DEFAULT = IV_Swinger2.V_CAL_DEFAULT
I_CAL_DEFAULT = IV_Swinger2.I_CAL_DEFAULT
R1_DEFAULT = IV_Swinger2.R1_DEFAULT
R1_DEFAULT_BUG = IV_Swinger2.R1_DEFAULT_BUG
R2_DEFAULT = IV_Swinger2.R2_DEFAULT
RF_DEFAULT = IV_Swinger2.RF_DEFAULT
RG_DEFAULT = IV_Swinger2.RG_DEFAULT
SHUNT_DEFAULT = IV_Swinger2.SHUNT_DEFAULT
INFINITE_VAL = IV_Swinger2.INFINITE_VAL

# GUI-specific
VERSION_FILE = "version.txt"
SPLASH_IMG = "Splash_Screen.png"
BLANK_IMG = "Blank_Screen.png"
TITLEBAR_ICON = "IV_Swinger2.ico"  # Windows
HELP_DIALOG_FONT = "Arial"
HELP_DIALOG_MIN_HEIGHT_PIXELS = 360
HELP_DIALOG_MAX_HEIGHT_PIXELS = 2000
WIZARD_MIN_HEIGHT_PIXELS = 250  # pixels
WIZARD_TREE_HEIGHT = 100  # rows
WIZARD_TREE_WIDTH = 300  # pixels
TOOLTIP_COLOR = "#FFFF40"
TOOLTIP_WAITTIME = 800
TOOLTIP_WRAP_PIXELS = 250
TOOLTIP_STAYTIME = 35
TOP_TT_KWARGS = {"bg": TOOLTIP_COLOR,
                 "waittime": TOOLTIP_WAITTIME,
                 "wraplength": TOOLTIP_WRAP_PIXELS,
                 "staytime": TOOLTIP_STAYTIME}
BOT_TT_KWARGS = {"bg": TOOLTIP_COLOR,
                 "waittime": TOOLTIP_WAITTIME,
                 "wraplength": TOOLTIP_WRAP_PIXELS,
                 "staytime": TOOLTIP_STAYTIME,
                 "offset_up": True}
SPI_COMBO_VALS = {SPI_CLOCK_DIV2: "DIV2 (8 MHz)",
                  SPI_CLOCK_DIV4: "DIV4 (4 MHz)",
                  SPI_CLOCK_DIV8: "DIV8 (2 MHz)",
                  SPI_CLOCK_DIV16: "DIV16 (1 MHz)",
                  SPI_CLOCK_DIV32: "DIV32 (500 kHz)",
                  SPI_CLOCK_DIV64: "DIV64 (250 KHz)",
                  SPI_CLOCK_DIV128: "DIV128 (125 kHz)"}
SPI_COMBO_VALS_INV = {v: k for k, v in SPI_COMBO_VALS.items()}
# Default plotting config
FANCY_LABELS_DEFAULT = "Fancy"
INTERPOLATION_TYPE_DEFAULT = "Linear"
CORRECT_ADC_DEFAULT = "On"
FIX_ISC_DEFAULT = "On"
FIX_VOC_DEFAULT = "On"
COMB_DUPV_PTS_DEFAULT = "On"
REDUCE_NOISE_DEFAULT = "On"
FIX_OVERSHOOT_DEFAULT = "On"
BATTERY_BIAS_DEFAULT = "Off"
# Debug constants
DEBUG_MEMLEAK = False


########################
#   Global functions   #
########################
def debug_memleak(msg_str):
    """Global function to print the current memory usage at a given place in
       the code or point in time. Not supported on Windows.
    """
    if DEBUG_MEMLEAK:
        date_time_str = IV_Swinger2.get_date_time_str()
        print ("{}: Memory usage ({}): {}"
               .format(date_time_str, msg_str,
                       resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))


def gen_dbg_str(msg_str):
    """Global function to use when debugging. The supplied string is
       returned, along with the file name and line number where it is
       found in the code.
    """
    cf = currentframe()
    fi = getframeinfo(cf)
    dbg_str = "DEBUG({}, line {}): {}".format(fi.filename,
                                              cf.f_back.f_lineno,
                                              msg_str)
    return dbg_str


def get_app_dir():
    """Global function to return the directory where the application is
       located, regardless of whether it is a script or a frozen
       executable (e.g. built with pyinstaller).
    """
    if getattr(sys, "frozen", False):
        return os.path.abspath(os.path.dirname(sys.executable))
    return os.path.abspath(os.path.dirname(__file__))


def tkmsg_showinfo(master, message):
    """Global function that creates a tkMessageBox object and calls
       its showinfo method, passing the message from the caller. The
       purpose of this is to add the workaround for the Mac grayed
       menu bug.
    """
    tkmsg.showinfo(message=message)
    master.mac_grayed_menu_workaround()


def tkmsg_showwarning(master, message):
    """Global function that creates a tkMessageBox object and calls
       its showwarning method, passing the message from the caller. The
       purpose of this is to add the workaround for the Mac grayed
       menu bug.
    """
    tkmsg.showwarning(message=message)
    master.mac_grayed_menu_workaround()


def tkmsg_showerror(master, message):
    """Global function that creates a tkMessageBox object and calls
       its showerror method, passing the message from the caller. The
       purpose of this is to add the workaround for the Mac grayed
       menu bug.
    """
    tkmsg.showerror(message=message)
    master.mac_grayed_menu_workaround()


def tkmsg_askyesno(master, title, message, default):
    """Global function that creates a tkMessageBox object and calls
       its askyesno method, passing the args from the caller. The
       purpose of this is to add the workaround for the Mac grayed
       menu bug.
    """
    answer = tkmsg.askyesno(title, message=message, default=default)
    master.mac_grayed_menu_workaround()
    return answer


def tksd_askstring(master, title, prompt, initialvalue):
    """Global function that creates a tkSimpleDialog object and calls
       its askstring method, passing the args from the caller. The
       purpose of this is to add the workaround for the Mac grayed
       menu bug.
    """
    answer = tksd.askstring(title=title, prompt=prompt,
                            initialvalue=initialvalue)
    master.mac_grayed_menu_workaround()
    return answer


def tksd_askinteger(master, title, prompt, initialvalue):
    """Global function that creates a tkSimpleDialog object and calls
       its askinteger method, passing the args from the caller. The
       purpose of this is to add the workaround for the Mac grayed
       menu bug.
    """
    answer = tksd.askinteger(title=title, prompt=prompt,
                             initialvalue=initialvalue)
    master.mac_grayed_menu_workaround()
    return answer


def tksd_askfloat(master, title, prompt, initialvalue):
    """Global function that creates a tkSimpleDialog object and calls
       its askfloat method, passing the args from the caller. The
       purpose of this is to add the workaround for the Mac grayed
       menu bug.
    """
    answer = tksd.askfloat(title=title, prompt=prompt,
                           initialvalue=initialvalue)
    master.mac_grayed_menu_workaround()
    return answer


def handle_early_exception():
    """Global function that prints the stack trace for an early exception
       (i.e. detected before mainloop() is started) to a temporary file
       and opens that file for the user in the system viewer. This is
       only for a frozen executable (e.g. built with pyinstaller);
       otherwise the exception info is just printed to the console.
    """
    err_msg = "Unexpected error: {}\n".format(sys.exc_info()[0])
    err_msg += traceback.format_exc()
    if not getattr(sys, "frozen", False):
        print err_msg
        return
    tmp_file = tempfile.NamedTemporaryFile(delete=False)
    err_msg += "\n"
    err_msg += """
-----------------------------------------------------------
Please copy/paste the above and send it to csatt1@gmail.com

Alternately, you may attach this file:
{}
""".format(tmp_file.name)
    with open(tmp_file.name, "a") as f:
        f.write(err_msg)
    IV_Swinger2.sys_view_file(tmp_file.name)


def get_dialog_width(dialog):
    """Global function to parse the width of a dialog from its current
       geometry
    """
    m = re.match(r"(\d+)x(\d+)", dialog.geometry())
    width = int(m.group(1))
    return width


def pdf_permission_denied(e):
    """Global function to search an exception message for the pattern that
       indicates that the problem is that permission to write a PDF was
       denied.
    """
    exception_str = "({})".format(e)
    pdf_permission_denied_re = re.compile(r"Permission denied:.*\.pdf'")
    return pdf_permission_denied_re.search(exception_str)


def date_at_time_from_dts(dts):
    """Global function to convert a date_time_str to date@time, e.g. from
       170110_190017 to 01/10/17@19:00:17
    """
    (date, time_of_day) = IV_Swinger2.xlate_date_time_str(dts)
    return "{}@{}".format(date, time_of_day)


def grab_overlay_curve(event=None):
    """Global function to select clicked curve in the treeview in
       preparation for dragging to reorder
    """
    tv = event.widget
    if tv.identify_row(event.y) not in tv.selection():
        tv.selection_set(tv.identify_row(event.y))


def selectall(event):
    """Global function to select all text in a Text or ScrolledText
       widget
    """
    event.widget.tag_add("sel", "1.0", "end")


#################
#   Classes     #
#################


# Tkinter/ttk GUI class
#
class GraphicalUserInterface(ttk.Frame):
    """Class that provides the GUI for user interaction with the
       IV Swinger 2
    """
    # pylint: disable=too-many-ancestors
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods

    # Initializer
    def __init__(self, app_data_dir=None):
        self.root = tk.Tk()
        self.set_root_options()
        ttk.Frame.__init__(self, self.root)
        self.win_sys = self.root.tk.call("tk", "windowingsystem")
        self.memory_monitor()
        self.ivs2 = IV_Swinger2.IV_Swinger2(app_data_dir)
        self.check_app_data_dir()
        self.init_instance_vars()
        self.props = GraphicalUserInterfaceProps(self)
        self.app_dir = get_app_dir()
        self.go_button = None
        self.go_button_box = None
        self.go_button_status_label = None
        self.i_range_entry = None
        self.img_file = None
        self.img_pane = None
        self.img_size_combo = None
        self.loop_mode_cb = None
        self.loop_rate_cb = None
        self.loop_save_cb = None
        self.plot_power_cb = None
        self.preferences_button = None
        self.prefs_results_bb = None
        self.range_lock_cb = None
        self.results_button = None
        self.results_wiz = None
        self.stop_button = None
        self.swing_loop_id = None
        self.v_range_entry = None
        self.version_label = None
        self.get_version()
        self.set_grid()
        self.config = Configuration(gui=self)
        self.config.get()
        self.start_to_right()
        self.set_style()
        self.create_menu_bar()
        self.create_widgets()
        self.ivs2.log_initial_debug_info()
        self.usb_monitor()

    # -------------------------------------------------------------------------
    def check_app_data_dir(self):
        """Method to check that directories can be created in the the parent of
           app_data_dir and that files can be created in app_data_dir.
           If not, display an error dialog and exit.
        """
        try:
            app_data_parent = os.path.dirname(self.ivs2.app_data_dir)
            dummy_dir = os.path.join(app_data_parent, "DUMMY_DIR")
            os.makedirs(dummy_dir)
            os.rmdir(dummy_dir)
        except (IOError, OSError):
            err_msg = """
FATAL ERROR: This user does not have
permission to create directories (folders) in
{}""".format(app_data_parent)
            tkmsg_showerror(self, err_msg)
            sys.exit()
        try:
            dummy_file = os.path.join(self.ivs2.app_data_dir, "DUMMY_FILE")
            open(dummy_file, "a").close()
            os.remove(dummy_file)
        except (IOError, OSError):
            err_msg = """
FATAL ERROR: This user does not have
permission to create files in
{}""".format(self.ivs2.app_data_dir)
            tkmsg_showerror(self, err_msg)
            sys.exit()

    # -------------------------------------------------------------------------
    def report_callback_exception(self, *args):
        """Method to override the parent class's method of the same name. This
           method is called whenever there is an exception in the code
           run by the mainloop() - i.e. everything after the GUI
           actually comes up. Without this override, the exception is
           printed to stderr, but doesn't crash the program. That makes
           it completely silent when the program is started from an
           icon. We at least need it to get logged and also to inform
           the user.
        """
        # pylint: disable=unused-argument
        self.ivs2.logger.print_and_log("Unexpected error: {}"
                                       .format(sys.exc_info()[0]))
        self.ivs2.logger.print_and_log(traceback.format_exc())
        exception_msg = """
An internal error has occurred.  Please send
the log file to csatt1@gmail.com.

Use "View Log File" on the "File" menu.
The file name is near the top.
"""
        tkmsg_showerror(self, exception_msg)

    # -------------------------------------------------------------------------
    def memory_monitor(self):
        """Method to run the debug_memleak global function once per second"""
        debug_memleak("memory_monitor")
        self.after(1000, self.memory_monitor)

    # -------------------------------------------------------------------------
    def get_version(self):
        """Method to open the version.txt file, read the version number
           contained in it, and set the object's "version" attribute to
           that value
        """
        version_file = os.path.join(self.app_dir, VERSION_FILE)
        try:
            with open(version_file, "r") as f:
                lines = f.read().splitlines()
                if len(lines) != 1:
                    err_str = ("ERROR: {} has {} lines"
                               .format(VERSION_FILE, len(lines)))
                    self.ivs2.logger.print_and_log(err_str)
                    return
                version = lines[0]
                if not version or version[0] != "v":
                    err_str = ("ERROR: {} has invalid version: {}"
                               .format(VERSION_FILE, version))
                    self.ivs2.logger.print_and_log(err_str)
                    return
                self.version = version
                log_msg = "Application version: {}".format(version)
                self.ivs2.logger.log(log_msg)
        except IOError:
            err_str = "ERROR: {} doesn't exist".format(VERSION_FILE)
            self.ivs2.logger.print_and_log(err_str)

    # -------------------------------------------------------------------------
    def init_instance_vars(self):
        """Method to initialize the object's instance variables"""
        self.resolution_str = tk.StringVar()
        self.plot_power = tk.StringVar()
        self.v_range = tk.StringVar()
        self.i_range = tk.StringVar()
        self.axes_locked = tk.StringVar()
        self.axes_locked.set("Unlock")
        self.loop_mode = tk.StringVar()
        self.loop_mode.set("Off")
        self.loop_rate = tk.StringVar()
        self.loop_save = tk.StringVar()
        self.label_all_iscs = tk.StringVar()
        self.label_all_mpps = tk.StringVar()
        self.mpp_watts_only = tk.StringVar()
        self.label_all_vocs = tk.StringVar()
        self.version = "UNKNOWN"
        self.grid_args = {}
        self.results_wiz = None
        self.img_file = None
        self._cfg_filename = None
        self._restore_loop = False
        self._loop_stop_on_err = True
        self._loop_mode_active = False
        self._loop_rate_limit = False
        self._loop_delay = 0
        self._loop_save_results = False
        self._loop_save_graphs = False
        self._suppress_cfg_file_copy = False
        self._overlay_names = {}
        self._overlay_dir = None
        self._overlay_mode = False
        self._redisplay_after_axes_unlock = True
        self._current_run_displayed = False
        self.zero_voc_str = """
ERROR: Voc is zero volts

Check that the IV Swinger 2 is connected
properly to the PV module (or cell)
"""
        self.zero_isc_str = """
ERROR: Isc is zero amps

Check that the IV Swinger 2 is connected
properly to the PV module (or cell)
"""
        self.isc_timeout_str = """
ERROR: Timed out polling for stable Isc

This may be due to insufficient sunlight.

If that is not the case, the "Isc stable ADC"
value may need to be increased to a larger
value on the Arduino tab of Preferences
"""

    # -------------------------------------------------------------------------
    def get_adc_pairs_from_csv(self, adc_csv_file):
        """Method to get the ADC pairs from the CSV file containing them. Just
           a wrapper around the IV_Swinger2 class's
           read_adc_pairs_from_csv_file() method.
        """
        return self.ivs2.read_adc_pairs_from_csv_file(adc_csv_file)

    # -------------------------------------------------------------------------
    def set_root_options(self):
        """Method to set options for the root Tk object"""
        # Override tkinter's report_callback_exception method
        self.root.report_callback_exception = self.report_callback_exception
        # Disable resizing, at least for now
        self.root.resizable(width=False, height=False)
        # No dotted line in menus
        self.root.option_add("*tearOff", False)
        # Add title and titlebar icon (Windows)
        self.root.title("IV Swinger 2")
        if sys.platform == "win32" and os.path.exists(TITLEBAR_ICON):
            self.root.tk.call("wm", "iconbitmap",
                              self.root._w,  # pylint: disable=protected-access
                              "-default", TITLEBAR_ICON)

    # -------------------------------------------------------------------------
    def set_style(self):
        """Method to configure a custom ttk style for certain widgets"""
        self.style = ttk.Style()
        font = ("TkDefaultFont {} bold italic"
                .format(max(int(round(self.ivs2.x_pixels / 43.0)), 19)))
        self.style.configure("go_stop_button.TButton",
                             foreground="red",
                             padding=4,
                             font=font)

    # -------------------------------------------------------------------------
    def set_grid(self):
        """Method to configure the grid for the top level frame"""
        self.grid(column=0, row=0, sticky=(N, S, E, W))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    # -------------------------------------------------------------------------
    def create_menu_bar(self):
        """Method to create the menu bar
        """
        self.menu_bar = MenuBar(master=self)

    # -------------------------------------------------------------------------
    def mac_grayed_menu_workaround(self):
        """Method to work around a Mac bug in the version of Tk (8.5.9) that
           is included with OSX/MacOS versions since 10.7 (Lion) and up to at
           least 10.13 (High Sierra) that has the effect that if the user
           looks at the menu while a "modal" window is active, the menu items
           remain disabled (grayed out) even after the modal window is
           closed. See https://bugs.python.org/issue21757. Although this can
           be solved by installing Python from python.org, we'll opt to work
           around the problem by recreating the menu bar whenever a modal
           window is closed.
        """
        if self.win_sys == "aqua":  # Mac
            self.create_menu_bar()

    # -------------------------------------------------------------------------
    def set_dialog_geometry(self, dialog, min_height=None, max_height=None):
        """Method to set the size and position of a dialog. If min_height is
           specified, the window will be sized to that value initially.
           The max_height parameter is only relevant if min_height is
           specified; if max_height is not specified, the height when
           this method was called will be used as the maximum. If
           min_height is not specified, the height and width are not
           changed, only the offsets (position).
        """
        # Run update_idletasks to get the geometry manager to size the
        # window to fit the widgets
        self.update_idletasks()

        # Get current window width
        width = get_dialog_width(dialog)

        if min_height is not None:
            # Disable width resizing by setting min and max width to
            # the width that it comes up. This is a workaround for the
            # fact that (at least on Mac) the "resizable" option
            # doesn't work for width only.
            if max_height is None:
                max_height = dialog.winfo_height()
            dialog.minsize(width, min_height)
            dialog.maxsize(width, max_height)

        # Calculate offset of dialog from the root window. If there
        # are enough screen pixels to the left of the root window,
        # then put it there (with 10 pixels of overlap). Second choice
        # is to the right of the root window. Last choice is whichever
        # side has more space, overlapping root window by as much as
        # necessary to leave 10 pixels of screen.
        m = re.match(r".*([-+]\d+)([-+]\d+)", self.root.geometry())
        left_pixels_avail = int(m.group(1))
        m = re.match(r"(\d+)x(\d+)", self.root.geometry())
        root_width = int(m.group(1))
        right_pixels_avail = (self.winfo_screenwidth() - left_pixels_avail -
                              root_width)
        if left_pixels_avail < 0:
            # Weird multi-display case: app is started on right
            # display and moved to left display. No way (?) to tell
            # how much space there really is, so just overlap root
            # window completely.
            left_offset = -10
        elif left_pixels_avail > width - 10:
            # Normal first choice: fits to left of root
            left_offset = width - 10
        elif right_pixels_avail > width - 10:
            # Second choice: fits to right of root
            left_offset = -(root_width - 10)
        elif left_pixels_avail > right_pixels_avail:
            # Third choice: more room to left of root
            left_offset = left_pixels_avail - 10
        else:
            # Last choice: more room to right of root
            left_offset = -(root_width - 10) - (right_pixels_avail - width)

        if min_height is None:
            # Set the geometry to the offset from main window
            # determined above
            dialog.geometry("+{}+{}".format(self.winfo_rootx()-left_offset,
                                            self.winfo_rooty()+10))
        else:
            # Set the geometry to the initial (fixed) width, minimum
            # height, and offset from main window determined above
            dialog.geometry("{}x{}+{}+{}"
                            .format(width, min_height,
                                    self.winfo_rootx()-left_offset,
                                    self.winfo_rooty()+10))

        # Run update_idletasks to prevent momentary appearance of pre-resized
        # window
        self.update_idletasks()

    # -------------------------------------------------------------------------
    def create_widgets(self):
        """Method to create the main window's widgets"""
        total_cols = 12
        pad_cols = 2
        column = 1
        row = 1
        # Grid layout
        self.grid_args["img_size_combo"] = {"column": column,
                                            "row": row,
                                            "sticky": (W)}
        self.grid_args["version_label"] = {"column": total_cols,
                                           "row": row,
                                           "sticky": (E)}
        row += 1
        self.grid_args["img_pane"] = {"column": column,
                                      "row": row,
                                      "columnspan": total_cols}
        row += 1
        self.grid_args["prefs_results_buttons"] = {"column": column,
                                                   "row": row,
                                                   "rowspan": 3}
        column += pad_cols
        self.grid_args["axis_ranges_box"] = {"column": column,
                                             "row": row,
                                             "rowspan": 3,
                                             "sticky": (W)}
        column += pad_cols
        self.grid_args["go_button_box"] = {"column": column,
                                           "row": row,
                                           "rowspan": 3}
        column += pad_cols
        self.grid_args["plot_power_cb"] = {"column": column,
                                           "row": row,
                                           "rowspan": 3}
        column += 1
        remaining_cols = total_cols - column + 1
        self.grid_args["looping_controls_box"] = {"column": column,
                                                  "row": row,
                                                  "sticky": (S, W),
                                                  "columnspan": remaining_cols}
        # Create them
        self.create_img_size_combo()
        self.create_version_label()
        self.create_img_pane()
        self.create_prefs_results_button_box()
        self.create_go_button_box()
        self.create_axis_ranges_box()
        self.create_plot_power_cb()
        self.create_looping_controls()

    # -------------------------------------------------------------------------
    def create_img_size_combo(self):
        """Method to create the image size combo box and its bindings
        """
        self.img_size_combo = ImgSizeCombo(master=self,
                                           textvariable=self.resolution_str)
        aspect = "{}x{}".format(self.ivs2.plot_x_inches,
                                self.ivs2.plot_y_inches)
        tt_text = ("Pull down to select desired display size or type in "
                   "desired size and hit Enter. Must be an aspect ratio of "
                   "{} (height will be modified if not)".format(aspect))
        Tooltip(self.img_size_combo, text=tt_text, **TOP_TT_KWARGS)
        self.img_size_combo.bind("<<ComboboxSelected>>", self.update_img_size)
        self.img_size_combo.bind("<Return>", self.update_img_size)
        self.img_size_combo.grid(**self.grid_args["img_size_combo"])

    # -------------------------------------------------------------------------
    def create_version_label(self):
        """Method to create the version label
        """
        version_text = "         Version: {}".format(self.version)
        self.version_label = ttk.Label(master=self, text=version_text)
        self.version_label.grid(**self.grid_args["version_label"])

    # -------------------------------------------------------------------------
    def create_img_pane(self):
        """Method to create the image pane
        """
        self.img_pane = ImagePane(master=self)
        self.img_pane.grid(**self.grid_args["img_pane"])

    # -------------------------------------------------------------------------
    def create_prefs_results_button_box(self):
        """Method to create the box containing the Preferences and Results
           Wizard buttons
        """
        self.prefs_results_bb = ttk.Frame(self)
        self.preferences_button = ttk.Button(master=self.prefs_results_bb,
                                             text="Preferences")
        # Tooltip
        tt_text = "Open Preferences dialog"
        Tooltip(self.preferences_button, text=tt_text, **BOT_TT_KWARGS)
        self.preferences_button.bind("<Button-1>", self.show_preferences)
        self.preferences_button.pack()

        self.results_button = ttk.Button(master=self.prefs_results_bb,
                                         text="Results Wizard")
        # Tooltip
        tt_text = ("View results of previous runs, combine multiple curves on "
                   "the same plot, modify their title and appearance, copy "
                   "them to USB (or elsewhere), and more ...")
        Tooltip(self.results_button, text=tt_text, **BOT_TT_KWARGS)
        self.results_button.bind("<Button-1>", self.results_actions)
        self.results_button.pack(pady=(8, 0))

        self.prefs_results_bb.grid(**self.grid_args["prefs_results_buttons"])

    # -------------------------------------------------------------------------
    def recreate_prefs_results_button_box(self):
        """Method to remove the current box around the Preferences and Results
           Wizard buttons and create a new one
        """
        old_button_box = self.prefs_results_bb
        self.create_prefs_results_button_box()
        old_button_box.destroy()

    # -------------------------------------------------------------------------
    def create_axis_ranges_box(self):
        """Method to create the axis ranges box containing one Entry widget for
           the Voltage range, another for the Current range, and a
           checkbutton for locking the ranges
        """
        # Box around everything - this is gridded into the main GUI window
        axis_ranges_box = ttk.Frame(self)

        # Tooltip
        tt_text = ("Axis ranges are automatic by default. The Lock "
                   "checkbutton can be checked to lock the ranges "
                   "to the values of the first (or most recent) run or to "
                   "values entered by the user. If the values are changed "
                   "when a plot is currently displayed, it will be redrawn "
                   "using the new values (does not apply to overlays that "
                   "have been 'finished')")
        Tooltip(axis_ranges_box, text=tt_text, **BOT_TT_KWARGS)

        # Title label
        title_label = ttk.Label(master=axis_ranges_box,
                                text="  Axis Ranges")
        title_label.pack()

        # Box around the boxes containing the labels and entries
        labels_and_entries_box = ttk.Frame(master=axis_ranges_box)

        # Box containing the labels
        labels_box = ttk.Frame(labels_and_entries_box)
        v_label = ttk.Label(master=labels_box, text="Max V:")
        i_label = ttk.Label(master=labels_box, text="Max I:")
        v_label.pack()
        i_label.pack()

        # Box containing the entries
        entries_box = ttk.Frame(labels_and_entries_box)
        self.v_range_entry = ttk.Entry(master=entries_box, width=9,
                                       textvariable=self.v_range)
        self.i_range_entry = ttk.Entry(master=entries_box, width=9,
                                       textvariable=self.i_range)
        self.v_range_entry.bind("<Return>", self.apply_new_ranges)
        self.i_range_entry.bind("<Return>", self.apply_new_ranges)
        self.v_range_entry.pack()
        self.i_range_entry.pack()
        self.update_axis_ranges()

        # Pack labels and entries side-by-side in
        # labels_and_entries_box
        labels_box.pack(side=LEFT)
        entries_box.pack(side=LEFT)

        # Pack labels_and_entries_box in top-level box
        labels_and_entries_box.pack()

        # Create lock checkbutton and pack it under
        # labels_and_entries_box
        self.range_lock_cb = LockAxes(master=axis_ranges_box,
                                      gui=self,
                                      variable=self.axes_locked)
        self.range_lock_cb.pack()

        # Place the whole thing in the main GUI
        axis_ranges_box.grid(**self.grid_args["axis_ranges_box"])

    # -------------------------------------------------------------------------
    def create_go_button_box(self):
        """Method to create the go button and its associated bindings, along
           with the status label, both packed in a box
        """
        # Box around button and status label - this is gridded into the
        # main GUI window
        self.go_button_box = ttk.Frame(self)

        # Go button
        self.go_button = GoStopButton(master=self.go_button_box)
        if not self.ivs2.arduino_ready:
            self.go_button.state(["disabled"])
        # Tooltip
        tt_text = ("Trigger an IV curve trace (if connected). If loop mode is "
                   "selected, this button changes to a STOP button and curve "
                   "tracing continues until stopped.")
        Tooltip(self.go_button, text=tt_text, **BOT_TT_KWARGS)

        # Left-clicking go button and hitting Return or space bar do the
        # same thing
        self.go_button.bind("<Button-1>", self.go_actions)
        self.root.bind("<Return>", self.go_actions)
        self.root.bind("<space>", self.go_actions)

        # Status label
        self.go_button_status_label = ttk.Label(master=self.go_button_box)
        if not self.ivs2.arduino_ready:
            self.go_button_status_label["text"] = "Not connected"

        # Grid placement in enclosing box
        self.go_button.grid(column=0, row=0)
        self.go_button_status_label.grid(column=0, row=1)

        # Grid placement of box within main GUI
        self.go_button_box.grid(**self.grid_args["go_button_box"])

    # -------------------------------------------------------------------------
    def create_plot_power_cb(self):
        """Method to create the plt power checkbutton
        """
        self.plot_power_cb = PlotPower(master=self,
                                       variable=self.plot_power)
        # Tooltip
        tt_text = "Check to add the power curve to the plot"
        Tooltip(self.plot_power_cb, text=tt_text, **BOT_TT_KWARGS)
        self.plot_power_cb.grid(**self.grid_args["plot_power_cb"])

    # -------------------------------------------------------------------------
    def create_looping_controls(self):
        """Method to create the looping control widgets
        """
        grid_args = {}
        grid_args["loop_mode_cb"] = {"column": 1,
                                     "row": 1,
                                     "sticky": (W),
                                     "columnspan": 2}
        grid_args["loop_rate_box"] = {"column": 2,
                                      "row": 2,
                                      "sticky": (W),
                                      "columnspan": 1}
        grid_args["loop_save_box"] = {"column": 2,
                                      "row": 3,
                                      "sticky": (W),
                                      "columnspan": 1}
        # Box around everything - this is gridded into the main GUI
        # window
        looping_controls_box = ttk.Frame(self)

        # Box containing the padding and rate limit checkbutton
        loop_rate_box = ttk.Frame(looping_controls_box)
        loop_rate_pad = ttk.Label(loop_rate_box, text="    ")
        self.loop_rate_cb = LoopRateLimit(master=loop_rate_box,
                                          gui=self,
                                          variable=self.loop_rate)
        loop_rate_pad.pack(side=LEFT)
        self.loop_rate_cb.pack(side=LEFT)
        if self.config.cfg.getboolean("Looping", "restore values"):
            if self.props.loop_rate_limit:
                self.loop_rate_cb.state(["selected"])
                self.loop_rate_cb.update_value_str()
        tt_text = "Check to limit repetition rate of looping"
        Tooltip(self.loop_rate_cb, text=tt_text, **BOT_TT_KWARGS)

        # Box containing the padding and loop save checkbutton
        loop_save_box = ttk.Frame(looping_controls_box)
        loop_save_pad = ttk.Label(loop_save_box, text="    ")
        self.loop_save_cb = LoopSaveResults(master=loop_save_box,
                                            gui=self,
                                            variable=self.loop_save)
        loop_save_pad.pack(side=LEFT)
        self.loop_save_cb.pack(side=LEFT)
        if self.config.cfg.getboolean("Looping", "restore values"):
            if self.props.loop_save_results:
                self.loop_save_cb.state(["selected"])
                self.loop_save_cb.update_value_str()
        tt_text = "Check to save results while looping"
        Tooltip(self.loop_save_cb, text=tt_text, **BOT_TT_KWARGS)

        # Loop mode checkbutton
        self.loop_mode_cb = LoopMode(master=looping_controls_box,
                                     gui=self,
                                     variable=self.loop_mode,
                                     rate_limit=self.loop_rate_cb,
                                     save_results=self.loop_save_cb,
                                     lock_axes=self.range_lock_cb)
        tt_text = "Check to enable automatic repetition of curve tracing"
        Tooltip(self.loop_mode_cb, text=tt_text, **BOT_TT_KWARGS)

        # Grid placement within enclosing box
        self.loop_mode_cb.grid(**grid_args["loop_mode_cb"])
        loop_rate_box.grid(**grid_args["loop_rate_box"])
        loop_save_box.grid(**grid_args["loop_save_box"])

        # Grid placement within main GUI
        looping_controls_box.grid(**self.grid_args["looping_controls_box"])

    # -------------------------------------------------------------------------
    def update_plot_power_cb(self):
        """Method to set the plot_power StringVar to the correct value, based
           on the value in the config
        """
        if self.config.cfg.getboolean("Plotting", "plot power"):
            self.plot_power.set("Plot")
        else:
            self.plot_power.set("DontPlot")

    # -------------------------------------------------------------------------
    def update_axis_ranges(self):
        """Method to update the values displayed in the axis range entry
           widgets
        """
        axes_are_locked = self.ivs2.plot_lock_axis_ranges
        v_range_entry = "<auto>"
        i_range_entry = "<auto>"
        self.v_range_entry.state(["disabled"])
        self.i_range_entry.state(["disabled"])
        if axes_are_locked:
            self.v_range_entry.state(["!disabled"])
            self.i_range_entry.state(["!disabled"])
            if self.ivs2.plot_max_x is not None:
                v_range_entry = str(self.ivs2.plot_max_x)
            if self.ivs2.plot_max_y is not None:
                i_range_entry = str(self.ivs2.plot_max_y)
        self.v_range.set(str(v_range_entry))
        self.i_range.set(str(i_range_entry))

    # -------------------------------------------------------------------------
    def apply_new_ranges(self, event=None):
        """Method to apply a new voltage or current range (max value
           on axis) when entered by the user
        """
        # Replace config from saved config of displayed image
        run_dir = self.ivs2.hdd_output_dir
        config_dir = os.path.dirname(self.config.cfg_filename)
        if run_dir is not None and run_dir != config_dir:
            cfg_file = os.path.join(run_dir, "{}.cfg".format(APP_NAME))
            if os.path.exists(cfg_file):
                # Snapshot current config
                original_cfg_file = self.config.cfg_filename
                self.config.get_snapshot()
                # Get config from run_dir
                self.config.cfg_filename = cfg_file
                self.config.get_old_result(cfg_file)

        # Update IVS2 property
        try:
            self.ivs2.plot_max_x = float(self.v_range.get())
            self.ivs2.plot_max_y = float(self.i_range.get())
            event.widget.tk_focusNext().focus()  # move focus out
        except ValueError:
            # Silently reject invalid values
            pass
        self.update_axis_ranges()
        self.update_idletasks()

        # Redisplay the image with the new settings (saves config)
        self.redisplay_img(reprocess_adc=False)

        if (run_dir is not None and run_dir != config_dir and
                os.path.exists(cfg_file)):
            # Restore the config file from the snapshot
            self.config.cfg_filename = original_cfg_file
            self.config.save_snapshot()

        # Unlock the axes
        if self.axes_locked.get() == "Unlock":
            self.unlock_axes()

    # -------------------------------------------------------------------------
    def attempt_arduino_handshake(self, write_eeprom=False):
        """Method which is a "best-effort" attempt to reset the Arduino and
           perform the initial handshake when the GUI comes up. If this
           succeeds, there will be no delay when the go button is
           pressed for the first time. If it fails, it might be because
           the IVS2 hardware is not connected yet, which isn't a
           requirement, so it should fail silently. In that case, it
           retries itself once a second.  If and when the IVS2 hardware
           is connected, it will bring up the interface.
        """
        # Bail out now if Arduino ready flag is set
        if self.ivs2.arduino_ready:
            return

        # Find new serial ports, if any
        old_serial_ports = self.ivs2.serial_ports
        self.ivs2.find_serial_ports()
        if old_serial_ports != self.ivs2.serial_ports:
            self.ivs2.find_arduino_port()

        if self.ivs2.usb_port is not None:
            self.go_button.state(["disabled"])
            self.go_button_status_label["text"] = "Not connected"
            self.update_idletasks()
            # Reset Arduino
            rc = self.ivs2.reset_arduino()
            if rc == RC_SUCCESS:
                # Wait for Arduino ready message
                rc = self.ivs2.wait_for_arduino_ready_and_ack(write_eeprom)
                if rc == RC_SUCCESS:
                    self.go_button.state(["!disabled"])
                    self.go_button_status_label["text"] = "     Connected     "
                    self.after(1000,
                               self.clear_go_button_status_label)
                    self.check_arduino_sketch_version()
                    self.update_config_after_arduino_handshake()
                    return

        # If any of the above failed, try again in 1 second
        self.after(1000, self.attempt_arduino_handshake)

    # -------------------------------------------------------------------------
    def clear_go_button_status_label(self):
        """Method to fill the go button's status label with space characters"""
        self.go_button_status_label["text"] = " " * 30

    # -------------------------------------------------------------------------
    def update_config_after_arduino_handshake(self):
        """Method to update configuration values that can be changed as
           side-effects of the Arduino handshake: namely the USB port
           and the calibration values.
        """
        # pylint: disable=too-many-statements
        config_changed = False
        # USB
        section = "USB"
        option = "port"
        cfg_usb = self.config.cfg.get(section, option)
        if cfg_usb != self.ivs2.usb_port:
            self.config.cfg_set(section, option, self.ivs2.usb_port)
            config_changed = True
        # Calibration
        section = "Calibration"
        option = "r1 ohms"
        cfg_vdiv_r1 = self.config.cfg.get(section, option)
        if cfg_vdiv_r1 != self.ivs2.vdiv_r1:
            self.config.cfg_set(section, option, self.ivs2.vdiv_r1)
            config_changed = True
        option = "r2 ohms"
        cfg_vdiv_r2 = self.config.cfg.get(section, option)
        if cfg_vdiv_r2 != self.ivs2.vdiv_r2:
            self.config.cfg_set(section, option, self.ivs2.vdiv_r2)
            config_changed = True
        option = "rf ohms"
        cfg_amm_op_amp_rf = self.config.cfg.get(section, option)
        if cfg_amm_op_amp_rf != self.ivs2.amm_op_amp_rf:
            self.config.cfg_set(section, option, self.ivs2.amm_op_amp_rf)
            config_changed = True
        option = "rg ohms"
        cfg_amm_op_amp_rg = self.config.cfg.get(section, option)
        if cfg_amm_op_amp_rg != self.ivs2.amm_op_amp_rg:
            self.config.cfg_set(section, option, self.ivs2.amm_op_amp_rg)
            config_changed = True
        option = "shunt max volts"
        cfg_amm_shunt_max_volts = self.config.cfg.get(section, option)
        if cfg_amm_shunt_max_volts != self.ivs2.amm_shunt_max_volts:
            self.config.cfg_set(section, option,
                                self.ivs2.amm_shunt_max_volts)
            config_changed = True
        option = "voltage"
        cfg_v_cal = self.config.cfg.get(section, option)
        if cfg_v_cal != self.ivs2.v_cal:
            self.config.cfg_set(section, option, self.ivs2.v_cal)
            config_changed = True
        option = "voltage intercept"
        cfg_v_cal_b = self.config.cfg.get(section, option)
        if cfg_v_cal_b != self.ivs2.v_cal_b:
            self.config.cfg_set(section, option, self.ivs2.v_cal_b)
            config_changed = True
        option = "current"
        cfg_i_cal = self.config.cfg.get(section, option)
        if cfg_i_cal != self.ivs2.i_cal:
            self.config.cfg_set(section, option, self.ivs2.i_cal)
            config_changed = True
        option = "current intercept"
        cfg_i_cal_b = self.config.cfg.get(section, option)
        if cfg_i_cal_b != self.ivs2.i_cal_b:
            self.config.cfg_set(section, option, self.ivs2.i_cal_b)
            config_changed = True
        if config_changed:
            self.save_config()

    # -------------------------------------------------------------------------
    def check_arduino_sketch_version(self):
        """Method to check if the Arduino sketch is the latest version. If not,
           then display the down-level sketch dialog.
        """
        if self.ivs2.arduino_sketch_ver != "Unknown":
            if self.ivs2.arduino_sketch_ver_lt(LATEST_SKETCH_VER):
                DownlevelArduinoSketchDialog(self)

    # -------------------------------------------------------------------------
    def update_img_size(self, event=None):
        """Method to update the image size when the size is change via
           the image size combo box.
        """
        res_str = self.resolution_str.get()

        # The first number in the input is x_pixels
        res_re = re.compile(r"(\d+)")
        match = res_re.search(res_str)
        if match:
            # Use x_pixels, calculate y_pixels
            x_pixels = int(match.group(1))
            y_pixels = int(round(x_pixels *
                                 self.ivs2.plot_y_inches /
                                 self.ivs2.plot_x_inches))
            new_res_str = "{}x{}".format(x_pixels, y_pixels)
            self.ivs2.logger.log("New resolution: {}".format(new_res_str))
            # Set the resolution string to the new value
            self.resolution_str.set(new_res_str)
            # Set the x_pixels property of the IVS2 object to the new value
            self.ivs2.x_pixels = x_pixels
            # Update config
            self.config.cfg_set("General", "x pixels", self.ivs2.x_pixels)
            # Update style and recreate go_button
            self.set_style()
            self.go_button.destroy()
            self.create_go_button_box()
            # Recreate Preferences and Results Wizard buttons
            self.recreate_prefs_results_button_box()
            # Redisplay the image with the new settings (saves config)
            self.redisplay_img(reprocess_adc=False)
        else:
            # No match - keep current value
            x_pixels = self.ivs2.x_pixels
            y_pixels = int(round(x_pixels *
                                 self.ivs2.plot_y_inches /
                                 self.ivs2.plot_x_inches))
            new_res_str = "{}x{}".format(x_pixels, y_pixels)
            self.ivs2.logger.log("Keeping old resolution: {}"
                                 .format(new_res_str))
            self.resolution_str.set(new_res_str)
        event.widget.selection_clear()  # remove annoying highlight
        event.widget.tk_focusNext().focus()  # move focus out so Return works

    # -------------------------------------------------------------------------
    def get_curr_x_pixels(self):
        """Method to get the current number of X dimension pixels from the image
           size resolution string
        """
        res_str = self.resolution_str.get()
        res_re = re.compile(r"(\d+)")
        match = res_re.search(res_str)
        x_pixels = int(match.group(1))
        return x_pixels

    # -------------------------------------------------------------------------
    def redisplay_img(self, reprocess_adc=False):
        """Method to redisplay the current image. This is used when the image
           size has changed or when something else has changed that
           requires regenerating and redisplaying the IV curve.
        """
        # If we're still displaying a splash screen, update it to
        # the new size. If an IV curve is showing, regenerate it..
        if self.img_pane.splash_img_showing:
            self.img_pane.display_splash_img()
        elif self.props.overlay_mode:
            self.results_wiz.plot_overlay_and_display()
        else:
            remove_directory = False
            if not os.path.exists(self.ivs2.hdd_output_dir):
                # Directory may have been removed if looping so
                # re-create it, but remove it after image is displayed
                remove_directory = True
                os.makedirs(self.ivs2.hdd_output_dir)
                reprocess_adc = True
            rc = RC_SUCCESS
            if reprocess_adc:
                rc = self.ivs2.process_adc_values()
            if rc == RC_SUCCESS:
                self.plot_results()
                if not self.props.suppress_cfg_file_copy:
                    self.config.add_axes_and_title()
                self.display_img(self.ivs2.current_img)
            elif rc == RC_NO_POINTS:
                self.show_no_points_dialog()
            if remove_directory:
                if self.ivs2.hdd_output_dir == os.getcwd():
                    os.chdir("..")
                shutil.rmtree(self.ivs2.hdd_output_dir)
            else:
                self.ivs2.clean_up_files(self.ivs2.hdd_output_dir,
                                         loop_mode=False)
        # Save the config
        self.save_config()

    # -------------------------------------------------------------------------
    def plot_results(self):
        """Wrapper method around the IV_Swinger2 method of the same name. Adds
           option for user to retry if the file is open in a viewer
           (Windows issue).
        """
        self.retry_if_pdf_permission_denied(self.ivs2.plot_results)

    # -------------------------------------------------------------------------
    def retry_if_pdf_permission_denied(self, func, *args):
        """Method to call another function (with its args) that may fail due to
           a "Permission denied" exception on a PDF file. If the
           exception is encountered, the user is prompted to close the
           file if they have it open in a viewer. Then the function is
           called again.
        """
        try:
            func(*args)
        except IOError as e:
            if pdf_permission_denied(e):
                err_str = ("({})"
                           "\n\n"
                           "PDF could not be written. If you have it open in "
                           "a viewer, close it BEFORE clicking OK.".format(e))
                tkmsg_showerror(self, message=err_str)
                try:
                    func(*args)
                except IOError as e:
                    if pdf_permission_denied(e):
                        err_str = ("({})"
                                   "\n\n"
                                   "PDF still could not be written. "
                                   "It will not be updated.".format(e))
                        tkmsg_showerror(self, message=err_str)

    # -------------------------------------------------------------------------
    def save_config(self):
        """Method to save the current config to the .cfg file. This is mostly a
           wrapper around the save() method of the Configuration class,
           but it has code to determine whether or not to set the
           copy_dir parameter.
        """
        copy_dir = None
        if (not self.props.suppress_cfg_file_copy and
                (self.props.loop_save_results or
                 not self.props.loop_mode_active)):
            copy_dir = self.ivs2.hdd_output_dir
        else:
            copy_dir = None

        self.config.save(copy_dir=copy_dir)

    # -------------------------------------------------------------------------
    def show_preferences(self, event=None):
        """Method to open the Preferences dialog"""
        # pylint: disable=unused-argument
        if self.preferences_button.instate(["disabled"]):
            # Mystery why this is necessary ...
            return
        # Create the Preferences dialog
        PreferencesDialog(self)

        # There's a weird bug where the button takes its "pressed"
        # appearance and never turns back to its normal appearance when the
        # dialog is closed. The current workaround is to re-create the button
        # (actually the whole box containing both buttons) and then destroy the
        # previous button box. Another workaround is to use
        # "self.wait_window(self)" to block this method from ever returning,
        # but it is not understood why that works, and it doesn't seem like a
        # great idea.
        try:
            self.recreate_prefs_results_button_box()
        except tk.TclError:
            pass

    # -------------------------------------------------------------------------
    def results_actions(self, event=None):
        """Method to open the Results Wizard"""
        # pylint: disable=unused-argument
        if (self.results_wiz is None and
                not self.results_button.instate(["disabled"])):
            self.results_wiz = ResultsWizard(self)

    # -------------------------------------------------------------------------
    def go_actions(self, event=None):
        """Method to start swinging one or more IV curves when the go
           button is pressed
        """
        if self.go_button.instate(["disabled"]):
            # Mystery why this is necessary ...
            return

        if (event.widget == self.img_size_combo or
                event.widget == self.v_range_entry or
                event.widget == self.i_range_entry):
            # When Return key is hit in any of these widgets, it's to
            # change their value, so bail out without doing anything
            return

        # Change button to "pressed" appearance
        self.go_button.state(["pressed"])
        self.update_idletasks()

        # Swing the IV curve, possibly looping
        rc = self.swing_loop(loop_mode=self.loop_mode.get() == "On",
                             first_loop=True)
        if rc == RC_SERIAL_EXCEPTION:
            self.reestablish_arduino_comm()

        # Restore button to "unpressed" appearance
        self.go_button.state(["!pressed"])

    # -------------------------------------------------------------------------
    def reestablish_arduino_comm(self, write_eeprom=False):
        """Method to re-establish communication with the Arduino"""
        self.ivs2.arduino_ready = False
        self.attempt_arduino_handshake(write_eeprom)

    # -------------------------------------------------------------------------
    def usb_monitor(self):
        """Method that runs every 500 milliseconds, checking if the USB cable
           was disconnected. If communication had previously been
           established with the Arduino, it attempts to reestablish
           communication.
        """
        if self.ivs2.arduino_ready and self.ivs2.usb_port_disconnected():
            self.ivs2.arduino_ready = False
            self.go_button.state(["disabled"])
            self.go_button_status_label["text"] = "Not connected"
            self.reestablish_arduino_comm()

        self.after(500, self.usb_monitor)

    # -------------------------------------------------------------------------
    def swing_loop(self, loop_mode=False, first_loop=False):
        """Method that invokes the IVS2 object method to swing the IV curve,
           and then displays the generated GIF in the image pane. In
           loop mode it ends by scheduling another call of itself after
           the programmed delay. In that sense it appears to be a
           loop. Unlike an actual loop, however, it is non-blocking.
           This is essential in order for the GUI not to lock up.

        """
        # pylint: disable=too-many-statements
        def show_error_dialog_clean_up_and_return(rc):
            """Local function to show an error dialog and clean up after a
               failure
            """
            self.show_error_dialog(rc)
            if loop_mode:
                self.stop_actions(event=None)
            self.ivs2.clean_up_after_failure(self.ivs2.hdd_output_dir)
            return rc

        # Clear current_run_displayed flag
        self.props.current_run_displayed = True

        # Capture the start time
        loop_start_time = dt.datetime.now()

        # Add the stop button if needed. Also disable the loop mode
        # checkbuttons.
        self.swing_loop_id = None
        if loop_mode and first_loop:
            self.add_stop_button()
            self.loop_mode_cb.state(["disabled"])
            self.loop_rate_cb.state(["disabled"])
            self.loop_save_cb.state(["disabled"])

        # Swing battery calibration curve if dynamic bias calibration is
        # enabled
        if self.ivs2.battery_bias and self.ivs2.dyn_bias_cal:
            rc = self.ivs2.swing_battery_calibration_curve(gen_graphs=False)
            # Restore config file
            self.props.suppress_cfg_file_copy = True
            self.save_config()
            if rc == RC_SUCCESS:
                # Generate bias battery ADC CSV file
                bias_batt_csv_file = self.ivs2.gen_bias_batt_adc_csv()
                # Remove any previous bias battery calibration CSV
                # files from parent directory
                self.ivs2.remove_prev_bias_battery_csv()
                # Copy calibration CSV file to parent directory
                self.ivs2.copy_file_to_parent(bias_batt_csv_file)
                # Clean up files, depending on mode and options
                self.ivs2.clean_up_files(self.ivs2.hdd_output_dir, loop_mode,
                                         self.props.loop_save_results)
            else:
                err_str = ("ERROR: Failed to swing curve for bias battery")
                tkmsg_showerror(self, message=err_str)
                return show_error_dialog_clean_up_and_return(rc)

        # Turn second relay on for battery + PV curve. This is done
        # regardless of whether dynamic bias calibration is enabled.
        if self.ivs2.battery_bias:
            self.ivs2.second_relay_state = IV_Swinger2.SECOND_RELAY_ON

        # Allow copying the .cfg file to the run directory
        self.props.suppress_cfg_file_copy = False

        # Call the IVS2 method to swing the curve
        if loop_mode and (not self.props.loop_save_results or
                          not self.props.loop_save_graphs):
            self.ivs2.generate_pdf = False
        self.config.remove_axes_and_title()
        rc = self.ivs2.swing_curve(loop_mode=loop_mode)
        self.config.add_axes_and_title()
        self.config.update_vref()
        self.ivs2.generate_pdf = True

        if rc == RC_SUCCESS:
            # Update the image pane with the new curve GIF
            self.display_img(self.ivs2.current_img)
            self.props.current_run_displayed = True
        elif (loop_mode and
              not self.props.loop_stop_on_err and
              (rc == RC_ZERO_ISC or rc == RC_ZERO_VOC or
               rc == RC_ISC_TIMEOUT)):
            # If it failed and we're in loop mode with the stop-on-error option
            # disabled and the error is non-fatal, just clean up and continue
            # after displaying the error message on the screen
            self.display_screen_err_msg(rc)
            self.ivs2.clean_up_after_failure(self.ivs2.hdd_output_dir)
        else:
            # Otherwise return without generating graphs if it failed,
            # displaying reason in a dialog
            return show_error_dialog_clean_up_and_return(rc)

        # Schedule another call with "after" if looping
        if loop_mode:
            elapsed_time = dt.datetime.now() - loop_start_time
            elapsed_ms = int(round(elapsed_time.total_seconds() * 1000))
            delay_ms = self.props.loop_delay * 1000 - elapsed_ms
            if not self.props.loop_rate_limit or delay_ms <= 0:
                delay_ms = 1
            thread_id = self.after(delay_ms,
                                   lambda: self.swing_loop(loop_mode=True,
                                                           first_loop=False))
            # Captured id is used to cancel when stop button is pressed
            self.swing_loop_id = thread_id

        # Save the config to capture current max x,y values and Vref
        self.save_config()

        # Clean up files, depending on mode and options
        self.ivs2.clean_up_files(self.ivs2.hdd_output_dir, loop_mode,
                                 self.props.loop_save_results,
                                 self.props.loop_save_graphs)

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def display_img(self, img_file):
        """Method to display an image (from a file) in the image pane. This
           method does not do any scaling, so the image is displayed at
           its native size.
        """
        self.img_file = img_file
        new_img = tk.PhotoImage(file=img_file)
        self.img_pane.configure(image=new_img)
        self.img_pane.configure(text="")
        self.img_pane.image = new_img
        self.img_pane.splash_img_showing = False
        # Update values in range boxes
        self.update_axis_ranges()
        self.update_idletasks()

    # -------------------------------------------------------------------------
    def display_screen_err_msg(self, rc):
        """Method to display an error message in the image pane. This is used
           for non-fatal errors that are detected while looping, when
           the stop-on-error option is not enabled.
        """
        dts = IV_Swinger2.extract_date_time_str(self.ivs2.hdd_output_dir)
        xlated = IV_Swinger2.xlate_date_time_str(dts)
        (xlated_date, xlated_time) = xlated
        screen_msg = "{}@{}".format(xlated_date, xlated_time)
        screen_msg += "\n\n"
        screen_msg += "** Curve trace FAILED **"
        screen_msg += "\n\n"
        if rc == RC_ISC_TIMEOUT:
            screen_msg += self.isc_timeout_str
        elif rc == RC_ZERO_VOC:
            screen_msg += self.zero_voc_str
        else:
            screen_msg += self.zero_isc_str
        self.img_pane.display_error_img(screen_msg)
        self.img_pane.splash_img_showing = True  # Hack
        self.update_idletasks()

    # -------------------------------------------------------------------------
    def add_stop_button(self):
        """Method to create the stop button. The stop button is only created
           when we're in loop mode. Its size and location are the same
           as the go button, so it just covers up the go button (from
           the user's point of view it just looks like the label on the
           button changes). When the stop button is pressed, the looping
           is stopped, and the button is removed.
        """
        self.stop_button = GoStopButton(master=self.go_button_box, text="STOP")
        self.stop_button["width"] = self.go_button["width"]
        # Tooltip
        tt_text = "Press button to stop looping"
        Tooltip(self.stop_button, text=tt_text, **BOT_TT_KWARGS)
        self.stop_button.bind("<Button-1>", self.stop_actions)
        self.root.bind("<Return>", self.stop_actions)
        self.root.bind("<space>", self.stop_actions)
        self.stop_button.grid(column=0, row=0)
        self.update_idletasks()

    # -------------------------------------------------------------------------
    def stop_actions(self, event=None):
        """Method to stop looping and restore the normal buttons and
           bindings
        """
        # pylint: disable=unused-argument

        # Restore normal bindings of return key and space bar
        self.root.bind("<Return>", self.go_actions)
        self.root.bind("<space>", self.go_actions)

        # Cancel scheduled swing loop
        if self.swing_loop_id is not None:
            self.after_cancel(self.swing_loop_id)

        # Remove the stop button
        self.stop_button.destroy()

        # Re-enable loop checkbuttons
        self.loop_mode_cb.state(["!disabled"])
        self.loop_rate_cb.state(["!disabled"])
        self.loop_save_cb.state(["!disabled"])

    # -------------------------------------------------------------------------
    def show_baud_mismatch_dialog(self):
        """Method to display an error dialog on a (probable) baud mismatch
           error
        """
        baud_mismatch_str = """
ERROR: Decode error on serial data from
Arduino

This is mostly likely a baud rate
mismatch. The baud rate is hardcoded in
the Arduino sketch, and this must match
the rate specified in Preferences.
"""
        tkmsg_showerror(self, message=baud_mismatch_str)

    # -------------------------------------------------------------------------
    def show_timeout_dialog(self):
        """Method to display an error dialog on an Arduino timeout"""
        timeout_str = """
ERROR: Timed out waiting for message
from Arduino

Check that the IV Swinger 2 is connected
to a USB port and the green LED on the
Arduino is lit.

Check that the correct port is selected
on the "USB Port" menu.
"""
        tkmsg_showerror(self, message=timeout_str)

    # -------------------------------------------------------------------------
    def show_serial_exception_dialog(self):
        """Method to display an error dialog on USB serial exception"""
        serial_exception_str = """
ERROR: problem opening USB port to
communicate with Arduino

Check that the IV Swinger 2 is connected
to a USB port and the green LED on the
Arduino is lit.

Check that the correct port is selected
on the "USB Port" menu.
"""
        tkmsg_showerror(self, message=serial_exception_str)

    # -------------------------------------------------------------------------
    def show_zero_voc_dialog(self):
        """Method to display an error dialog when Voc = 0"""
        tkmsg_showerror(self, message=self.zero_voc_str)

    # -------------------------------------------------------------------------
    def show_zero_isc_dialog(self):
        """Method to display an error dialog when Isc = 0"""
        tkmsg_showerror(self, message=self.zero_isc_str)

    # -------------------------------------------------------------------------
    def show_isc_timeout_dialog(self):
        """Method to display an error dialog when there is an Isc stable
           timeout
        """
        tkmsg_showerror(self, message=self.isc_timeout_str)

    # -------------------------------------------------------------------------
    def show_no_points_dialog(self):
        """Method to display an error dialog when there are no points to
           display
        """
        no_points_str = """
ERROR: No points to display

This could be a result of selecting "Battery bias" in Preferences when no
bias was actually applied.
"""
        tkmsg_showerror(self, message=no_points_str)

    # -------------------------------------------------------------------------
    def show_error_dialog(self, rc):
        """Method to call the appropriate error dialog method, based on the
           value of the bad return code
        """
        if rc == RC_BAUD_MISMATCH:
            self.show_baud_mismatch_dialog()
        elif rc == RC_TIMEOUT:
            self.show_timeout_dialog()
        elif rc == RC_SERIAL_EXCEPTION:
            self.show_serial_exception_dialog()
        elif rc == RC_ZERO_VOC:
            self.show_zero_voc_dialog()
        elif rc == RC_ZERO_ISC:
            self.show_zero_isc_dialog()
        elif rc == RC_ISC_TIMEOUT:
            self.show_isc_timeout_dialog()
        elif rc == RC_NO_POINTS:
            self.show_no_points_dialog()

    # -------------------------------------------------------------------------
    def start_on_top(self):
        """Method to cause the app to open on top of other existing
           applications' windows
        """
        # Causes app to open on top of existing windows
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after_idle(self.root.attributes, "-topmost", False)

    # -------------------------------------------------------------------------
    def start_centered(self):
        """Method to cause app to open centered (side-to-side) on screen,
           aligned to top (5 pixel overscan compensation)
        """
        self.root.geometry("+{}+5".format((self.root.winfo_screenwidth()/2) -
                                          (self.ivs2.x_pixels/2)))

    # -------------------------------------------------------------------------
    def start_to_right(self):
        """Method to cause app to open to the right of the screen (with 20
           pixels left), aligned to top (5 pixel overscan compensation)
        """
        self.root.geometry("+{}+5".format(self.root.winfo_screenwidth() -
                                          self.ivs2.x_pixels - 20))

    # -------------------------------------------------------------------------
    def start_to_left(self):
        """Method to cause app to open to the left of the screen, aligned to top
           (5 pixel overscan compensation)
        """
        self.root.geometry("+20+5")

    # -------------------------------------------------------------------------
    def close_gui(self):
        """Method to perform actions needed when the GUI is closed"""
        # Clean up before closing
        if self.props.overlay_dir is not None:
            self.results_wiz.rm_overlay_if_unfinished()
            self.ivs2.clean_up_files(self.props.overlay_dir)
        if self.ivs2.hdd_output_dir is not None:
            self.ivs2.clean_up_files(self.ivs2.hdd_output_dir)
        IV_Swinger2.close_plots()
        # Log configuration differences relative to starting values
        self.config.log_cfg_diffs()
        # Add newline to end of log file
        IV_Swinger2.terminate_log()
        # Close the app
        self.root.destroy()

    # -------------------------------------------------------------------------
    def unlock_axes(self):
        """Method to unlock the axes"""
        self.ivs2.plot_lock_axis_ranges = False
        self.ivs2.plot_max_x = None
        self.ivs2.plot_max_y = None
        self.range_lock_cb.update_axis_lock(None)
        self.axes_locked.set("Unlock")

    # -------------------------------------------------------------------------
    def run(self):
        """Method to run the GUI. It also schedules a call to
           attempt_arduino_handshake() so that the go button is enabled
           as early as possible if the hardware is connected when the
           app is started. This method blocks until the GUI is closed.
        """
        self.after(100, self.attempt_arduino_handshake)
        self.start_on_top()
        self.root.protocol("WM_DELETE_WINDOW", self.close_gui)
        self.root.mainloop()


# GUI properties class
#
class GraphicalUserInterfaceProps(object):
    """Class to hold the properties for the GraphicalUserInterface class.
       This is necessary because properties only work with new-style
       classes (i.e. those derived from "object")
    """
    # pylint: disable=protected-access

    # Initializer
    def __init__(self, master=None):
        self.master = master

    # ---------------------------------
    @property
    def restore_loop(self):
        """True if loop settings should be restored on next startup,
           false otherwise
        """
        return self.master._restore_loop

    @restore_loop.setter
    def restore_loop(self, value):
        if value not in set([True, False]):
            raise ValueError("restore_loop must be boolean")
        self.master._restore_loop = value

    # ---------------------------------
    @property
    def loop_stop_on_err(self):
        """True if looping should stop on non-fatal errors, false if
           looping should continue on non-fatal errors
        """
        return self.master._loop_stop_on_err

    @loop_stop_on_err.setter
    def loop_stop_on_err(self, value):
        if value not in set([True, False]):
            raise ValueError("loop_stop_on_err must be boolean")
        self.master._loop_stop_on_err = value

    # ---------------------------------
    @property
    def loop_mode_active(self):
        """True if loop mode is active, false otherwise
        """
        return self.master._loop_mode_active

    @loop_mode_active.setter
    def loop_mode_active(self, value):
        if value not in set([True, False]):
            raise ValueError("loop_mode_active must be boolean")
        self.master._loop_mode_active = value

    # ---------------------------------
    @property
    def loop_rate_limit(self):
        """True if loop rate limiting is in effect, false otherwise
        """
        return self.master._loop_rate_limit

    @loop_rate_limit.setter
    def loop_rate_limit(self, value):
        if value not in set([True, False]):
            raise ValueError("loop_rate_limit must be boolean")
        self.master._loop_rate_limit = value

    # ---------------------------------
    @property
    def loop_delay(self):
        """Seconds to delay between loops
        """
        return self.master._loop_delay

    @loop_delay.setter
    def loop_delay(self, value):
        self.master._loop_delay = value

    # ---------------------------------
    @property
    def loop_save_results(self):
        """True if results should be saved while looping, false otherwise
        """
        return self.master._loop_save_results

    @loop_save_results.setter
    def loop_save_results(self, value):
        if value not in set([True, False]):
            raise ValueError("loop_save_results must be boolean")
        self.master._loop_save_results = value

    # ---------------------------------
    @property
    def loop_save_graphs(self):
        """True if graphs should be saved while looping, false otherwise
        """
        return self.master._loop_save_graphs

    @loop_save_graphs.setter
    def loop_save_graphs(self, value):
        if value not in set([True, False]):
            raise ValueError("loop_save_graphs must be boolean")
        self.master._loop_save_graphs = value

    # ---------------------------------
    @property
    def suppress_cfg_file_copy(self):
        """True if copying the config file should be suppressed
        """
        return self.master._suppress_cfg_file_copy

    @suppress_cfg_file_copy.setter
    def suppress_cfg_file_copy(self, value):
        if value not in set([True, False]):
            raise ValueError("suppress_cfg_file_copy must be boolean")
        self.master._suppress_cfg_file_copy = value

    # ---------------------------------
    @property
    def overlay_names(self):
        """Dict containing mapping of dts to name for overlay curves
        """
        return self.master._overlay_names

    @overlay_names.setter
    def overlay_names(self, value):
        self.master._overlay_names = value

    # ---------------------------------
    @property
    def overlay_dir(self):
        """Name of directory for current overlay
        """
        return self.master._overlay_dir

    @overlay_dir.setter
    def overlay_dir(self, value):
        self.master._overlay_dir = value

    # ---------------------------------
    @property
    def overlay_mode(self):
        """True if the Results Wizard is in overlay mode
        """
        return self.master._overlay_mode

    @overlay_mode.setter
    def overlay_mode(self, value):
        if value not in set([True, False]):
            raise ValueError("overlay_mode must be boolean")
        self.master._overlay_mode = value

    # ---------------------------------
    @property
    def redisplay_after_axes_unlock(self):
        """True if the current image should be redisplayed after the axes are
           unlocked
        """
        return self.master._redisplay_after_axes_unlock

    @redisplay_after_axes_unlock.setter
    def redisplay_after_axes_unlock(self, value):
        if value not in set([True, False]):
            raise ValueError("redisplay_after_axes_unlock must be boolean")
        self.master._redisplay_after_axes_unlock = value

    # ---------------------------------
    @property
    def current_run_displayed(self):
        """True if the current run is displayed on the screen (as opposed to the
           splash screen, or an older run).
        """
        return self.master._current_run_displayed

    @current_run_displayed.setter
    def current_run_displayed(self, value):
        if value not in set([True, False]):
            raise ValueError("current_run_displayed must be boolean")
        self.master._current_run_displayed = value


# GUI Configuration class
#
class Configuration(IV_Swinger2.Configuration):
    """Class that extends the IV_Swinger2 Configuration class to add the
       looping configuration values
    """

    # Initializer
    def __init__(self, gui=None):
        self.gui = gui
        self.ivs2 = gui.ivs2
        IV_Swinger2.Configuration.__init__(self, self.ivs2)

    # -------------------------------------------------------------------------
    def apply_all(self):
        """Method that is an extension of the parent class method
        """
        # Call parent method
        super(Configuration, self).apply_all()

        # Looping section
        if self.cfg.has_section("Looping"):
            self.apply_looping()

    # -------------------------------------------------------------------------
    def apply_looping(self):
        """Method to apply the Looping section options read from the
           .cfg file to the associated object properties
        """
        section = "Looping"

        # Restore values
        args = (section, "restore values", CFG_BOOLEAN,
                self.gui.props.restore_loop)
        self.gui.props.restore_loop = self.apply_one(*args)

        # Stop on error
        args = (section, "stop on error", CFG_BOOLEAN,
                self.gui.props.loop_stop_on_err)
        self.gui.props.loop_stop_on_err = self.apply_one(*args)

        if self.gui.props.restore_loop:
            # Loop mode
            args = (section, "loop mode", CFG_BOOLEAN,
                    self.gui.props.loop_mode_active)
            self.gui.props.loop_mode_active = self.apply_one(*args)

            # Rate limit
            args = (section, "rate limit", CFG_BOOLEAN,
                    self.gui.props.loop_rate_limit)
            self.gui.props.loop_rate_limit = self.apply_one(*args)

            # Delay
            args = (section, "delay", CFG_INT, self.gui.props.loop_delay)
            self.gui.props.loop_delay = self.apply_one(*args)

            # Save results
            args = (section, "save results", CFG_BOOLEAN,
                    self.gui.props.loop_save_results)
            self.gui.props.loop_save_results = self.apply_one(*args)

            # Save graphs
            args = (section, "save graphs", CFG_BOOLEAN,
                    self.gui.props.loop_save_graphs)
            self.gui.props.loop_save_graphs = self.apply_one(*args)

    # -------------------------------------------------------------------------
    def populate(self):
        """Method that is an extension of the parent class method
        """
        # Call parent method
        super(Configuration, self).populate()

        # Add looping config
        section = "Looping"
        self.cfg.add_section(section)
        self.cfg_set(section, "restore values", self.gui.props.restore_loop)
        self.cfg_set(section, "stop on error", self.gui.props.loop_stop_on_err)
        self.cfg_set(section, "loop mode", self.gui.props.loop_mode_active)
        self.cfg_set(section, "rate limit", self.gui.props.loop_rate_limit)
        self.cfg_set(section, "delay", self.gui.props.loop_delay)
        self.cfg_set(section, "save results", self.gui.props.loop_save_results)
        self.cfg_set(section, "save graphs", self.gui.props.loop_save_graphs)

    # -------------------------------------------------------------------------
    def get(self):
        """Method that is an extension of the parent class method
        """
        # Call parent method
        super(Configuration, self).get()

        # If config doesn't include looping section, re-populate it
        if not self.cfg.has_section("Looping"):
            self.populate()


# Image size combobox class
#
class ImgSizeCombo(ttk.Combobox):
    """Class that is the Combobox used to select image size"""
    # pylint: disable=too-many-ancestors

    # Initializer
    def __init__(self, master=None, textvariable=None):
        ttk.Combobox.__init__(self, master=master, textvariable=textvariable)
        y_pixels = int(round(master.ivs2.x_pixels *
                             master.ivs2.plot_y_inches /
                             master.ivs2.plot_x_inches))
        curr_size = "{}x{}".format(master.ivs2.x_pixels, y_pixels)
        textvariable.set(curr_size)
        self["values"] = ("550x425",
                          "660x510",
                          "770x595",
                          "880x680",
                          "990x765",
                          "1100x850")
        self["width"] = 10


# Results wizard class
#
class ResultsWizard(tk.Toplevel):
    """Class that implements the Results wizard. Unlike other dialogs that
       are extensions of the generic Dialog class, this is NOT a "modal
       window", so it does not completely block access to the main
       window. This is so the user can still do things like changing
       preferences. However, certain actions are disallowed in the main
       window such as the Go button and the Results Wizard button since
       allowing those actions while the results wizard is open is not
       useful or at least the expected behavior if they were allowed is
       not obvious.
    """
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods

    # Initializer
    def __init__(self, master=None):
        tk.Toplevel.__init__(self, master=master)
        self.master = master
        self.title("Results Wizard")
        self.results_dir = self.master.ivs2.app_data_dir
        self.chron_dir = None
        self.copy_dest = None
        self.dates = None
        self.done_button = None
        self.ivp = None
        self.label_all_iscs_cb = None
        self.label_all_mpps_cb = None
        self.label_all_vocs_cb = None
        self.mpp_watts_only_cb = None
        self.overlaid_runs = None
        self.overlay_cancel_button = None
        self.overlay_finish_button = None
        self.overlay_help_button = None
        self.overlay_iid = None
        self.overlay_img = None
        self.overlay_title = None
        self.overlay_widget_box = None
        self.overlay_widget_buttonbox = None
        self.overlay_widget_cb_box = None
        self.overlay_widget_label = None
        self.overlay_widget_treeview = None
        self.overlays_reordered = None
        self.right_buttonbox = None
        self.selected_csv_files = []
        self.shortcut_button = None
        self.tree = None
        self.treebox = None
        self.treescroll = None

        # Tie this window to master
        self.transient(self.master)

        # Disable some (but not all) main window functions
        self.constrain_master()

        # Create body frame
        self.body = ttk.Frame(self)

        # Call create_body method to create body contents
        self.create_body(self.body)
        self.body.pack(fill=BOTH, expand=True)

        # Set geometry
        self.master.set_dialog_geometry(self,
                                        min_height=WIZARD_MIN_HEIGHT_PIXELS)

    # -------------------------------------------------------------------------
    def constrain_master(self):
        """Method to disable some of the functionality of the master while the
           wizard is running
        """
        self.master.results_button.state(["disabled"])
        self.master.go_button.state(["disabled"])

    # -------------------------------------------------------------------------
    def change_min_height(self, min_height):
        """Method to change the minimum height of the dialog to the specified
           value
        """
        # Get current window width
        width = get_dialog_width(self)

        # Set minimum size using current width and requested height
        self.minsize(width, min_height)

    # -------------------------------------------------------------------------
    def create_body(self, master):
        """Method to create the dialog body, which contains a Treeview widget
           and some buttons
        """
        self.treeview(master)
        self.buttons(master)

        # Layout
        #  Row 0
        self.treebox.grid(column=0, row=0, sticky=(N, S, E, W))
        self.right_buttonbox.grid(column=1, row=0, sticky=(N, E))
        master.rowconfigure(0, weight=1)
        #  Row 1
        self.shortcut_button.grid(column=0, row=1, sticky=(S, W))
        self.done_button.grid(column=1, row=1, sticky=(S, E))

    # -------------------------------------------------------------------------
    def buttons(self, master):
        """Method to create the dialog buttons"""
        width = 12
        # Right buttons
        self.right_buttonbox = ttk.Frame(master)
        expand_button = ttk.Button(self.right_buttonbox, text="Expand All",
                                   width=width, command=self.expand_all)
        collapse_button = ttk.Button(self.right_buttonbox,
                                     text="Collapse All",
                                     width=width, command=self.collapse_all)
        title_button = ttk.Button(self.right_buttonbox,
                                  text="Change Title",
                                  width=width,
                                  command=self.change_title)
        overlay_button = ttk.Button(self.right_buttonbox,
                                    text="Overlay",
                                    width=width,
                                    command=self.overlay_runs)
        pdf_button = ttk.Button(self.right_buttonbox,
                                text="View PDF",
                                width=width,
                                command=self.view_pdf)
        update_button = ttk.Button(self.right_buttonbox,
                                   text="Update",
                                   width=width,
                                   command=self.update_selected)
        delete_button = ttk.Button(self.right_buttonbox,
                                   text="Delete",
                                   width=width,
                                   command=self.delete_selected)
        copy_button = ttk.Button(self.right_buttonbox,
                                 text="Copy",
                                 width=width,
                                 command=self.copy_selected)

        # Add button tooltips
        tt_text = "Expand all date groupings"
        Tooltip(expand_button, text=tt_text, **TOP_TT_KWARGS)
        tt_text = "Collapse all date groupings"
        Tooltip(collapse_button, text=tt_text, **TOP_TT_KWARGS)
        tt_text = "Change the title of the current plot"
        Tooltip(title_button, text=tt_text, **TOP_TT_KWARGS)
        tt_text = "Combine up to 8 curves on the same plot"
        Tooltip(overlay_button, text=tt_text, **TOP_TT_KWARGS)
        tt_text = "Open the PDF in a viewer"
        Tooltip(pdf_button, text=tt_text, **TOP_TT_KWARGS)
        tt_text = ("Apply current plotting options (including size) to all "
                   "selected runs.  IMPORTANT: Select runs BEFORE making "
                   "changes to plotting options.")
        Tooltip(update_button, text=tt_text, **TOP_TT_KWARGS)
        tt_text = "Send one or more runs or overlays to trash"
        Tooltip(delete_button, text=tt_text, **TOP_TT_KWARGS)
        tt_text = "Copy one or more runs or overlays to USB or elsewhere"
        Tooltip(copy_button, text=tt_text, **TOP_TT_KWARGS)

        # Pack buttons into containing box
        expand_button.pack()
        collapse_button.pack()
        title_button.pack()
        overlay_button.pack()
        pdf_button.pack()
        update_button.pack()
        delete_button.pack()
        copy_button.pack()

        # Shortcut button
        self.shortcut_button = ttk.Button(master)
        self.config_shortcut_button()

        # Done button
        self.done_button = ttk.Button(master, text="Done", width=width,
                                      command=self.done)
        tt_text = "Exit the Results Wizard"
        Tooltip(self.done_button, text=tt_text, **TOP_TT_KWARGS)
        self.protocol("WM_DELETE_WINDOW", self.done)

    # -------------------------------------------------------------------------
    def treeview(self, master):
        """Method to create the Treeview widget and its associated scrollbar"""
        self.treebox = ttk.Frame(master)
        self.tree = ttk.Treeview(self.treebox, selectmode="extended")
        self.treescroll = ttk.Scrollbar(self.treebox, command=self.tree.yview)
        self.tree.configure(yscroll=self.treescroll.set)
        self.tree.bind("<<TreeviewSelect>>", self.select)
        self.configure_tree_size()
        self.tree.insert("", "end", "", text="WORKING...")
        self.master.root.after(100, self.populate_tree)
        tt_text = ("Click on path at the top to change. Shift-click and "
                   "Control-click can be used to select multiple runs "
                   "for overlaying, updating, deleting or copying.")
        Tooltip(self.tree, text=tt_text, **TOP_TT_KWARGS)
        self.tree.pack(side=LEFT)
        self.treescroll.pack(side=LEFT, fill=Y)

    # -------------------------------------------------------------------------
    def populate_tree(self):
        """Method to populate the Treeview. The top level is the date, and each
           of those can be opened (expanded) to see the runs from that
           day.  There is also a top level item for the overlays, and it
           has all of the overlays under it.
        """
        # Remove any prior contents
        self.delete_all()
        self.dates = []

        # Get a list of all of the subdirectories (and files) in the
        # results directory - newest first
        subdirs = sorted(os.listdir(self.results_dir), reverse=True)

        # Step through each one
        for subdir in subdirs:
            # Skip files and empty directories
            full_path = os.path.join(self.results_dir, subdir)
            if not os.path.isdir(full_path):
                continue
            if not os.listdir(full_path):
                continue

            # First handle overlays
            if subdir == "overlays":
                self.populate_overlays(subdir)

            # Then filter out anything that isn't a directory in the
            # canonical date/time string format - these are the runs
            if IV_Swinger2.is_date_time_str(subdir):
                self.populate_runs(subdir)

        # If there are no overlays or run directories, insert a dummy item
        if not self.tree.exists("overlays") and not self.dates:
            self.tree.insert("", "end", "err_msg", text="NO RUNS HERE")

        # Set the column #0 heading
        self.tree.heading("#0", text=self.results_dir,
                          command=self.change_folder)

        self.update_idletasks()

    # -------------------------------------------------------------------------
    def configure_tree_size(self):
        """Method to set the tree height and column width"""
        # Configure a large height so it is never shorter than the
        # window
        self.tree.configure(height=WIZARD_TREE_HEIGHT)

        # Configure the column width to be large enough for a fairly
        # long path in the heading
        self.tree.column("#0", width=WIZARD_TREE_WIDTH)

    # -------------------------------------------------------------------------
    def populate_overlays(self, subdir):
        """Method to populate the overlays part of the Treeview.
        """
        # Add overlays parent to Treeview if it doesn't already exist
        if not self.tree.exists(subdir):
            self.tree.insert("", 0, subdir, text="Overlays")

        # Get a list of the overlay subdirectories, newest first
        overlays = sorted(os.listdir(os.path.join(self.results_dir, subdir)),
                          reverse=True)

        # Step through them
        for overlay in overlays:
            # Full path
            overlay_dir = os.path.join(self.results_dir, subdir, overlay)

            # Then filter out anything that isn't a directory in the
            # canonical date/time string format - these are the overlays
            if (IV_Swinger2.is_date_time_str(overlay) and
                    os.path.isdir(overlay_dir)):

                # Skip empty directories
                if not os.listdir(overlay_dir):
                    continue

                # Translate to human readable date and time
                xlated = IV_Swinger2.xlate_date_time_str(overlay)
                (xlated_date, xlated_time) = xlated

                # Add to tree
                iid = "overlay_{}".format(overlay)
                text = "Created on {} at {}".format(xlated_date, xlated_time)
                self.tree.insert(subdir, "end", iid, text=text)

    # -------------------------------------------------------------------------
    def populate_runs(self, subdir):
        """Method to populate the runs part of the Treeview.
        """
        # Translate to human readable date and time
        xlated = IV_Swinger2.xlate_date_time_str(subdir)
        (xlated_date, xlated_time) = xlated
        date = subdir.split("_")[0]

        # Add a date item (parent to time items) if it doesn't already
        # exist
        if not self.tree.exists(date):
            self.tree.insert("", "end", date, text=xlated_date)
            # Add it to the list of all dates for the expand_all
            # and collapse_all methods
            self.dates.append(date)

        # Get the title from the saved config
        title = None
        run_dir = self.get_run_dir(subdir)
        cfg_file = os.path.join(run_dir, "{}.cfg".format(APP_NAME))
        if os.path.exists(cfg_file):
            title = IV_Swinger2.get_saved_title(cfg_file)
        else:
            title = "   * no saved cfg *"
        if title == "None" or title is None:
            title_str = ""
        else:
            title_str = "   {}".format(title)
            self.master.props.overlay_names[subdir] = title

        # Add child time item (iid is full date_time_str)
        text = xlated_time + title_str
        self.tree.insert(date, "end", subdir, text=text)

    # -------------------------------------------------------------------------
    def delete_all(self):
        """Method to delete all items from the Treeview"""
        self.tree.delete(*self.tree.get_children())

    # -------------------------------------------------------------------------
    def done(self, event=None):
        """Method called when wizard is closed
        """
        # pylint: disable=unused-argument

        # If we're in overlay mode ask user if they want to save the
        # overlay
        if self.master.props.overlay_mode:
            msg_str = "Save overlay before quitting Results Wizard?"
            save_overlay = tkmsg_askyesno(self.master,
                                          "Save overlay?", msg_str,
                                          default=tkmsg.NO)
            if save_overlay:
                # Yes: same as if Finished button had been pressed
                self.overlay_finished(event=None)
                return
            else:
                # No: turn off overlay mode and display non-overlaid
                # image
                self.master.props.overlay_mode = False
                self.overlay_title = None
                self.master.redisplay_img()
        # Remove incomplete overlay
        self.rm_overlay_if_unfinished()
        self.restore_master()
        self.master.props.overlay_mode = False
        self.master.props.overlay_dir = None
        self.master.results_wiz = None
        self.destroy()

    # -------------------------------------------------------------------------
    def restore_master(self):
        """Method to restore focus to the master, re-enable its widgets that
           were disabled while the wizard was open, and restore the
           original configuration
        """
        self.master.focus_set()
        self.master.results_button.state(["!disabled"])
        if self.master.ivs2.arduino_ready:
            self.master.go_button.state(["!disabled"])
        self.master.config.cfg_filename = None  # property will restore
        self.master.config.get()
        self.master.update_plot_power_cb()
        # If the user has explicitly checked the Lock checkbutton, keep
        # the axes locked to the values from the last result that was
        # browsed. Otherwise unlock the axes.
        if self.master.axes_locked.get() == "Unlock":
            self.master.props.redisplay_after_axes_unlock = False
            self.master.unlock_axes()
            self.master.props.redisplay_after_axes_unlock = True

    # -------------------------------------------------------------------------
    def select(self, event=None):
        """Method to handle a select event from the Treeview"""
        # pylint: disable=unused-argument
        selections = self.tree.selection()
        if not selections:
            return
        # If multiple items are selected, last one (oldest) is
        # displayed
        selection = selections[-1]
        if self.master.props.overlay_mode:
            self.overlay_runs(event=None)
        elif selection.startswith("overlay_"):
            self.overlay_select_actions(selection)
        elif IV_Swinger2.is_date_time_str(selection):
            self.non_overlay_select_actions(selection)
        # Clear the flag that indicates that the current run is displayed on
        # the screen. No exception is made if the selected run is the current
        # run.
        self.master.props.current_run_displayed = False

    # -------------------------------------------------------------------------
    def overlay_select_actions(self, selection):
        """Method to display an existing overlay and perform related actions
        """
        dts = IV_Swinger2.extract_date_time_str(selection)
        overlay_dir = os.path.join(self.results_dir, "overlays", dts)
        gif_leaf_name = "overlaid_{}.gif".format(dts)
        gif_full_path = os.path.join(overlay_dir, gif_leaf_name)
        if os.path.exists(gif_full_path):
            self.master.display_img(gif_full_path)
        else:
            # Legacy
            gif_leaf_name = "overlaid.gif"
            gif_full_path = os.path.join(overlay_dir, gif_leaf_name)
            if os.path.exists(gif_full_path):
                self.master.display_img(gif_full_path)

    # -------------------------------------------------------------------------
    def non_overlay_select_actions(self, selection):
        """Method to display a normal (non-overlaid) run and perform related
           actions
        """
        # Get full path to run directory
        run_dir = self.get_run_dir(selection)
        if run_dir is None:
            return

        # Get names of CSV and GIF files
        (csv_data_point_file,
         adc_csv_file,
         gif_file) = self.get_csv_and_gif_names(run_dir, selection)
        if csv_data_point_file is None and adc_csv_file is None:
            return

        # If GIF file exists, display it now
        if gif_file is not None:
            self.master.display_img(gif_file)

        # Prepare IVS2 object for regeneration of plot with modified
        # options
        self.prep_ivs2_for_redisplay(run_dir, adc_csv_file)

        # If config file exists, read it in and update the config
        self.update_to_selected_config(run_dir)

        # If GIF file doesn't exist, generate it from data point CSV
        # file and display it
        if gif_file is None:
            self.master.img_pane.splash_img_showing = False
            if csv_data_point_file is None:
                self.master.redisplay_img(reprocess_adc=True)
            else:
                self.master.redisplay_img(reprocess_adc=False)

    # -------------------------------------------------------------------------
    def get_run_dir(self, selection):
        """Method to determine the path to the run directory for the selection
           and check that it is really a directory
        """
        run_dir = os.path.join(self.results_dir, selection)
        if not os.path.isdir(run_dir):
            err_str = "ERROR: directory {} does not exist".format(run_dir)
            self.master.ivs2.logger.print_and_log(err_str)
            tkmsg_showerror(self.master, message=err_str)
            return None
        return run_dir

    # -------------------------------------------------------------------------
    def get_csv_and_gif_names(self, run_dir, selection):
        """Method to determine the full paths to the two CSV files and the GIF
           file based on the run directory and the selection. Also
           checks that each file exists, and returns None if not
        """
        self.master.ivs2.get_csv_filenames(run_dir, selection)
        csv_data_point_file = self.master.ivs2.hdd_csv_data_point_filename
        adc_csv_file = self.master.ivs2.hdd_adc_pairs_csv_filename
        gif_leaf_name = "{}{}.gif".format(self.master.ivs2.file_prefix,
                                          selection)
        gif_file = os.path.join(run_dir, gif_leaf_name)

        # Check that data point CSV file exists
        if not os.path.exists(csv_data_point_file):
            # Check for IVS1 CSV file
            ivs1_csv_file = os.path.join(self.results_dir, selection,
                                         "data_points_{}.csv"
                                         .format(selection))
            if os.path.exists(ivs1_csv_file):
                csv_data_point_file = ivs1_csv_file
                self.master.ivs2.hdd_csv_data_point_filename = ivs1_csv_file
            else:
                csv_data_point_file = None
        # Check that the ADC CSV file exists
        if not os.path.exists(adc_csv_file):
            adc_csv_file = None
        # Check that the GIF file exists
        if not os.path.exists(gif_file):
            gif_file = None

        return (csv_data_point_file, adc_csv_file, gif_file)

    # -------------------------------------------------------------------------
    def prep_ivs2_for_redisplay(self, run_dir, adc_csv_file):
        """Method to prepare IVS2 object for regeneration of plot with modified
           options
        """
        self.master.ivs2.hdd_output_dir = run_dir
        self.master.ivs2.plot_title = None
        if adc_csv_file is not None and os.path.exists(adc_csv_file):
            adc_pairs = self.master.get_adc_pairs_from_csv(adc_csv_file)
            self.master.ivs2.adc_pairs = adc_pairs
        else:
            self.master.ivs2.adc_pairs = None

    # -------------------------------------------------------------------------
    def update_to_selected_config(self, run_dir):
        """Method to read config file, if it exists, and update the config
        """
        self.master.props.suppress_cfg_file_copy = False
        cfg_file = os.path.join(run_dir, "{}.cfg".format(APP_NAME))
        if cfg_file == self.master.config.cfg_filename:
            return
        if os.path.exists(cfg_file):
            self.master.config.get_old_result(cfg_file)
            self.master.update_plot_power_cb()
            self.master.update_axis_ranges()
            # Change the IVS2 object config file property to point to
            # this one
            self.master.config.cfg_filename = cfg_file
        else:
            # Indicate that axis ranges are unknown
            self.master.v_range.set("<unknown>")
            self.master.i_range.set("<unknown>")
            # Set flag to suppress copying the .cfg file if there
            # wasn't already one in this directory
            self.master.props.suppress_cfg_file_copy = True

    # -------------------------------------------------------------------------
    def change_folder(self, event=None):
        """Method to handle the change folder event (click on treeview
           column heading)
        """
        # pylint: disable=unused-argument
        options = {}
        options["initialdir"] = self.results_dir
        options["parent"] = self.master
        options["title"] = "Choose Folder"
        if self.master.win_sys == "aqua":  # Mac
            options["message"] = options["title"]
        new_dir = tkFileDialog.askdirectory(**options)
        self.master.mac_grayed_menu_workaround()
        if new_dir:
            self.results_dir = os.path.normpath(new_dir)
            self.populate_tree()
            if not self.tree.exists("overlays") and not self.dates:
                # If there are no overlays or runs in the specified folder, but
                # there is a subfolder named IV_Swinger2 or the parent
                # directory is named IV_Swinger2, then assume the user meant to
                # select the subfolder or parent folder respectively
                ivs2_subdir = os.path.join(self.results_dir, APP_NAME)
                parent_dir = os.path.dirname(self.results_dir)
                if os.path.isdir(ivs2_subdir):
                    self.results_dir = ivs2_subdir
                    self.populate_tree()
                elif os.path.basename(parent_dir) == APP_NAME:
                    self.results_dir = parent_dir
                    self.populate_tree()
            self.config_import_button()

    # -------------------------------------------------------------------------
    def config_shortcut_button(self):
        """Method to configure the shortcut button normally"""
        self.shortcut_button["text"] = "Make desktop shortcut"
        self.shortcut_button["command"] = self.make_shortcut
        tt_text = "Create a desktop shortcut to results folder"
        Tooltip(self.shortcut_button, text=tt_text, **TOP_TT_KWARGS)

    # -------------------------------------------------------------------------
    def config_import_button(self):
        """Method to configure the shortcut button as the import button"""
        self.shortcut_button["text"] = "Import"
        self.shortcut_button["command"] = self.import_results
        tt_text = ("Import results to {} from {}"
                   .format(self.master.ivs2.app_data_dir, self.results_dir))
        Tooltip(self.shortcut_button, text=tt_text, **TOP_TT_KWARGS)

    # -------------------------------------------------------------------------
    def make_shortcut(self, event=None):
        """Method to create a desktop shortcut to the app data folder
        """
        # pylint: disable=unused-argument
        # pylint: disable=too-many-branches

        # Find path to Desktop
        desktop_path = os.path.expanduser(os.path.join("~", "Desktop"))
        if not os.path.exists(desktop_path):
            err_str = "ERROR: {} does not exist".format(desktop_path)
            tkmsg_showerror(self.master, message=err_str)

        # Define shortcut name
        desktop_shortcut_path = os.path.join(desktop_path, "IV_Swinger2")

        result = None

        if sys.platform == "win32":
            import win32com.client  # pylint: disable=import-error
            # For Windows, use win32com
            desktop_shortcut_path += ".lnk"
            try:
                ws = win32com.client.Dispatch("wscript.shell")
                shortcut = ws.CreateShortcut(desktop_shortcut_path)
                if shortcut.TargetPath:
                    curr_value = shortcut.TargetPath
                    if curr_value == self.master.ivs2.app_data_dir:
                        result = "EXISTS_SAME"
                    else:
                        result = "EXISTS_DIFFERENT"
                else:
                    shortcut.TargetPath = self.master.ivs2.app_data_dir
                    shortcut.Save()
                    result = "CREATED"
            except:  # pylint: disable=bare-except
                result = "FAILED"
        else:
            # For Mac or Linux, just create a symlink
            if os.path.exists(desktop_shortcut_path):
                if os.path.islink(desktop_shortcut_path):
                    curr_value = os.readlink(desktop_shortcut_path)
                    if curr_value == self.master.ivs2.app_data_dir:
                        result = "EXISTS_SAME"
                    else:
                        result = "EXISTS_DIFFERENT"
            else:
                try:
                    os.symlink(self.master.ivs2.app_data_dir,
                               desktop_shortcut_path)
                    result = "CREATED"
                except:  # pylint: disable=bare-except
                    result = "FAILED"

        if result == "CREATED":
            msg_str = "Shortcut created:\n  {}".format(desktop_shortcut_path)
        elif result == "EXISTS_SAME":
            msg_str = "Shortcut already exists"
        elif result == "EXISTS_DIFFERENT":
            msg_str = ("ERROR: Shortcut\n  {}"
                       "\nalready exists, but its target is:\n  {}"
                       "\ninstead of:\n  {}"
                       .format(desktop_shortcut_path,
                               curr_value,
                               self.results_dir))
        elif result == "FAILED":
            msg_str = "ERROR: could not create shortcut"
        else:
            msg_str = "ERROR: Programming bug"
        tkmsg_showerror(self.master, message=msg_str)

    # -------------------------------------------------------------------------
    def import_results(self, event=None):
        """Method to import results to app data folder"""
        # pylint: disable=unused-argument

        # Get the selected run(s) from the Treeview
        import_runs = self.get_selected_runs()

        # Get the selected overlay(s) from the Treeview
        import_overlays = self.get_selected_overlays()

        # Import everything if nothing is selected
        if not import_runs and not import_overlays:
            # Get the list of runs to import from the current tree
            import_runs = []
            for date in self.dates:
                for run in self.tree.get_children(date):
                    run_path = os.path.join(self.results_dir, run)
                    import_runs.append(run_path)

            # Get the list of overlays to import
            import_overlays = []
            if self.tree.exists("overlays"):
                for overlay in self.tree.get_children("overlays"):
                    dts = IV_Swinger2.extract_date_time_str(overlay)
                    overlay_path = os.path.join(self.results_dir,
                                                "overlays", dts)
                    import_overlays.append(overlay_path)

        all_import = import_runs + import_overlays

        # Set the copy destination to the parent of the app data folder
        # (i.e. strip off the IV_Swinger2)
        self.copy_dest = os.path.dirname(self.master.ivs2.app_data_dir)

        # Do a "dry run" to check if any of the directories to be
        # copied to already exist. If so, ask user for permission to
        # overwrite (or not).
        overwrite = self.copy_overwrite_precheck(all_import)

        # Copy all directories
        num_copied = self.copy_dirs(all_import, overwrite)

        # Display a summary message
        self.display_copy_summary(num_copied)

        # Restore the tree to the app data folder
        self.results_dir = self.master.ivs2.app_data_dir
        self.populate_tree()
        self.config_shortcut_button()

    # -------------------------------------------------------------------------
    def expand_all(self, event=None):
        """Method to expand/open all Treeview date groupings (click on
           button)
        """
        # pylint: disable=unused-argument

        for date in self.dates:
            self.tree.item(date, open=True)

    # -------------------------------------------------------------------------
    def collapse_all(self, event=None):
        """Method to collapse/close all Treeview date groupings (click
           on button)
        """
        # pylint: disable=unused-argument

        for date in self.dates:
            self.tree.item(date, open=False)

    # -------------------------------------------------------------------------
    def get_copy_dest(self):
        """Method to get the copy destination from the user
        """
        # Open a tkFileDialog to get user to choose a destination
        options = {}
        options["parent"] = self.master
        options["title"] = "Choose Copy Destination"
        if self.master.win_sys == "aqua":  # Mac
            options["message"] = options["title"]
        copy_dest = tkFileDialog.askdirectory(**options)
        self.master.mac_grayed_menu_workaround()
        if not copy_dest:  # Cancel
            return RC_FAILURE
        self.copy_dest = os.path.normpath(copy_dest)

        # If leaf directory is named IV_Swinger2, assume the user meant
        # to choose its parent directory
        if os.path.basename(self.copy_dest) == APP_NAME:
            self.copy_dest = os.path.dirname(self.copy_dest)

        # Check that it is writeable
        if not os.access(self.copy_dest, os.W_OK | os.X_OK):
            err_str = "ERROR: {} is not writeable".format(self.copy_dest)
            tkmsg_showerror(self.master, message=err_str)
            return RC_FAILURE

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def delete_selected(self, event=None):
        """Method to send the selected runs and/or overlays to the
           trash
        """
        # pylint: disable=unused-argument

        # Get the selected run(s) from the Treeview
        selected_runs = self.get_selected_runs()

        # Get the selected overlay(s) from the Treeview
        selected_overlays = self.get_selected_overlays()

        # Display error dialog and return if nothing is selected
        if not selected_runs and not selected_overlays:
            tkmsg_showerror(self.master,
                            message="ERROR: no runs or overlays are selected")
            return

        # Display error dialog and return if in overlay mode
        if self.master.props.overlay_mode:
            err_msg = "ERROR: cannot perform a delete in overlay mode"
            tkmsg_showerror(self.master, message=err_msg)
            return

        all_selected = selected_runs + selected_overlays

        if self.ok_to_trash(len(selected_runs), len(selected_overlays)):
            # Send selected runs and overlays to trash
            for selected in all_selected:
                try:
                    send2trash(selected)
                except OSError:
                    err_str = ("WARNING: Couldn't send {} to trash"
                               .format(selected))
                    self.master.ivs2.logger.print_and_log(err_str)

            # Delete them from the treeview
            self.tree.delete(*self.tree.selection())

    # -------------------------------------------------------------------------
    def ok_to_trash(self, num_selected_runs, num_selected_overlays):
        """Method to prompt the user before moving runs and overlays to the
           trash
        """
        msg_str = ""
        if num_selected_runs:
            msg_str += ("Send {} runs to the trash?\n"
                        .format(num_selected_runs))
        if num_selected_overlays:
            msg_str += ("Send {} overlays to the trash?\n"
                        .format(num_selected_overlays))
        granted = tkmsg_askyesno(self.master,
                                 "OK to send to trash?", msg_str,
                                 default=tkmsg.NO)
        return granted

    # -------------------------------------------------------------------------
    def copy_selected(self, event=None):
        """Method to copy the selected runs and/or overlays (to a USB
           drive or elsewhere)
        """
        # pylint: disable=unused-argument

        # Get the selected run(s) from the Treeview
        selected_runs = self.get_selected_runs()

        # Get the selected overlay(s) from the Treeview
        selected_overlays = self.get_selected_overlays()

        # Display error dialog and return if nothing is selected
        if not selected_runs and not selected_overlays:
            tkmsg_showerror(self.master,
                            message="ERROR: no runs or overlays are selected")
            return

        # Display error dialog and return if in overlay mode
        if self.master.props.overlay_mode:
            err_msg = "ERROR: cannot perform a copy in overlay mode"
            tkmsg_showerror(self.master, message=err_msg)
            return

        # Get destination from user
        rc = self.get_copy_dest()
        if rc != RC_SUCCESS:
            return

        all_selected = selected_runs + selected_overlays

        # Do a "dry run" to check if any of the directories to be
        # copied to already exist. If so, ask user for permission to
        # overwrite (or not).
        overwrite = self.copy_overwrite_precheck(all_selected)

        # Copy all directories
        num_copied = self.copy_dirs(all_selected, overwrite)

        # Display a summary message
        self.display_copy_summary(num_copied)

    # -------------------------------------------------------------------------
    def get_selected_runs(self, include_whole_days=True):
        """Method to get all of the selected runs (optionally including the
           children of selected whole-day groupings) and return them in
           a list
        """
        selected_runs = []

        # Get the selection(s)
        selections = self.tree.selection()

        # Separate them into individual runs and whole day
        # groupings. Add the individual runs and the children of the
        # whole day groupings to the selected_runs list.
        for selection in selections:
            individual_run = IV_Swinger2.is_date_time_str(selection)
            is_date_group = re.compile(r"^(\d{6})$").search(selection)
            if individual_run:
                selected_runs.append(os.path.join(self.results_dir, selection))
            elif (include_whole_days and is_date_group and not
                  (IV_Swinger2.is_date_time_str(selections[0]) or
                   IV_Swinger2.is_date_time_str(selections[-1]))):
                # Whole day (but not in the middle of a range of
                # individual runs)
                for child in self.tree.get_children(selection):
                    # Add all the day's runs to the list
                    selected_runs.append(os.path.join(self.results_dir, child))

        return selected_runs

    # -------------------------------------------------------------------------
    def get_selected_overlays(self):
        """Method to get all of the selected overlays and return them in a list
        """
        selected_overlays = []

        # Get the selection(s)
        selections = self.tree.selection()

        for selection in selections:
            # Add all of the overlays if the whole group is selected,
            # but not if the last selection is an individual overlay
            # (DWIM)
            if (selection == "overlays" and
                    not selections[-1].startswith("overlay_")):
                for child in self.tree.get_children(selection):
                    # Add all the overlays to the list
                    dts = IV_Swinger2.extract_date_time_str(child)
                    selected_overlays.append(os.path.join(self.results_dir,
                                                          "overlays", dts))
            # Add individual overlay
            if selection.startswith("overlay_"):
                dts = IV_Swinger2.extract_date_time_str(selection)
                selected_overlays.append(os.path.join(self.results_dir,
                                                      "overlays", dts))

        return selected_overlays

    # -------------------------------------------------------------------------
    def copy_overwrite_precheck(self, selected_src_dirs):
        """Method to check if the selected runs/overlays already exist in the
           destination directory, and if so, to ask user if they should be
           overwritten or not
        """
        overwrite = False
        existing_dest_dirs = []

        # Dry run loop through drives and selected runs checking for
        # existing directories in destination
        for src_dir in selected_src_dirs:
            dest_dir = self.get_dest_dir(src_dir)
            if dest_dir == src_dir:
                err_str = ("ERROR: source and destination are the same: {}"
                           .format(os.path.dirname(dest_dir)))
                tkmsg_showerror(self.master, message=err_str)
                return False
            if os.path.exists(dest_dir):
                existing_dest_dirs.append(dest_dir)

        if existing_dest_dirs:
            if len(existing_dest_dirs) > 10:
                # If more than 10 found, just prompt with the count found
                msg_str = ("{} folders to be copied exist in {}\n"
                           .format(len(existing_dest_dirs),
                                   os.path.join(self.copy_dest, APP_NAME)))
            else:
                # If 1-10 found, prompt with the list of names
                msg_str = "The following destination folder(s) exist(s):\n"
                for dest_dir in existing_dest_dirs:
                    msg_str += "  {}\n".format(dest_dir)
            msg_str += "\nOverwrite all?"
            overwrite = tkmsg_askyesno(self.master,
                                       "Overwrite all?", msg_str,
                                       default=tkmsg.NO)
        return overwrite

    # -------------------------------------------------------------------------
    def copy_dirs(self, src_dirs, overwrite):
        """Method to copy the specified directories to the destination,
           overwriting or not, based on input parameter. Returns number of
           runs copied.
        """
        num_copied = {"overlays": 0, "runs": 0}
        for src_dir in src_dirs:
            dest_dir = self.get_dest_dir(src_dir)
            if os.path.exists(dest_dir):
                if overwrite:
                    try:
                        shutil.rmtree(dest_dir)
                    except (IOError, OSError, shutil.Error) as e:
                        err_str = ("ERROR: removing {} ({})"
                                   .format(dest_dir, e))
                        tkmsg_showerror(self.master, message=err_str)
                        continue
                else:
                    continue  # pragma: no cover (coverage bug?)
            try:
                shutil.copytree(src_dir, dest_dir)
                if os.path.basename(os.path.dirname(src_dir)) == "overlays":
                    num_copied["overlays"] += 1
                else:
                    num_copied["runs"] += 1
                self.master.ivs2.logger.log("Copied {} to {}"
                                            .format(src_dir, dest_dir))
            except (IOError, OSError, shutil.Error) as e:
                err_str = ("ERROR: error copying {} to {}\n({})"
                           .format(src_dir, dest_dir, e))
                tkmsg_showerror(self.master, message=err_str)

        return num_copied

    # -------------------------------------------------------------------------
    def get_dest_dir(self, src_dir):
        """Method to derive the destination directory name from the source
           directory name
        """
        if os.path.basename(os.path.dirname(src_dir)) == "overlays":
            dest_dir = os.path.join(self.copy_dest, APP_NAME,
                                    "overlays", os.path.basename(src_dir))
        else:
            dest_dir = os.path.join(self.copy_dest, APP_NAME,
                                    os.path.basename(src_dir))
        return dest_dir

    # -------------------------------------------------------------------------
    def display_copy_summary(self, num_copied):
        """Method to display a message dialog with a count of how many runs
           were copied
        """
        msg_str = ("Copied:\n"
                   "   {} overlays\n"
                   "   {} runs\n"
                   "to {}\n"
                   .format(num_copied["overlays"],
                           num_copied["runs"],
                           os.path.join(self.copy_dest, APP_NAME)))
        tkmsg_showinfo(self.master, message=msg_str)

    # -------------------------------------------------------------------------
    def change_title(self, event=None):
        """Method to change the title of the selected run or of the
           current overlay
        """
        # pylint: disable=unused-argument
        # pylint: disable=too-many-branches
        if self.master.props.overlay_mode:
            prompt_title_str = "Change overlay title"
            prompt_str = "Enter new overlay title"
            init_val = ("IV Swinger Plot for {} Runs"
                        .format(len(self.overlaid_runs)))
        else:
            prompt_title_str = "Change run title"
            prompt_str = "Enter new run title"
            selected_overlays = self.get_selected_overlays()
            # Display error dialog and return if any overlays are selected
            if selected_overlays:
                tkmsg_showerror(self.master,
                                message=("ERROR: cannot change title on "
                                         "completed overlays"))
                return
            sel_runs = self.get_selected_runs(include_whole_days=False)
            if len(sel_runs) == 1:
                dts = IV_Swinger2.extract_date_time_str(sel_runs[0])
                date_time = date_at_time_from_dts(dts)
                if self.master.ivs2.plot_title is None:
                    init_val = "IV Swinger Plot for {}".format(date_time)
                else:
                    init_val = self.master.ivs2.plot_title
            elif len(sel_runs) > 1:
                err_str = ("ERROR: Title can only be changed on one run "
                           "at a time")
                tkmsg_showerror(self.master, message=err_str)
                return
            else:
                err_str = ("ERROR: No run selected")
                tkmsg_showerror(self.master, message=err_str)
                return
        new_title = tksd_askstring(self.master,
                                   title=prompt_title_str,
                                   prompt=prompt_str,
                                   initialvalue=init_val)
        if new_title:
            try:
                str(new_title)
            except UnicodeEncodeError:
                err_str = ("ERROR: Title must be ASCII")
                tkmsg_showerror(self.master, message=err_str)
                return
            if self.master.props.overlay_mode:
                self.overlay_title = new_title
                self.plot_overlay_and_display()
            else:
                time_of_day = self.tree.item(dts)["text"][:8]
                if new_title == "None":
                    new_title = None
                    text = time_of_day
                    self.tree.item(dts, text=text)
                else:
                    text = "{}   {}".format(time_of_day, new_title)
                    self.tree.item(dts, text=text)
                self.master.ivs2.plot_title = new_title
                self.master.props.overlay_names[dts] = new_title
                self.master.redisplay_img(reprocess_adc=False)

    # -------------------------------------------------------------------------
    def view_pdf(self, event=None):
        """Method to view the PDF when the View PDF button
           is pressed.
        """
        # pylint: disable=unused-argument

        # If there is a PDF, it has the same name as the image being
        # displayed in the image pane, but with a .pdf suffix
        # replacing the .gif suffix.
        img = self.master.img_file
        if img is not None and os.path.exists(img):
            (basename, _) = os.path.splitext(img)
            pdf = "{}.pdf".format(basename)
            if self.master.props.overlay_mode:
                # In overlay mode, the PDF is only generated when the Finished
                # button is pressed, so we have to generate it "on demand" when
                # the View PDF button is pressed.
                self.plot_graphs_to_pdf()
            if os.path.exists(pdf):
                IV_Swinger2.sys_view_file(pdf)
                return
        err_str = ("ERROR: No PDF to display")
        tkmsg_showerror(self.master, message=err_str)

    # -------------------------------------------------------------------------
    def plot_graphs_to_pdf(self):
        """Method that is a wrapper around the IV_Swinger2_plotter method of
           the same name. Adds option for user to retry if the file is
           open in a viewer (Windows issue).
        """
        self.master.retry_if_pdf_permission_denied(self.ivp.plot_graphs_to_pdf,
                                                   self.ivp.ivsp_ivse,
                                                   self.ivp.csv_proc)

    # -------------------------------------------------------------------------
    def update_selected(self, event=None):
        """Method to update the selected runs when the Update button
           is pressed.
        """
        # pylint: disable=unused-argument

        # Display error dialog and return if any overlays are selected
        selected_overlays = self.get_selected_overlays()
        if selected_overlays:
            tkmsg_showerror(self.master,
                            message="ERROR: overlays cannot be updated")
            return

        # Display error dialog and return if in overlay mode
        if self.master.props.overlay_mode:
            err_msg = "ERROR: cannot perform an update in overlay mode"
            tkmsg_showerror(self.master, message=err_msg)
            return

        # Get the selected run(s) from the Treeview (sorted from
        # oldest to newest). Display error dialog and return if no
        # runs are selected
        selected_runs = sorted(self.get_selected_runs())
        if not selected_runs:
            tkmsg_showerror(self.master,
                            message="ERROR: no runs are selected")
            return

        # Loop through runs, regenerating/redisplaying
        for run_dir in selected_runs:
            selection = os.path.basename(run_dir)

            # Get names of CSV files
            (csv_data_point_file,
             adc_csv_file, _) = self.get_csv_and_gif_names(run_dir, selection)
            if csv_data_point_file is None and adc_csv_file is None:
                continue

            # Prepare IVS2 object for regeneration of plot with modified
            # options
            self.prep_ivs2_for_redisplay(run_dir, adc_csv_file)

            # Set x_pixels to current value
            self.master.ivs2.x_pixels = self.master.get_curr_x_pixels()

            # Restore the saved config, then overwrite the Plotting
            # section with current values. This preserves the
            # calibration values, Arduino preferences, title, etc. since
            # none of those should change on a batch update. There is a
            # use case for using a batch update for calibration changes,
            # but that is outweighed by the danger of unintentionally
            # losing the calibration values at the time of the run. This
            # is particularly true for the battery bias calibration.
            cfg_file = os.path.join(run_dir, "{}.cfg".format(APP_NAME))
            if os.path.exists(cfg_file):
                self.master.config.cfg_filename = cfg_file
                self.master.config.merge_old_with_current_plotting(cfg_file)

            # If Lock checkbutton is unchecked, unlock axes so scaling
            # is automatic - otherwise, all updates will use the
            # current lock values
            if self.master.axes_locked.get() == "Unlock":
                self.master.props.redisplay_after_axes_unlock = False
                self.master.unlock_axes()
                self.master.props.redisplay_after_axes_unlock = True
            else:
                self.master.ivs2.plot_max_x = float(self.master.v_range.get())
                self.master.ivs2.plot_max_y = float(self.master.i_range.get())

            # Redisplay the image with the current options. This
            # regenerates the image files, and while not necessary to
            # display the image, it serves the function of a progress
            # indicator.
            self.master.img_pane.splash_img_showing = False
            reprocess_adc = (adc_csv_file is not None and
                             os.path.exists(adc_csv_file))
            self.master.redisplay_img(reprocess_adc=reprocess_adc)
            self.update()

        # Display done message if multiple runs selected
        if len(selected_runs) > 1:
            tkmsg_showinfo(self.master,
                           message="Batch update complete")

    # -------------------------------------------------------------------------
    def overlay_runs(self, event=None):
        """Method to overlay the selected runs
        """
        # pylint: disable=unused-argument

        # Get the selected run(s) from the Treeview
        # Sort in oldest-to-newest order
        self.overlaid_runs = self.get_selected_runs(include_whole_days=False)
        self.sort_overlaid_runs()

        # Check for too many selected
        max_overlays = len(IV_Swinger2.PLOT_COLORS)
        if len(self.overlaid_runs) > max_overlays:
            err_str = ("ERROR: Maximum of {} overlays supported ({} requested)"
                       .format(max_overlays, len(self.overlaid_runs)))
            tkmsg_showerror(self.master, message=err_str)
            return RC_FAILURE

        # Check for none selected
        if not self.master.props.overlay_mode and not self.overlaid_runs:
            info_str = ("Select at least one run to begin an overlay")
            tkmsg_showerror(self.master, message=info_str)
            return RC_FAILURE

        # Enter overlay mode (if not already in it)
        if not self.master.props.overlay_mode:
            self.add_overlay_widgets()
            self.master.props.overlay_mode = True
            self.make_overlay_dir()

        # Populate the overlay treeview
        self.populate_overlay_treeview(self.overlaid_runs)

        # If anything is selected, create the overlay and display the
        # result
        if self.overlaid_runs:
            rc = self.get_selected_csv_files(self.overlaid_runs)
            if rc == RC_SUCCESS:
                self.plot_overlay_and_display()
                self.add_new_overlay_to_tree()

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def sort_overlaid_runs(self, chron=False):
        """Method to sort the runs selected to be overlaid. Initially runs are
           sorted in oldest-to-newest order. If the chron flag is set,
           the sorting is chronological, reversing order each
           time. Otherwise, any ordering that has been applied by the
           user in the overlay treeview is preserved.  Any additional
           runs are added to the end of the list in oldest-to-newest
           order.
        """
        if not self.master.props.overlay_mode:
            # First time: oldest-to-newest
            self.overlaid_runs.sort(reverse=False)
            self.chron_dir = "forward"
        elif chron:
            if self.chron_dir == "forward":
                self.overlaid_runs.sort(reverse=True)
                self.chron_dir = "reverse"
            else:
                self.overlaid_runs.sort(reverse=False)
                self.chron_dir = "forward"
        else:
            # Revisions
            prev_runs = self.overlay_widget_treeview.get_children()  # dts only
            common_runs = []
            added_runs = []

            # Find runs that are in both the previous set (in the
            # overlay treeview) and in the current selection and put
            # them in a list in the same order they appear in the
            # treeview list (which may have been reordered by the
            # user).
            for prev_run_dts in prev_runs:
                for run in self.overlaid_runs:
                    run_dts = IV_Swinger2.extract_date_time_str(run)
                    if run_dts == prev_run_dts:
                        common_runs.append(run)
                        break

            # Find additional runs in the current selection and put
            # them in a separate list
            for run in self.overlaid_runs:
                if run not in common_runs:
                    added_runs.append(run)

            # Sort the additional runs oldest-to-newest
            added_runs.sort()

            # Concatenate the two lists and overwrite the list of runs
            # to be overlaid
            self.overlaid_runs = common_runs + added_runs

    # -------------------------------------------------------------------------
    def add_new_overlay_to_tree(self):
        """Method to add a just-created overlay to the Treeview
        """
        overlay_dir = self.master.props.overlay_dir
        overlay = IV_Swinger2.extract_date_time_str(overlay_dir)
        self.overlay_iid = "overlay_{}".format(overlay)
        parent = "overlays"

        # If the iid already exists in the tree, nothing to do
        if self.tree.exists(self.overlay_iid):
            return

        # Add overlays parent to Treeview if it doesn't already exist
        if not self.tree.exists(parent):
            self.tree.insert("", 0, parent, text="Overlays")

        # Translate to human readable date and time
        xlated = IV_Swinger2.xlate_date_time_str(overlay)
        (xlated_date, xlated_time) = xlated

        # Add to tree at the beginning of the parent (since order is
        # newest first)
        text = "Created on {} at {}".format(xlated_date, xlated_time)
        self.tree.insert(parent, 0, self.overlay_iid, text=text)

    # -------------------------------------------------------------------------
    def add_overlay_widgets(self):
        """Method to add the overlay mode widgets to the dialog
        """
        self.overlay_widget_box = ttk.Frame(self.body, borderwidth=5,
                                            relief="ridge")
        self.overlay_widget_label = ttk.Label(master=self.overlay_widget_box,
                                              text="Overlay Runs:")
        self.overlay_widget_cb_box = ttk.Frame(self.overlay_widget_box)
        self.overlay_widget_buttonbox = ttk.Frame(self.overlay_widget_box)
        self.overlay_help_button = ttk.Button(self.overlay_widget_buttonbox,
                                              text="Help",
                                              width=5,
                                              command=self.overlay_help)
        self.overlay_cancel_button = ttk.Button(self.overlay_widget_buttonbox,
                                                text="Cancel",
                                                width=7,
                                                command=self.overlay_cancel)
        tt_text = "Exit overlay mode without saving"
        Tooltip(self.overlay_cancel_button, text=tt_text, **TOP_TT_KWARGS)
        overlay_button_pad = ttk.Label(self.overlay_widget_buttonbox,
                                       text="    ")
        self.overlay_finish_button = ttk.Button(self.overlay_widget_buttonbox,
                                                text="Finished",
                                                width=9,
                                                command=self.overlay_finished)
        tt_text = ("Save overlay and generate PDF. NOTE: Overlays cannot be "
                   "modified once they have been saved.")
        Tooltip(self.overlay_finish_button, text=tt_text, **TOP_TT_KWARGS)

        # Create the Treeview widget that lists the overlay members and
        # allows the user to label and reorder them
        self.create_overlay_treeview()

        # Add the label control checkbuttons
        self.add_overlay_label_cbs()

        # Increase the minimum height of the wizard window to
        # accomodate the overlay widget box
        self.change_min_height(WIZARD_MIN_HEIGHT_PIXELS + 230)

        # Layout
        self.overlay_widget_box.grid(column=0, row=1, sticky=(N, S, E, W))
        self.overlay_widget_label.grid(column=0, row=0, sticky=(W))
        self.overlay_widget_treeview.grid(column=0, row=1, sticky=(W))
        self.overlay_widget_cb_box.grid(column=0, row=2, sticky=(W))
        self.overlay_widget_buttonbox.grid(column=0, row=3, sticky=(W))
        self.overlay_help_button.pack(side=LEFT)
        self.overlay_cancel_button.pack(side=LEFT)
        overlay_button_pad.pack(side=LEFT)
        self.overlay_finish_button.pack(side=LEFT)

    # -------------------------------------------------------------------------
    def add_overlay_label_cbs(self):
        """Method to add the overlay label control checkbuttons
        """
        master = self.overlay_widget_cb_box
        onvalue = "Enabled"
        offvalue = "Disabled"
        command = self.overlay_label_changed_actions

        # Add checkbutton to choose whether to label all Isc points
        variable = self.master.label_all_iscs
        text = "Label all Isc points"
        self.label_all_iscs_cb = ttk.Checkbutton(master=master,
                                                 text=text,
                                                 command=command,
                                                 variable=variable,
                                                 onvalue=onvalue,
                                                 offvalue=offvalue)
        tt_text = ("Default is to label the Isc point of the first curve "
                   "only. Check to label the Isc points of all curves.")
        Tooltip(self.label_all_iscs_cb, text=tt_text, **TOP_TT_KWARGS)

        # Add checkbutton to choose whether to label all MPPs
        variable = self.master.label_all_mpps
        text = "Label all MPPs"
        self.label_all_mpps_cb = ttk.Checkbutton(master=master,
                                                 text=text,
                                                 command=command,
                                                 variable=variable,
                                                 onvalue=onvalue,
                                                 offvalue=offvalue)
        tt_text = ("Default is to label the MPP of the first curve "
                   "only. Check to label the MPPs of all curves.")
        Tooltip(self.label_all_mpps_cb, text=tt_text, **TOP_TT_KWARGS)

        # Add checkbutton to choose whether to display watts only on MPPs
        variable = self.master.mpp_watts_only
        text = "Watts-only MPPs"
        self.mpp_watts_only_cb = ttk.Checkbutton(master=master,
                                                 text=text,
                                                 command=command,
                                                 variable=variable,
                                                 onvalue=onvalue,
                                                 offvalue=offvalue)
        tt_text = ("Default is for MPP label to include V*I values. "
                   "Check to display watts only.")
        Tooltip(self.mpp_watts_only_cb, text=tt_text, **TOP_TT_KWARGS)

        # Add checkbutton to choose whether to label all Voc points
        variable = self.master.label_all_vocs
        text = "Label all Voc points"
        self.label_all_vocs_cb = ttk.Checkbutton(master=master,
                                                 text=text,
                                                 command=command,
                                                 variable=variable,
                                                 onvalue=onvalue,
                                                 offvalue=offvalue)
        tt_text = ("Default is to label the Voc point of the first curve "
                   "only. Check to label the Voc points of all curves.")
        Tooltip(self.label_all_vocs_cb, text=tt_text, **TOP_TT_KWARGS)
        # Layout
        self.label_all_iscs_cb.grid(column=0, row=0, sticky=(W))
        self.label_all_mpps_cb.grid(column=0, row=1, sticky=(W))
        self.mpp_watts_only_cb.grid(column=1, row=1, sticky=(W))
        self.label_all_vocs_cb.grid(column=0, row=2, sticky=(W))

    # -------------------------------------------------------------------------
    def overlay_label_changed_actions(self, event=None):
        """Method for changes to the overlay label checkbuttons
        """
        # pylint: disable=unused-argument
        self.plot_overlay_and_display()

    # -------------------------------------------------------------------------
    def create_overlay_treeview(self):
        """Method to create the overlay Treeview widget
        """
        self.overlay_widget_treeview = ttk.Treeview(self.overlay_widget_box,
                                                    columns=("label"),
                                                    displaycolumns=("label"),
                                                    selectmode="browse")
        # Set treeview height to accomodate the maximum number of
        # overlays
        max_overlays = len(IV_Swinger2.PLOT_COLORS)
        self.overlay_widget_treeview.configure(height=max_overlays)

        # Set each column's width to half the wizard's main treeview
        # width so the two treeviews are the same width. Add column
        # headings.
        col0_text = "Date/Time"
        col1_text = "Name (2-click to change)"
        self.overlay_widget_treeview.column("#0", width=WIZARD_TREE_WIDTH/2)
        self.overlay_widget_treeview.heading("#0", text=col0_text,
                                             command=self.chron_sort_overlays)
        self.overlay_widget_treeview.column("#1", width=WIZARD_TREE_WIDTH/2)
        self.overlay_widget_treeview.heading("#1", text=col1_text,
                                             command=self.overlay_tv_col1_help)

        # Register callbacks for drag-and-drop reordering
        self.overlay_widget_treeview.bind("<ButtonPress-1>",
                                          grab_overlay_curve)

        self.overlay_widget_treeview.bind("<B1-Motion>",
                                          self.move_overlay_curve)

        self.overlay_widget_treeview.bind("<ButtonRelease-1>",
                                          self.update_overlay_order)

        # Tooltip
        tt_text = ("Double-click to rename. Drag and drop to reorder. "
                   "Click on Date/Time heading to sort chronologically. "
                   "Add or remove curves using Control-click in the selection "
                   "tree view pane above.")
        Tooltip(self.overlay_widget_treeview, text=tt_text,
                **TOP_TT_KWARGS)

        # Register callback for changing the name
        self.overlay_widget_treeview.bind("<Double-ButtonPress-1>",
                                          self.change_overlay_curve_name)

    # -------------------------------------------------------------------------
    def chron_sort_overlays(self, event=None):
        """Method to sort the overlays in the treeview chronologically
           when the heading is clicked. Order reverses each time it is
           called.
        """
        # pylint: disable=unused-argument
        self.sort_overlaid_runs(chron=True)
        self.populate_overlay_treeview(self.overlaid_runs)
        self.reorder_selected_csv_files()
        self.plot_overlay_and_display()

    # -------------------------------------------------------------------------
    def overlay_tv_col1_help(self, event=None):
        """Method to display a help dialog if the column 1 heading (Name) is
           clicked.
        """
        # pylint: disable=unused-argument
        help_str = ("Double-click items below to rename.\n"
                    "Drag items to change order.")
        tkmsg_showinfo(self.master, message=help_str)

    # -------------------------------------------------------------------------
    def populate_overlay_treeview(self, run_dirs):
        """Method to add items to the overlay treeview widget
        """
        # Remove all current items
        curr_items = self.overlay_widget_treeview.get_children()
        self.overlay_widget_treeview.delete(*curr_items)
        # Add item for each selected run
        for run_dir in run_dirs:
            dts = os.path.basename(run_dir)
            date_time = date_at_time_from_dts(dts)
            if dts in self.master.props.overlay_names:
                name = self.master.props.overlay_names[dts]
            else:
                name = date_time
            self.overlay_widget_treeview.insert("", "end", dts,
                                                text=date_time,
                                                values=[name])
        self.overlays_reordered = False

    # -------------------------------------------------------------------------
    def move_overlay_curve(self, event=None):
        """Method to drag the selected curve to a new position in the
           list
        """
        tv = event.widget
        moveto = tv.index(tv.identify_row(event.y))
        try:
            tv.move(tv.selection()[0], "", moveto)
            self.overlays_reordered = True
        except IndexError:
            # Spurious error - ignore
            pass

    # -------------------------------------------------------------------------
    def update_overlay_order(self, event=None):
        """Method to update the order of the overlay curves after a
           drag-and-drop
        """
        # pylint: disable=unused-argument
        if self.overlays_reordered:
            self.reorder_selected_csv_files()
            self.plot_overlay_and_display()
        self.overlays_reordered = False

    # -------------------------------------------------------------------------
    def change_overlay_curve_name(self, event=None):
        """Method to prompt the user to enter a new name for an
           overlay curve
        """
        tv = event.widget
        dts = tv.identify_row(event.y)
        if IV_Swinger2.is_date_time_str(dts):
            date_time = date_at_time_from_dts(dts)
        else:
            # Double-click was somewhere else
            return

        # Open dialog to add or change name
        prompt_str = "Enter name for {} curve".format(date_time)
        if dts in self.master.props.overlay_names:
            init_val = self.master.props.overlay_names[dts]
        else:
            init_val = date_time
        new_name = tksd_askstring(self.master,
                                  title="Change name",
                                  prompt=prompt_str,
                                  initialvalue=init_val)
        if new_name:
            self.master.props.overlay_names[dts] = new_name
            self.populate_overlay_treeview(self.overlaid_runs)
            self.plot_overlay_and_display()

    # -------------------------------------------------------------------------
    def remove_overlay_widgets(self):
        """Method to remove the overlay mode widgets from the dialog
        """
        # Destroying the parent box recursively destroys all widgets
        self.overlay_widget_box.destroy()

        # Decrease the minimum height of the wizard window back to its
        # normal value
        self.change_min_height(WIZARD_MIN_HEIGHT_PIXELS)

    # -------------------------------------------------------------------------
    def overlay_help(self, event=None):
        """Method to display overlay help dialog when the Help button
           is pressed.
        """
        # pylint: disable=unused-argument
        OverlayHelpDialog(self.master)

    # -------------------------------------------------------------------------
    def overlay_cancel(self, event=None):
        """Method to perform actions when Cancel button is pressed.
           Overlay mode is exited and the widgets are removed. The runs
           are left selected.
        """
        # pylint: disable=unused-argument

        # Exit overlay mode and remove widgets
        self.master.props.overlay_mode = False
        self.overlay_title = None
        self.remove_overlay_widgets()

        # Remove overlay from tree
        try:
            self.tree.delete(self.overlay_iid)
        except tk.TclError:
            pass

        # Remove overlay directory
        if self.master.props.overlay_dir == os.getcwd():
            os.chdir("..")
        shutil.rmtree(self.master.props.overlay_dir)

    # -------------------------------------------------------------------------
    def overlay_finished(self, event=None):
        """Method to perform actions when Finished button is pressed.
           PDF is generated. Overlay mode is exited and the widgets are
           removed. The runs are de-selected and the overlay is selected
           and made visible, with the assumption that the user's next
           action will be to copy the overlay files.
        """
        # pylint: disable=unused-argument

        # Generate the PDF
        self.plot_graphs_to_pdf()

        # Exit overlay mode and remove widgets
        self.master.props.overlay_mode = False
        self.overlay_title = None
        self.remove_overlay_widgets()

        # Remove overlay if incomplete, and return
        if self.rm_overlay_if_unfinished():
            return

        # De-select the runs
        selections = self.tree.selection()
        self.tree.selection_remove(selections)

        # Make the "overlays" group visible and the new overlay visible
        # and selected
        if self.overlay_iid is not None:
            self.tree.see("overlays")
            self.tree.see(self.overlay_iid)
            self.tree.selection_add(self.overlay_iid)

    # -------------------------------------------------------------------------
    def rm_overlay_if_unfinished(self):
        """Method to remove the current overlay directory if it is
           "unfinished", i.e. if it doesn't contain a PDF (or doesn't
           exist at all). Returns True if it was removed (or didn't
           exist) and False otherwise.
        """
        if self.master.props.overlay_dir is not None:
            if not os.path.exists(self.master.props.overlay_dir):
                return True
            # Remove directory if it doesn't contain overlaid PDF
            dts = os.path.basename(self.master.props.overlay_dir)
            overlay_pdf = "overlaid_{}.pdf".format(dts)
            if overlay_pdf not in os.listdir(self.master.props.overlay_dir):
                if self.master.props.overlay_dir == os.getcwd():
                    os.chdir("..")
                shutil.rmtree(self.master.props.overlay_dir)
                return True
            # Clean up the directory
            self.master.ivs2.clean_up_files(self.master.props.overlay_dir,
                                            loop_mode=False)
        return False

    # -------------------------------------------------------------------------
    def get_selected_csv_files(self, selected_runs):
        """Method to get the full paths of the CSV files for the selected runs
        """
        self.selected_csv_files = []
        for csv_dir in selected_runs:
            dts = IV_Swinger2.extract_date_time_str(csv_dir)
            csv_files_found = 0
            for filename in os.listdir(csv_dir):
                if (filename.endswith("{}.csv".format(dts)) and
                        "adc_pairs" not in filename):
                    csv_file_full_path = os.path.join(csv_dir, filename)
                    self.selected_csv_files.append(csv_file_full_path)
                    csv_files_found += 1
            if not csv_files_found:
                err_str = ("ERROR: no data point CSV file found in {}"
                           .format(csv_dir))
                tkmsg_showerror(self.master, message=err_str)
                return RC_FAILURE
            elif csv_files_found > 1:
                err_str = ("ERROR: multiple data point CSV files found in {}"
                           .format(csv_dir))
                tkmsg_showerror(self.master, message=err_str)
                return RC_FAILURE

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def reorder_selected_csv_files(self):
        """Method to change the order of the selected CSV files to match the
           order in the overlay treeview widget
        """
        new_csv_list = []
        curves = self.overlay_widget_treeview.get_children()
        for dts in curves:
            for csv in self.selected_csv_files:
                csv_dts = IV_Swinger2.extract_date_time_str(csv)
                if csv_dts == dts:
                    new_csv_list.append(csv)
                    break
        self.selected_csv_files = list(new_csv_list)

    # -------------------------------------------------------------------------
    def make_overlay_dir(self):
        """Method to create the directory for an overlay
        """
        # Generate the date/time string from the current time
        date_time_str = IV_Swinger2.get_date_time_str()

        # Create overlay directory
        self.master.props.overlay_dir = os.path.join(self.results_dir,
                                                     "overlays",
                                                     date_time_str)
        if not os.path.exists(self.master.props.overlay_dir):
            os.makedirs(self.master.props.overlay_dir)

    # -------------------------------------------------------------------------
    def plot_overlay(self):
        """Method to generate the overlay plot
        """
        self.ivp = IV_Swinger2.IV_Swinger2_plotter()
        self.get_overlay_curve_names()
        self.ivp.title = self.overlay_title
        self.ivp.logger = self.master.ivs2.logger
        self.ivp.csv_files = self.selected_csv_files
        self.ivp.plot_dir = self.master.props.overlay_dir
        self.ivp.x_pixels = self.master.ivs2.x_pixels
        self.ivp.generate_pdf = False
        self.ivp.fancy_labels = self.master.ivs2.fancy_labels
        self.ivp.label_all_iscs = (self.master.label_all_iscs.get() ==
                                   "Enabled")
        self.ivp.label_all_mpps = (self.master.label_all_mpps.get() ==
                                   "Enabled")
        self.ivp.mpp_watts_only = (self.master.mpp_watts_only.get() ==
                                   "Enabled")
        self.ivp.label_all_vocs = (self.master.label_all_vocs.get() ==
                                   "Enabled")
        self.ivp.linear = self.master.ivs2.linear
        self.ivp.overlay = True
        self.ivp.plot_power = self.master.ivs2.plot_power
        self.ivp.font_scale = self.master.ivs2.font_scale
        self.ivp.line_scale = self.master.ivs2.line_scale
        self.ivp.point_scale = self.master.ivs2.point_scale
        if self.master.axes_locked.get() == "Lock":
            self.ivp.max_x = self.master.ivs2.plot_max_x
            self.ivp.max_y = self.master.ivs2.plot_max_y
        self.ivp.run()
        self.overlay_img = self.ivp.current_img

    # -------------------------------------------------------------------------
    def plot_overlay_and_display(self):
        """Method to generate the overlay plot and display it
        """
        self.plot_overlay()
        self.master.display_img(self.overlay_img)

    # -------------------------------------------------------------------------
    def get_overlay_curve_names(self):
        """Method to generate the list of overlay curve names
        """
        self.ivp.curve_names = []
        curves = self.overlay_widget_treeview.get_children()
        for dts in curves:
            if dts in self.master.props.overlay_names:
                # Name is user-specified
                name = self.master.props.overlay_names[dts]
                self.ivp.curve_names.append(name)
            else:
                # Default name: date@time
                date_time = date_at_time_from_dts(dts)
                self.ivp.curve_names.append(date_time)
        if not self.ivp.curve_names:
            self.ivp.curve_names = None


# Menu bar class
#
class MenuBar(tk.Menu):
    """Class that implements the menu bar"""
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods

    # Initializer
    def __init__(self, master=None):
        tk.Menu.__init__(self, master=master)
        self.master = master
        self.menubar = tk.Menu(self.master)
        self.selected_port = tk.StringVar()
        self.create_about_menu()
        self.create_file_menu()
        self.create_usb_port_menu()
        self.create_calibrate_menu()
        self.create_window_menu()
        self.create_help_menu()
        self.master.root["menu"] = self.menubar

    # -------------------------------------------------------------------------
    def create_about_menu(self):
        """Method to create the "About" menu"""
        if self.master.win_sys == "aqua":  # Mac
            self.about_menu = tk.Menu(self.menubar, name="apple")
            self.menubar.add_cascade(menu=self.about_menu)
            self.master.root.createcommand("tk::mac::ShowPreferences",
                                           self.master.show_preferences)
        else:  # Windows / Linux
            self.about_menu = tk.Menu(self.menubar)
            self.menubar.add_cascade(menu=self.about_menu, label="About")
        self.about_menu.add_command(label="About IV Swinger 2",
                                    command=self.show_about_dialog)
        self.about_menu.add_separator()

    # -------------------------------------------------------------------------
    def create_file_menu(self):
        """Method to create the "File" menu"""
        self.file_menu = tk.Menu(self.menubar,
                                 postcommand=self.update_file_menu)
        self.menubar.add_cascade(menu=self.file_menu, label="File")
        self.file_menu.add_command(label="View Log File",
                                   command=self.view_log_file)
        self.file_menu.add_command(label="View Config File",
                                   command=self.view_config_file)
        self.file_menu.add_command(label="View Run Info File",
                                   command=self.view_run_info_file)
        self.file_menu.add_command(label="Open Run Folder",
                                   command=self.open_run_folder)

    # -------------------------------------------------------------------------
    def update_file_menu(self):
        """Method to update the "File" menu to enable/disable entries"""
        kwargs = {"state": "normal"}
        if (self.master.ivs2.hdd_output_dir is None or
                not os.path.exists(self.master.ivs2.hdd_output_dir)):
            kwargs = {"state": "disabled"}
        self.file_menu.entryconfig("View Run Info File", **kwargs)
        self.file_menu.entryconfig("Open Run Folder", **kwargs)

    # -------------------------------------------------------------------------
    def create_usb_port_menu(self):
        """Method to create the "USB Port" menu"""
        self.usb_port_menu = tk.Menu(self.menubar,
                                     postcommand=self.update_usb_port_menu)
        self.menubar.add_cascade(menu=self.usb_port_menu, label="USB Port")

    # -------------------------------------------------------------------------
    def update_usb_port_menu(self):
        """Method to update the "USB Port" menu to enable/disable entries"""
        # If already populated, clear it out
        index2 = self.usb_port_menu.index("end")
        if index2 is not None:
            self.usb_port_menu.delete(0, index2)
        # Populate
        self.selected_port.set(self.master.ivs2.usb_port)
        for serial_port in self.master.ivs2.serial_ports:
            device = serial_port.device
            label_part2 = u''
            if serial_port.manufacturer is not None:
                label_part2 = u' ' + serial_port.manufacturer
            elif serial_port.description is not None:
                label_part2 = u' ' + serial_port.description
            label = device + label_part2
            self.usb_port_menu.add_radiobutton(label=label,
                                               variable=self.selected_port,
                                               value=device,
                                               command=self.select_serial)

    # -------------------------------------------------------------------------
    def create_calibrate_menu(self):
        """Method to create the "Calibrate" menu"""
        self.calibrate_menu = tk.Menu(self.menubar,
                                      postcommand=self.update_calibrate_menu)
        self.menubar.add_cascade(menu=self.calibrate_menu, label="Calibrate")
        self.calibrate_menu.add_command(label="Vref (+5V)",
                                        command=self.get_vref_cal_value)
        self.calibrate_menu.add_command(label="Voltage - basic",
                                        command=self.get_v_cal_value)
        self.calibrate_menu.add_command(label="Current - basic",
                                        command=self.get_i_cal_value)
        self.calibrate_menu.add_command(label="Voltage - advanced",
                                        command=self.get_v_cal_value_adv)
        self.calibrate_menu.add_command(label="Current - advanced",
                                        command=self.get_i_cal_value_adv)
        self.calibrate_menu.add_command(label="Resistors",
                                        command=self.get_resistor_values)
        self.calibrate_menu.add_command(label="Pyranometer",
                                        command=self.get_pyrano_cal_value)
        self.calibrate_menu.add_command(label="Bias Battery",
                                        command=self.get_battery_bias)
        self.calibrate_menu.add_command(label="Invalidate Arduino EEPROM",
                                        command=self.invalidate_arduino_eeprom)
        self.calibrate_menu.add_command(label="Calibration Help",
                                        command=self.show_calibration_help)

    # -------------------------------------------------------------------------
    def update_calibrate_menu(self):
        """Method to update the "Calibrate" menu to enable/disable entries"""
        # Vref, Current/Voltage - advanced, Resistors, Bias battery, Invalidate
        # EEPROM
        #
        #   Enabled only if:
        #     Wizard not active
        #     Arduino is ready
        if (self.master.results_wiz is None and
                self.master.ivs2.arduino_ready):
            kwargs = {"state": "normal"}
        else:
            kwargs = {"state": "disabled"}
        self.calibrate_menu.entryconfig("Vref (+5V)", **kwargs)
        self.calibrate_menu.entryconfig("Voltage - advanced", **kwargs)
        self.calibrate_menu.entryconfig("Current - advanced", **kwargs)
        self.calibrate_menu.entryconfig("Resistors", **kwargs)
        self.calibrate_menu.entryconfig("Bias Battery", **kwargs)
        self.calibrate_menu.entryconfig("Invalidate Arduino EEPROM", **kwargs)

        # Voltage/Current - basic
        #
        #   Enabled only if:
        #     Wizard not active
        #     Arduino is ready
        #     Current run is displayed
        #     Data points are valid
        if (self.master.results_wiz is None and
                self.master.ivs2.arduino_ready and
                self.master.props.current_run_displayed and
                len(self.master.ivs2.data_points) > 1):
            kwargs = {"state": "normal"}
        else:
            kwargs = {"state": "disabled"}
        self.calibrate_menu.entryconfig("Voltage - basic", **kwargs)
        self.calibrate_menu.entryconfig("Current - basic", **kwargs)

        # Pyranometer
        #
        #   Enabled only if:
        #     Wizard not active
        #     Arduino is ready
        #     Current run is displayed
        #     Irradiance value is valid
        if (self.master.results_wiz is None and
                self.master.ivs2.arduino_ready and
                self.master.props.current_run_displayed and
                self.master.ivs2.irradiance is not None):
            kwargs = {"state": "normal"}
        else:
            kwargs = {"state": "disabled"}
        self.calibrate_menu.entryconfig("Pyranometer", **kwargs)

    # -------------------------------------------------------------------------
    def create_window_menu(self):
        """Method to create the "Window" menu"""
        if self.master.win_sys == "aqua":  # Mac
            self.window_menu = tk.Menu(self.menubar, name="window")
            self.menubar.add_cascade(menu=self.window_menu, label="Window")
        else:
            pass

    # -------------------------------------------------------------------------
    def create_help_menu(self):
        """Method to create the "Help" menu"""
        if self.master.win_sys == "aqua":  # Mac
            self.help_menu = tk.Menu(self.menubar, name="help")
            self.menubar.add_cascade(menu=self.help_menu, label="Help")
            self.master.root.createcommand("tk::mac::ShowHelp",
                                           self.show_help)
        else:  # Windows / Linux
            self.help_menu = tk.Menu(self.menubar)
            self.menubar.add_cascade(menu=self.help_menu, label="Help")
            self.help_menu.add_command(label="IV Swinger 2 Help",
                                       command=self.show_help)

    # -------------------------------------------------------------------------
    def show_about_dialog(self):
        """Method to show the "About" dialog"""
        version_str = "Version: {}\n\n".format(self.master.version)
        about_str = """
IV Swinger and IV Swinger 2 are open
source hardware and software projects

Permission to use the hardware designs
is granted under the terms of the TAPR
Open Hardware License Version 1.0 (May
25, 2007) - http://www.tapr.org/OHL

Permission to use the software is
granted under the terms of the GNU GPL
v3 as noted above.

Current versions of the licensing files,
documentation, hardware design files,
and software can be found at:

   https://github.com/csatt/IV_Swinger

Copyright (C) 2017-2019  Chris Satterlee
"""
        sketch_ver = self.master.ivs2.arduino_sketch_ver
        sketch_ver_str = ""
        if sketch_ver != "Unknown":
            sketch_ver_str = ("Arduino sketch version: {}\n\n"
                              .format(sketch_ver))
        tkmsg_showinfo(self.master,
                       message=version_str+sketch_ver_str+about_str)

    # -------------------------------------------------------------------------
    def view_log_file(self):
        """Method to view a log file. A tkFileDialog is opened for the user to
           select which log file to view. The default selection is
           chosen using the get_initial_log_file_name method. The
           selected file is then opened with the system file viewer.
        """
        (log_dir,
         log_file) = os.path.split(self.master.ivs2.logger.log_file_name)
        options = {}
        options["defaultextension"] = ".txt"
        (initial_dir,
         initial_file) = self.get_initial_log_file_name(log_dir, log_file)
        options["initialdir"] = initial_dir
        options["initialfile"] = initial_file
        options["parent"] = self.master
        options["title"] = "Choose log file"
        if self.master.win_sys == "aqua":  # Mac
            options["message"] = options["title"]
        log_file = tkFileDialog.askopenfilename(**options)
        self.master.mac_grayed_menu_workaround()
        if log_file:
            IV_Swinger2.sys_view_file(os.path.normpath(log_file))

    # -------------------------------------------------------------------------
    def get_initial_log_file_name(self, log_dir, current_log):
        """Method to choose the most likely log file as the default selection
           for the view_log_file method.  If the config file name has a
           date_time_str in its name, we're in the Results Wizard, and
           the relevant log file is the one that contains the info for
           the selected run.  That is the one that has a date_time_str
           that is older than or equal to the config file's, but the
           newest such log file. Otherwise, the current log file is the
           default.
        """
        cfg_filename = self.master.config.cfg_filename
        cfg_dts = IV_Swinger2.extract_date_time_str(cfg_filename)
        cfg_dir = os.path.dirname(cfg_filename)
        cfg_dir_logs = os.path.join(os.path.dirname(cfg_dir), "logs")
        if os.path.isdir(cfg_dir_logs):
            search_dir = cfg_dir_logs
        else:
            search_dir = log_dir
        if IV_Swinger2.is_date_time_str(cfg_dts):
            # Search list of log files, sorted newest to oldest
            for log_file in sorted(os.listdir(search_dir), reverse=True):
                if log_file.startswith("log_") and log_file.endswith(".txt"):
                    log_dts = IV_Swinger2.extract_date_time_str(log_file)
                    if IV_Swinger2.is_date_time_str(log_dts):
                        if log_dts <= cfg_dts:  # older than or equal to
                            return (search_dir, log_file)
        # Default is the current log file
        return (log_dir, current_log)

    # -------------------------------------------------------------------------
    def view_config_file(self):
        """Method to open the current config file using the system file
           viewer
        """
        IV_Swinger2.sys_view_file(self.master.config.cfg_filename)

    # -------------------------------------------------------------------------
    def view_run_info_file(self):
        """Method to open the current run info file using the system file
           viewer
        """
        self.master.ivs2.convert_sensor_to_run_info_file()
        self.master.ivs2.create_run_info_file()  # if it doesn't exist
        IV_Swinger2.sys_view_file(self.master.ivs2.run_info_filename)

    # -------------------------------------------------------------------------
    def open_run_folder(self):
        """Method to open the run directory using the system file manager
        """
        IV_Swinger2.sys_view_file(self.master.ivs2.hdd_output_dir)

    # -------------------------------------------------------------------------
    def select_serial(self):
        """Method to change the USB port to the one selected. The Arduino
           handshake is initiated using the new port. If that succeeds,
           the configuration is updated with the new port.
        """
        self.master.ivs2.usb_port = self.selected_port.get()
        self.master.ivs2.arduino_ready = False
        self.master.attempt_arduino_handshake()
        if self.master.ivs2.arduino_ready:
            self.master.config.cfg_set("USB", "port",
                                       self.master.ivs2.usb_port)
            self.master.save_config()

    # -------------------------------------------------------------------------
    def get_vref_cal_value(self):
        """Method to get the Vref calibration value from the user and apply it.
           This is now actually calibrating the bandgap voltage, which
           is used to measure Vref every time an IV curve is swung.
        """
        # First update the adc_vref property based on the current calibration
        # and measurement (if any). This is so the displayed voltage is the
        # currently measured value.
        if self.master.ivs2.read_bandgap() == RC_SUCCESS:
            self.master.ivs2.set_vref_from_bandgap()
        curr_vref = self.master.ivs2.adc_vref
        prompt_str = "Enter measured voltage of +5V reference:"
        new_vref = tksd_askfloat(self.master,
                                 title="+5V (Vref) Calibration",
                                 prompt=prompt_str,
                                 initialvalue=curr_vref)
        if new_vref:
            self.master.ivs2.adc_vref = new_vref
            self.master.config.cfg_set("Calibration", "vref", new_vref)
            # Redisplay the image with the new settings (saves config)
            self.master.redisplay_img(reprocess_adc=True)
            self.master.ivs2.calibrate_bandgap()
            self.update_values_in_eeprom()

    # -------------------------------------------------------------------------
    def get_v_cal_value(self):
        """Method to get the voltage calibration value from the user and apply
           it (basic calibration)
        """
        if self.master.ivs2.battery_bias and not self.master.ivs2.dyn_bias_cal:
            # If the battery bias mode is on, and we're NOT doing
            # dynamic bias battery calibration, we can't really do
            # anything that would work reliably.  It is likely that the
            # error is due to the bias battery curve being "stale".
            err_msg = """
ERROR: voltage calibration cannot
be performed using a curve that has
battery bias applied unless dynamic
bias battery calibration was enabled.
"""
            tkmsg_showerror(self.master, message=err_msg)
            return

        v_cal_b = self.master.ivs2.v_cal_b
        if not self.master.ivs2.battery_bias:
            if v_cal_b != 0.0:
                warn_msg = """
WARNING: An advanced voltage
calibration is active.
Performing a basic calibration
may degrade results.
"""
                tkmsg_showwarning(self.master, message=warn_msg)

        data_points = self.master.ivs2.data_points
        curr_voc = round(data_points[-1][IV_Swinger2.VOLTS_INDEX], 5)
        if curr_voc <= v_cal_b:
            err_msg = """
ERROR: Voc must be larger than
{} to perform voltage calibration.
""".format(v_cal_b)
            tkmsg_showerror(self.master, message=err_msg)
            return
        prompt_str = "Enter measured Voc value:"
        new_voc = tksd_askfloat(self.master,
                                title="Voltage Calibration - basic",
                                prompt=prompt_str,
                                initialvalue=curr_voc)
        if new_voc:
            if not self.master.ivs2.battery_bias:
                # Normal case: just scale v_cal proportionally
                adj_ratio = (new_voc - v_cal_b) / (curr_voc - v_cal_b)
                new_v_cal = self.master.ivs2.v_cal * adj_ratio
                self.master.ivs2.v_cal = new_v_cal
                self.master.config.cfg_set("Calibration", "voltage", new_v_cal)
                # Update value in EEPROM
                self.update_values_in_eeprom()
            elif self.master.ivs2.dyn_bias_cal:
                # If the battery bias mode is on, and we're doing
                # dynamic bias battery calibration, the error is due to
                # the Vref droop caused by the activation of the second
                # relay. So instead of updating the v_cal value, the
                # second_relay_cal value is updated.
                new_voc_uncal = new_voc / self.master.ivs2.v_cal
                batt_voc = self.master.ivs2.bias_batt_voc_volts
                curr_voc_with_batt = self.master.ivs2.pre_bias_voc_volts
                new_second_relay_cal = ((new_voc_uncal + batt_voc) /
                                        curr_voc_with_batt)
                self.master.ivs2.second_relay_cal = new_second_relay_cal
                self.master.config.cfg_set("Calibration", "second relay",
                                           new_second_relay_cal)

            # Redisplay the image with the new settings (saves config)
            self.master.redisplay_img(reprocess_adc=True)

    # -------------------------------------------------------------------------
    def get_i_cal_value(self):
        """Method to get the current calibration value from the user and apply
           it (basic calibration)
        """
        i_cal_b = self.master.ivs2.i_cal_b
        if i_cal_b != 0.0:
            warn_msg = """
WARNING: An advanced current
calibration is active.
Performing a basic calibration
may degrade results.
"""
            tkmsg_showwarning(self.master, message=warn_msg)
        data_points = self.master.ivs2.data_points
        curr_isc = round(data_points[0][IV_Swinger2.AMPS_INDEX], 5)
        if curr_isc <= i_cal_b:
            err_msg = """
ERROR: Isc must be larger than
{} to perform current calibration.
""".format(i_cal_b)
            tkmsg_showerror(self.master, message=err_msg)
            return
        prompt_str = "Enter measured Isc value:"
        new_isc = tksd_askfloat(self.master,
                                title="Current Calibration - basic",
                                prompt=prompt_str,
                                initialvalue=curr_isc)
        if new_isc:
            new_i_cal = (self.master.ivs2.i_cal *
                         (new_isc - i_cal_b) / (curr_isc - i_cal_b))
            self.master.ivs2.i_cal = new_i_cal
            self.master.config.cfg_set("Calibration", "current", new_i_cal)
            # Update value in EEPROM
            self.update_values_in_eeprom()
            # Redisplay the image with the new settings (saves config)
            self.master.redisplay_img(reprocess_adc=True)

    # -------------------------------------------------------------------------
    def get_v_cal_value_adv(self):
        """Method to get the voltage calibration values from the user and apply
           them (advanced calibration)
        """
        AdvVoltageCalDialog(self.master)

    # -------------------------------------------------------------------------
    def get_i_cal_value_adv(self):
        """Method to get the current calibration values from the user and apply
           them (advanced calibration)
        """
        AdvCurrentCalDialog(self.master)

    # -------------------------------------------------------------------------
    def get_pyrano_cal_value(self):
        """Method to get the pyranometer calibration value from the user and
           apply it
        """
        curr_irradiance = self.master.ivs2.irradiance
        prompt_str = "Enter measured W/m^2 value:"
        new_irradiance = tksd_askfloat(self.master,
                                       title="Pyranometer Calibration",
                                       prompt=prompt_str,
                                       initialvalue=curr_irradiance)
        if new_irradiance:
            pyrano_cal = self.master.ivs2.pyrano_cal
            pyrano_cal_a = self.master.ivs2.pyrano_cal_a
            mv = self.master.ivs2.scaled_photodiode_millivolts
            irrad_diff = new_irradiance - curr_irradiance
            # Keep pyrano_cal_a value. The following equation returns
            # the calibration value that results in the observed
            # irradiance.
            new_pyrano_cal = ((pyrano_cal_a * mv * irrad_diff +
                               new_irradiance * pyrano_cal) /
                              curr_irradiance)
            self.master.ivs2.pyrano_cal = new_pyrano_cal
            self.master.config.cfg_set("Calibration", "pyranometer",
                                       new_pyrano_cal)
            # Overwrite the value in the run info file
            self.master.ivs2.update_irradiance(new_irradiance)
            # Redisplay the image with the new settings (saves config)
            self.master.redisplay_img(reprocess_adc=False)

    # -------------------------------------------------------------------------
    def update_values_in_eeprom(self):
        """Method to update the values in the Arduino EEPROM"""
        if not self.master.ivs2.arduino_sketch_supports_eeprom_config:
            warning_str = """
WARNING: Calibration values cannot be stored on the IV Swinger 2 hardware with
this version of the Arduino software. Please upgrade.
"""
            self.master.save_config()
            tkmsg_showwarning(self.master, message=warning_str)
        else:
            self.master.reestablish_arduino_comm(write_eeprom=True)

    # -------------------------------------------------------------------------
    def get_resistor_values(self):
        """Method to open the resistor values calibration dialog for the user to
           enter the resistor values
        """
        ResistorValuesDialog(self.master)

    # -------------------------------------------------------------------------
    def get_battery_bias(self):
        """Method to open the dialog for the user to run a bias battery
           calibration
        """
        BiasBatteryDialog(self.master)

    # -------------------------------------------------------------------------
    def invalidate_arduino_eeprom(self):
        """Method to invalidate the Arduino EEPROM"""
        if not self.master.ivs2.arduino_sketch_supports_dynamic_config:
            err_str = ("ERROR: The Arduino sketch does not support "
                       "invalidating the EEPROM. You must update it "
                       "to use this feature.")
            tkmsg_showerror(self.master, message=err_str)
            return
        msg_str = """
Are you SURE you want to invalidate the
Arduino EEPROM? This removes the
calibration values that are saved in the
IV Swinger 2 hardware (voltage, current,
resistors). After the invalidate, the app
will exit.
"""
        inval_eeprom = tkmsg_askyesno(self.master,
                                      "Invalidate EEPROM?", msg_str,
                                      default=tkmsg.NO)
        if inval_eeprom:
            self.master.ivs2.invalidate_arduino_eeprom()
            self.master.close_gui()
        else:
            return

    # -------------------------------------------------------------------------
    def show_calibration_help(self):
        """Method the open the calibration help dialog"""
        CalibrationHelpDialog(self.master)

    # -------------------------------------------------------------------------
    def show_help(self):
        """Method the open the global help dialog"""
        GlobalHelpDialog(self.master)


# Generic dialog class (based on
# http://effbot.org/tkinterbook/tkinter-dialog-windows.htm)
#
class Dialog(tk.Toplevel):
    """Class that is used for dialogs, derived from the Tkinter Toplevel
       class. This is a so-called "modal window".  This means that when
       it comes up, access to the main window is disabled until this
       window is closed. Focus is directed to this window when it opens,
       and is returned to the main window when it is closed. This class
       is intended to be extended by subclasses.  This class provides
       the modal behavior and the standard OK and/or Cancel
       buttons. Placeholder methods to create the body and perform the
       appropriate actions when the OK or Cancel button is pressed are
       provided for the subclass to override. A placeholder function to
       validate the input before applying it is also provided for
       optional override.

    """
    # pylint: disable=too-many-instance-attributes

    # Initializer
    def __init__(self, master=None, title=None, has_ok_button=True,
                 has_cancel_button=True, return_ok=False, ok_label="OK",
                 resizable=False, parent_is_modal=False,
                 min_height=None, max_height=None):
        # pylint: disable=too-many-arguments
        tk.Toplevel.__init__(self, master=master)
        self.master = master
        self.win_sys = self.master.tk.call("tk", "windowingsystem")
        self.has_ok_button = has_ok_button
        self.has_cancel_button = has_cancel_button
        self.return_ok = return_ok
        self.ok_label = ok_label
        self.resizable(width=resizable, height=resizable)
        self.transient(self.master)  # tie this window to master
        if title is not None:
            self.title(title)
        self.grab_set()  # block change of focus to master
        self.focus_set()
        self.snapshot_values = {}
        self.curr_values = {}
        self.parent_is_modal = parent_is_modal
        self.min_height = min_height
        self.max_height = max_height

        # Snapshot current values for revert
        self.snapshot()

        # Create body frame
        body = ttk.Frame(self)

        # Call body method to create body contents
        self.body(body)
        body.pack(fill=BOTH, expand=True)

        # Add button box with OK and Cancel buttons
        self.buttonbox(body)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        # Set the dialog position and size
        self.master.set_dialog_geometry(self,
                                        min_height=self.min_height,
                                        max_height=self.max_height)

        # Map Ctrl-A and Cmd-A (Mac) to select-all for Text widgets
        # (which includes ScrolledText)
        self.master.bind_class("Text", "<Control-a>", selectall)
        self.master.bind_class("Text", "<Command-a>", selectall)

        # Wait for dialog to be closed before returning control
        self.wait_window(self)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Method to create the dialog body. This method should be
           overridden.
        """
        pass  # override

    # -------------------------------------------------------------------------
    def buttonbox(self, master):
        """Method to add the standard button box. Override if you don't want
           the standard buttons.
        """
        box = ttk.Frame(master)
        if self.return_ok:
            ok = ttk.Button(box, text=self.ok_label, width=10, command=self.ok,
                            default=tk.ACTIVE)
            self.bind("<Return>", self.ok)
        else:
            ok = ttk.Button(box, text=self.ok_label, width=10, command=self.ok)
        cancel = ttk.Button(box, text="Cancel", width=10, command=self.cancel)
        self.bind("<Escape>", self.cancel)
        self.update_idletasks()

        # Layout
        box.pack(side=RIGHT)
        if sys.platform == "win32":  # Windows
            ok_col = 0
            cancel_col = 1
        else:  # Mac, other
            cancel_col = 1
            ok_col = 2
        if self.has_ok_button:
            ok.grid(column=ok_col, row=0)
        if self.has_cancel_button:
            cancel.grid(column=cancel_col, row=0)

    # -------------------------------------------------------------------------
    def ok(self, event=None):
        """Method that runs when the OK button is pressed"""
        # pylint: disable=unused-argument
        if not self.validate():
            return
        self.withdraw()
        self.update_idletasks()
        self.apply()
        self.close()

    # -------------------------------------------------------------------------
    def cancel(self, event=None):
        """Method that runs when the Cancel button is pressed"""
        # pylint: disable=unused-argument
        self.revert()
        self.close()

    # -------------------------------------------------------------------------
    def snapshot(self):
        """Method that snapshots current values for revert. Should be
           overridden to do what is appropriate for the derived class.
        """
        pass

    # -------------------------------------------------------------------------
    def validate(self):  # pylint: disable=no-self-use
        """Method that checks values entered in the dialog for validity. Should
           be overridden to do what is appropriate for the derived
           class. Returns False if a check fails and True if all pass.
        """
        return True

    # -------------------------------------------------------------------------
    def revert(self):
        """Method that reverts values from the snapthos. Should be overridden
           to do what is appropriate for the derived class.
        """
        pass

    # -------------------------------------------------------------------------
    def apply(self):
        """Method that "commits" the changes made in the dialog. Should be
           overridden to do what is appropriate for the derived
           class.
        """
        pass

    # -------------------------------------------------------------------------
    def close(self, event=None):
        """Method to close the dialog"""
        # pylint: disable=unused-argument

        # put focus back to the master window
        self.master.focus_set()
        self.destroy()
        if not self.parent_is_modal:
            self.master.mac_grayed_menu_workaround()


# Global help dialog class
#
class GlobalHelpDialog(Dialog):
    """Class that is extended from the generic Dialog class and is used for
       the global Help dialog
    """
    # Initializer
    def __init__(self, master=None):
        title = "IV Swinger 2 Help"
        Dialog.__init__(self, master=master, title=title,
                        has_cancel_button=False, return_ok=True,
                        resizable=True,
                        min_height=HELP_DIALOG_MIN_HEIGHT_PIXELS,
                        max_height=HELP_DIALOG_MAX_HEIGHT_PIXELS)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Method to create the dialog body, which is just a Text widget"""
        help_text_intro = """
More specific help for the IV Swinger 2 app can be found in "tooltips" that
appear when the mouse pointer is hovered over a control or set of controls,
and also via Help buttons that appear in various places. More comprehensive
help can be found in the IV Swinger 2 User Guide.

This global help dialog is intended to give a new user a very coarse overview
of how to use the app.

There are three main things you can do with the IV Swinger 2 app:
  1) Swing IV curves
  2) Deal with previous results
  3) Set preferences
"""
        help_heading_1 = """
Swinging IV curves"""
        help_text_1 = """
When the IV Swinger 2 hardware is connected to a USB port on the computer
running the app, the large "Swing!" button in the middle of the lower panel
is enabled. Click on the "Swing!" button to capture and display the IV curve.

"Plot Power" can be checked to include the power curve on the graph. This
can be done after the fact too.

"Loop Mode" can be checked to repeatedly swing IV curves. "Rate Limit" can
be checked to slow down the looping rate to a specified interval.  Since
looping can generate a lot of data and image files, the default is to not
save the results. "Save Results" can be checked to override this default.
"""
        help_heading_2 = """
Dealing with previous results"""
        help_text_2 = """
Click on the "Results Wizard" button to:
  - View results of previous runs
  - Combine multiple curves on the same plot (overlays)
  - Modify the title and appearance of curves and overlays
  - Copy them to USB (or elsewhere)
  - View the PDF
The Results Wizard does not require the hardware to be connected. In fact it
can be run on results that were collected by a different computer and copied
to a USB drive.
"""
        help_heading_3 = """
Setting preferences"""
        help_text_3 = """
Click on the "Preferences" button to change the default behavior of the app.
"Plotting" tab preference changes are visible immediately on the curve
currently being displayed, regardless of whether it is a new one or an older
one being displayed by the Results Wizard. Use the Help buttons on the
Preferences dialog tabs for more detailed information.

Note that when using the Results Wizard, the preferences settings reflect
those that were in effect for the curve being displayed. This allows the user
to make incremental changes. However, when the Results Wizard is closed,
the preferences revert to those that were in effect before it was opened.
"""
        font = HELP_DIALOG_FONT
        self.text = ScrolledText(master, height=1, borderwidth=10)
        self.text.tag_configure("body_tag", font=font)
        self.text.tag_configure("heading_tag", font=font, underline=True)
        self.text.insert("end", help_text_intro, ("body_tag"))
        self.text.insert("end", help_heading_1, ("heading_tag"))
        self.text.insert("end", help_text_1, ("body_tag"))
        self.text.insert("end", help_heading_2, ("heading_tag"))
        self.text.insert("end", help_text_2, ("body_tag"))
        self.text.insert("end", help_heading_3, ("heading_tag"))
        self.text.insert("end", help_text_3, ("body_tag"))
        self.text.pack(fill=BOTH, expand=True)


# Calibration help dialog class
#
class CalibrationHelpDialog(Dialog):
    """Class that is extended from the generic Dialog class and is used for
       the Calibration Help dialog
    """
    # Initializer
    def __init__(self, master=None):
        title = "Calibration Help"
        Dialog.__init__(self, master=master, title=title,
                        has_cancel_button=False, return_ok=True,
                        resizable=True,
                        min_height=HELP_DIALOG_MIN_HEIGHT_PIXELS,
                        max_height=HELP_DIALOG_MAX_HEIGHT_PIXELS)

    def body(self, master):
        """Method to create the dialog body, which is just a Text widget"""
        # pylint: disable=too-many-locals
        help_text_1 = """
Basic voltage and current calibration are performed by "correcting" the open
circuit voltage (Voc) and short circuit current (Isc) values of a given IV
curve with values that are measured with a digital multimeter (DMM).  The
calibration is stored on the IV Swinger 2 hardware:

     - One laptop can be used with different IV Swinger 2's and each will have
       its own calibration
     - A given IV Swinger 2 only needs to be calibrated once, and that
       calibration will apply for any laptop it is used with

Advanced voltage and current calibration provide more accuracy and, for
SSR-based IV Swinger 2's, may be performed indoors with a DC power supply
instead of a PV module or cell.

NOTE: the "Vref (+5V)" calibration must be performed BEFORE current and
      voltage calibration.
"""
        vref_heading = """
Vref (+5V):"""
        vref_help_text = """
  Vref calibration must be done before voltage and current calibrations.
  Measure the voltage between the GND and +5V pins on the PCB, PermaProto, or
  Arduino.

  The calibration is now stored on the IV Swinger 2 hardware and allows it to
  measure Vref fairly accurately every time it swings an IV curve. It is no
  longer necessary to perform a Vref calibration on each laptop.
"""
        voltage_basic_heading = """
Voltage - basic:"""
        voltage_basic_help_text = """
  1. Connect the DMM to the IV Swinger 2 binding posts with the PV
     module/cell connected normally
  2. Set the DMM to measure DC voltage
  3. Note the DMM value immediately before and after swinging a curve
  4. Enter this value in the Voltage Calibration dialog and hit OK

  The curve will be regenerated with Voc calibrated to this value, and future
  curves will be generated using the new calibration.
"""
        current_basic_heading = """
Current - basic (a bit trickier):"""
        current_basic_help_text = """
NOTE: if your IV Swinger 2 is SSR-based, the advanced current calibration is
recommended since it is not only more accurate, but it is easier.

This must be done on a very clear day, preferably near noon - otherwise the Isc
value fluctuates too much. You need one additional piece of equipment: a
standard 15A single-pole light switch with a short wire connected to each
screw.

  1. Connect the red DMM lead to the "A" DMM input and set it to measure DC
     current
  2. Connect the red DMM probe to the PV+ lead
  3. Connect the black DMM lead to the "COM" DMM input
  4. Connect the black DMM probe to the IV Swinger 2 red binding post
  5. Connect the IV Swinger 2 black binding post to the PV- lead
  6. With the light switch in the OFF position, connect one wire to each
     binding post
  7. Swing an IV curve
  8. Flip the light switch ON - this will short the binding posts to each
     other
  9. Note the DMM value - if it is fluctuating by more than a few mA, wait for
     a better day to calibrate
 10. Flip the light switch OFF
 11. Enter the noted DMM value in the Current Calibration dialog and hit OK

  The curve will be regenerated with Isc calibrated to this value, and future
  curves will be generated using the new calibration. Repeat steps 7 - 11 to
  confirm/adjust.

  Note that the light switch will eventually be damaged by this procedure due
  to arcing (the 15A rating is for AC, not DC).
"""
        voltage_adv_heading = """
Voltage - advanced:"""
        voltage_adv_help_text = """
There is separate help for advanced voltage calibration. Select the "Voltage -
advanced" menu entry and then click on the "Help" button in the dialog that
opens.
"""
        current_adv_heading = """
Current - advanced"""
        current_adv_help_text = """
There is separate help for advanced current calibration. Select the "Current -
advanced" menu entry and select the relay type (EMR or SSR). Then click on the
"Help" button in the dialog that opens.
"""
        resistors_heading = """
Resistors:"""
        resistors_help_text = """
  Measured values of the resistors used in the IV Swinger 2 voltmeter and
  ammeter circuits can be specified. Note, however, that it is not required to
  do this if you perform the voltage and current calibrations since those will
  account for any differences in the resistances from their nominal values (in
  addition to other sources of error).  It is required, however, if the
  software is being used with a "scaled up" or "scaled down" version of IV
  Swinger 2 (i.e. one that is configured for higher or lower voltages or
  currents than the normal module version). This is the case for the cell
  version: Resistor R1 must be set to a value of 0.0, and when the DIP switch
  is set to the OFF position (or the jumper is removed) the value of resistor
  RF must be set to RF + RF1 (755000 nominal).
"""
        pyrano_heading = """
Pyranometer:"""
        pyrano_help_text = """
  If the optional pyranometer is being used, this can be used to calibrate the
  irradiance to a value measured with a reference pyranometer. It is enabled
  when a curve has been swung with the pyranometer.  The curve will be
  redisplayed with the new irradiance value, and future curves will be
  generated using the new calibration.
"""
        bias_battery_heading = """
Bias Battery:"""
        bias_battery_help_text = """
  This calibration is used only for the cell version of IV Swinger 2
  which sometimes requires a bias battery in series with the PV cell.
  More help is available when this option is selected.
"""
        invalidate_eeprom_heading = """
Invalidate Arduino EEPROM:"""
        invalidate_eeprom_help_text = """
  The calibration values for the voltage, current and resistors are
  saved to the hardware in the Arduino EEPROM. This menu item is
  primarily for testing that the software handles the case of IV Swinger
  2 hardware that is being used for the first time. It invalidates all
  calibration values that have been saved in the hardware."""
        font = HELP_DIALOG_FONT
        self.text = ScrolledText(master, height=1, borderwidth=10)
        self.text.tag_configure("body_tag", font=font)
        self.text.tag_configure("heading_tag", font=font, underline=True)
        self.text.insert("end", help_text_1, ("body_tag"))
        self.text.insert("end", vref_heading, ("heading_tag"))
        self.text.insert("end", vref_help_text, ("body_tag"))
        self.text.insert("end", voltage_basic_heading, ("heading_tag"))
        self.text.insert("end", voltage_basic_help_text, ("body_tag"))
        self.text.insert("end", current_basic_heading, ("heading_tag"))
        self.text.insert("end", current_basic_help_text, ("body_tag"))
        self.text.insert("end", voltage_adv_heading, ("heading_tag"))
        self.text.insert("end", voltage_adv_help_text, ("body_tag"))
        self.text.insert("end", current_adv_heading, ("heading_tag"))
        self.text.insert("end", current_adv_help_text, ("body_tag"))
        self.text.insert("end", resistors_heading, ("heading_tag"))
        self.text.insert("end", resistors_help_text, ("body_tag"))
        self.text.insert("end", pyrano_heading, ("heading_tag"))
        self.text.insert("end", pyrano_help_text, ("body_tag"))
        self.text.insert("end", bias_battery_heading, ("heading_tag"))
        self.text.insert("end", bias_battery_help_text, ("body_tag"))
        self.text.insert("end", invalidate_eeprom_heading, ("heading_tag"))
        self.text.insert("end", invalidate_eeprom_help_text, ("body_tag"))
        self.text.pack(fill=BOTH, expand=True)


# Advanced SSR current calibration help dialog class
#
class AdvSsrCurrentCalHelpDialog(Dialog):
    """Class that is extended from the generic Dialog class and is used for
       the SSR-only advanced current calibration Help dialog
    """
    # Initializer
    def __init__(self, master=None):
        title = "Advanced Current Calibration Help (SSR)"
        Dialog.__init__(self, master=master, title=title,
                        has_cancel_button=False, return_ok=True,
                        parent_is_modal=True,
                        resizable=True,
                        min_height=HELP_DIALOG_MIN_HEIGHT_PIXELS,
                        max_height=HELP_DIALOG_MAX_HEIGHT_PIXELS)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Method to create the dialog body, which is just a Text widget"""
        help_text_1 = """
This current calibration method works on IV Swinger 2 hardware with
solid-state relays (SSRs) only. It is easier to perform and more
accurate than the basic current calibration or the advanced current
calibration for hardware with electromagnetic relays (EMRs).

Connections:

  1. Connect the red digital multimeter (DMM) lead to the "A" DMM input
     and set it to measure DC current

  2. Connect the red DMM probe to the red (+) terminal of a DC power
     supply

  3. Connect the black DMM lead to the "COM" DMM input

  4. Connect the black DMM probe to the IV Swinger 2 red binding post

  5. Connect the IV Swinger 2 black binding post to the black (-)
     terminal of the DC power supply

  The DC power supply is now connected to the IV Swinger 2 with the DMM
  in series on the positive side.

  NOTE: A PV module or cell may be used instead of the DC power
        supply. Using a DC power supply is preferable, however,
        because its current is adjustable and more stable. That
        is not to mention the obvious advantage that it can be
        done indoors at any time of day in any weather.

Calibration:

  1. Turn on the DC power supply

  2. Click on the "Get Point 1" button

  3. Look at the DMM display and note the value (you have 3 seconds)

  4. Adjust the DC power supply current so that the DMM reads
     approximately 2 A (or 20% of the maximum value you expect to ever
     measure). You may repeat the previous two steps to make this
     adjustment.

  5. Enter the final noted DMM measured Point 1 value in the text entry
     box

  6. Repeat steps 2 - 5 for Point 2. Shoot for a current around 8 A (or
     80% of the maximum value you expect to ever measure).

  7. Click the "Calibrate" button

  8. Adjust the DC power supply current to an arbitrary value

  9. Click the "Test" button

 10. Enter the DMM value in the text entry box and hit Enter

 11. Note the Error value (mA and %)

 12. Repeat steps 8 - 11 as many times as desired. Use different DC
     power supply adjustments to test points throughout the desired
     current range.

 13. If you are unhappy with the calibration, repeat steps 2 - 12.

 14. Click OK when you are happy with the calibration. Clicking Cancel
     or closing the dialog window discards the calibration.

  NOTE 1: To avoid damage to the SSRs, a short cooling off period is
     enforced for currents above 6.75 amps.

  NOTE 2: Unlike the basic calibration, the advanced calibration does
     not require an IV curve to be swung before the calibration.
     However, it also does not recalibrate and redisplay the most recent
     curve the way the basic calibration does.

  NOTE 3: The Test button feature may be used without performing a new
     calibration.

  NOTE 4: The slope and intercept values may be manually entered to
     override the calculated values. But you should have a good reason
     if you do this.
"""
        font = HELP_DIALOG_FONT
        self.text = ScrolledText(master, height=1, borderwidth=10)
        self.text.tag_configure("body_tag", font=font)
        self.text.tag_configure("heading_tag", font=font, underline=True)
        self.text.insert("end", help_text_1, ("body_tag"))
        self.text.pack(fill=BOTH, expand=True)


# Advanced EMR current calibration help dialog class
#
class AdvEmrCurrentCalHelpDialog(Dialog):
    """Class that is extended from the generic Dialog class and is used for
       the EMR-only advanced current calibration Help dialog
    """
    # Initializer
    def __init__(self, master=None):
        title = "Advanced Current Calibration Help (EMR)"
        Dialog.__init__(self, master=master, title=title,
                        has_cancel_button=False, return_ok=True,
                        parent_is_modal=True,
                        resizable=True,
                        min_height=HELP_DIALOG_MIN_HEIGHT_PIXELS,
                        max_height=HELP_DIALOG_MAX_HEIGHT_PIXELS)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Method to create the dialog body, which is just a Text widget"""
        help_text_1 = """
This current calibration method works on IV Swinger 2 hardware with
electromechanical relays (EMRs). Its advantage over the basic current
calibration is that uses two points instead of just one. This can
improve the accuracy of the calibration over the complete range.

Required conditions:

  The calibration must be done on a very clear day, preferably near
  noon.

Additional equipment:

  Standard 15A single-pole light switch with a short wire connected to
  each screw

  NOTE: This process *WILL* destroy the switch after some number of
  measurements. An alternative is a knife switch or other switch rated
  for DC current. Othwerwise, buy in bulk if you plan on calibrating
  often.

Connections:

  1. Connect the red digital multimeter (DMM) lead to the "A" DMM input
     and set it to measure DC current

  2. Connect the red DMM probe to the PV+ lead

  3. Connect the black DMM lead to the "COM" DMM input

  4. Connect the black DMM probe to the IV Swinger 2 red binding post

  5. Connect the IV Swinger 2 black binding post to the PV- lead

  6. With the light switch in the OFF position, connect one wire to each
     binding post

  The PV module/cell is now connected to the IV Swinger 2 with the DMM
  in series on the positive side. The switch, when turned on, shorts the
  PV+ to the PV- through the DMM.

  NOTE: Unlike the calibration for the SSR-based designs, using a DC
        power supply is not possible; it MUST be done with a PV
        module/cell

Calibration:

  1. Prop the PV so that the sun is hitting it at a very oblique angle
     (shoot for an angle of about 80 degrees off of perpendicular).

  2. Click on the "Get Point 1" button.

  3. Adjust the angle of the PV until the current is approximately 2 A
     (or 20% of the maximum value you expect to ever measure). If you
     get an error, try increasing the angle.

  4. Click on the "Get Point 1" button several more times, checking that
     the value is not changing by more than a few mA. If it is, then try
     increasing the angle of the PV a bit more or wait for a better day
     to calibrate.

  5. Flip the light switch ON

  6. Look at the DMM display and enter the DMM measured Point 1 value in
     the text entry box

  7. Flip the light switch OFF. [If the DMM current does not drop to
     zero, your switch is fried.]

  8. Repeat steps 1 - 7 for Point 2. Shoot for a current around 8 A (or
     80% of the maximum value you expect to ever measure). A good
     starting point is an angle of about 35 degrees off of
     perpendicular.

  9. Click the "Calibrate" button

 10. Prop the PV at an arbitrary angle to the sun

 11. Click the "Test" button

 12. Flip the light switch ON

 13. Enter the DMM value in the text entry box and hit Enter

 14. Note the Error value (mA and %)

 15. Flip the light switch OFF. [If the DMM current does not drop to
     zero, your switch is fried.]

 16. Repeat steps 10 - 15 as many times as desired (or until your switch
     fries, which may happen first). Use different PV angles to test
     points throughout the desired current range.

 17. If you are unhappy with the calibration, repeat steps 1 - 17.

 18. Click OK when you are happy with the calibration. Clicking Cancel
     or closing the dialog window discards the calibration.

  NOTE 1: Unlike the basic calibration, the advanced calibration does
     not require an IV curve to be swung before the calibration.
     However, it also does not recalibrate or redisplay the most recent
     curve the way the basic calibration does.

  NOTE 2: The Test button feature may be used without performing a new
     calibration.

  NOTE 3: The switch will last a lot longer if the PV is shaded whenever
     it is turned ON or OFF. However, there may be small changes in the
     irradiance in the time that it takes to do that, affecting the
     accuracy of the calibration.

  NOTE 4: The slope and intercept values may be manually entered to
     override the calculated values. But you should have a good reason
     if you do this.
"""
        font = HELP_DIALOG_FONT
        self.text = ScrolledText(master, height=1, borderwidth=10)
        self.text.tag_configure("body_tag", font=font)
        self.text.tag_configure("heading_tag", font=font, underline=True)
        self.text.insert("end", help_text_1, ("body_tag"))
        self.text.pack(fill=BOTH, expand=True)


# Advanced voltage calibration help dialog class
#
class AdvVoltageCalHelpDialog(Dialog):
    """Class that is extended from the generic Dialog class and is used for
       the advanced voltage calibration Help dialog
    """
    # Initializer
    def __init__(self, master=None):
        title = "Advanced Voltage Calibration Help (EMR)"
        Dialog.__init__(self, master=master, title=title,
                        has_cancel_button=False, return_ok=True,
                        parent_is_modal=True,
                        resizable=True,
                        min_height=HELP_DIALOG_MIN_HEIGHT_PIXELS,
                        max_height=HELP_DIALOG_MAX_HEIGHT_PIXELS)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Method to create the dialog body, which is just a Text widget"""
        help_text_1 = """
This voltage calibration method works on all types of IV Swinger 2
hardware.  Its advantage over the basic current calibration is that uses
two points instead of just one. This can improve the accuracy of the
calibration over the complete range.

A DC power supply is required to perform this calibration. This is
because the Voc of a PV module or cell is not controllable. The DC power
supply should be able to generate voltages up to about 80% of the
maximum Voc that you expect to be measuring.

Connections:

  1. Connect the red digital multimeter (DMM) lead to the "V" DMM input
     and set it to measure DC voltage

  2. Connect the red DMM probe to the IV Swinger 2 red binding post

  3. Connect the black DMM lead to the "COM" DMM input

  4. Connect the black DMM probe to the IV Swinger 2 black binding post

  5. Connect the IV Swinger 2 red binding post to the red (+) terminal
     of the DC power supply

  6. Connect the IV Swinger 2 black binding post to the black (-)
     terminal of the DC power supply

Calibration:

  1. Turn on the DC power supply

  2. Adjust the DC power supply voltage so that the DMM reads
     approximately 20% of the maximum value you expect to ever
     measure.

  3. Click on the "Get Point 1" button.

  4. Look at the DMM display and enter the DMM measured Point 1 value in
     the text entry box. This value should be the same as it was before
     you clicked on the button.

  5. Repeat steps 2 - 4 for Point 2. Shoot for a voltage around 80% of
     the maximum value you expect to ever measure.

  6. Click the "Calibrate" button

  7. Adjust the DC power supply voltage to an arbitrary value

  8. Click the "Test" button

  9. Enter the DMM value in the text entry box and hit Enter

 10. Note the Error value (mV and %)

 11. Repeat steps 7 - 10 as many times as desired. Use different DC
     power supply adjustments to test points throughout the desired
     voltage range.

 12. If you are unhappy with the calibration, repeat steps 2 - 11.

 13. Click OK when you are happy with the calibration. Clicking Cancel
     or closing the dialog window discards the calibration.

  NOTE 1: Unlike the basic calibration, the advanced calibration does
     not require an IV curve to be swung before the calibration.
     However, it also does not recalibrate or redisplay the most recent
     curve the way the basic calibration does.

  NOTE 2: The Test button feature may be used without performing a new
     calibration.

  NOTE 3: The slope and intercept values may be manually entered to
     override the calculated values. But you should have a good reason
     if you do this.
"""
        font = HELP_DIALOG_FONT
        self.text = ScrolledText(master, height=1, borderwidth=10)
        self.text.tag_configure("body_tag", font=font)
        self.text.tag_configure("heading_tag", font=font, underline=True)
        self.text.insert("end", help_text_1, ("body_tag"))
        self.text.pack(fill=BOTH, expand=True)


# Downlevel Arduino sketch dialog class
#
class DownlevelArduinoSketchDialog(Dialog):
    """Class that is extended from the generic Dialog class and is used for
       the downlevel Arduino sketch dialog
    """
    # Initializer
    def __init__(self, master=None):
        title = "Downlevel Arduino Code"
        Dialog.__init__(self, master=master, title=title,
                        has_cancel_button=False, return_ok=True,
                        resizable=True,
                        min_height=HELP_DIALOG_MIN_HEIGHT_PIXELS,
                        max_height=HELP_DIALOG_MAX_HEIGHT_PIXELS)
        self.master = master

    def body(self, master):
        """Method to create the dialog body, which is just a Text widget"""
        app_version_text = self.master.version
        url = ("\n          https://raw.githubusercontent.com/"
               "csatt/IV_Swinger/")
        url += app_version_text
        url += ("/Arduino/IV_Swinger2/IV_Swinger2.ino")

        heading_text = "** ATTENTION **\n\n"
        text_1 = """
The Arduino software ("sketch") on the IV Swinger 2 hardware that is currently
connected is not the most current version.
"""
        text_2 = ("\n    Version detected: {}"
                  .format(self.master.ivs2.arduino_sketch_ver))
        text_3 = ("\n     Current version: {}\n"
                  .format(LATEST_SKETCH_VER))
        text_4 = """
You may continue with the older version, but it is recommended that you update
at your earliest convenience.

Here is the procedure:

      - Install the Arduino application (IDE) from:

           https://www.arduino.cc/en/Main/Software

      - Open the Arduino application

      - Find where the Arduino application looks for sketches:

           Arduino->Preferences->Sketchbook location

      - Use your browser to go to:
"""
        text_5 = url
        text_6 = """

      - Use your browser's "Save As" to save IV_Swinger.ino to the Arduino
        sketchbook folder found above (make sure your browser doesn't add an
        extension like .txt to the file name)

      - Go back to the Arduino application and find the IV_Swinger2.ino sketch
        using:

           File->Open

        The Arduino application will inform you that IV_Swinger2.ino must be in
        a folder named IV_Swinger2 and it will offer to do that for you. Accept
        its kind offer.

        Click on arrow button or select "Upload" from "Sketch" menu.
"""
        font = HELP_DIALOG_FONT
        self.text = ScrolledText(master, width=len(url)-12, height=1,
                                 borderwidth=10)
        self.text.tag_configure("heading_tag", font=font, underline=True)
        self.text.tag_configure("body_tag", font=font)
        self.text.insert("end", heading_text, ("heading_tag"))
        self.text.insert("end", text_1, ("body_tag"))
        self.text.insert("end", text_2, ("body_tag"))
        self.text.insert("end", text_3, ("body_tag"))
        self.text.insert("end", text_4, ("body_tag"))
        self.text.insert("end", text_5, ("body_tag"))
        self.text.insert("end", text_6, ("body_tag"))
        self.text.pack(fill=BOTH, expand=True)


# Advanced calibration dialog
#
class AdvCalDialog(Dialog):
    """Class that is extended from the generic Dialog class and is used for
       the advanced calibration dialogs. This class is used for both the
       advanced current and the advanced voltage calibration dialogs.
    """
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods

    # Initializer
    def __init__(self, master=None, cal_type="None"):
        self.master = master
        self.cal_type = cal_type
        title = "{} Calibration - advanced".format(self.cal_type)
        self.relay_type = tk.StringVar()
        self.pt_1_uncal_value = tk.StringVar()
        self.pt_1_dmm_value = tk.StringVar()
        self.pt_2_uncal_value = tk.StringVar()
        self.pt_2_dmm_value = tk.StringVar()
        self.slope = tk.StringVar()
        self.intercept = tk.StringVar()
        self.test_dmm_value = tk.StringVar()
        self.test_cal_value = tk.StringVar()
        self.test_err = tk.StringVar()
        self.ssr_mode = "Unknown"
        self.x1 = "Unknown"  # Point 1 uncalibrated value
        self.y1 = "Unknown"  # Point 1 DMM value
        self.x2 = "Unknown"  # Point 2 uncalibrated value
        self.y2 = "Unknown"  # Point 2 DMM value
        if self.type_is_current():
            self.m = self.master.ivs2.i_cal    # Slope
            self.b = self.master.ivs2.i_cal_b  # Intercept
            self.unit_abbrev = "A"
        else:
            self.m = self.master.ivs2.v_cal    # Slope
            self.b = self.master.ivs2.v_cal_b  # Intercept
            self.unit_abbrev = "V"
        self.test_dmm_units = "Unknown"     # Test: DMM amps/volts
        self.test_cal_units = "Unknown"     # Test: Calibrated amps/volts
        # Clear out old ADC value from IVS2
        self.master.ivs2.reset_adv_cal_adc_val()
        Dialog.__init__(self, master=master, title=title)

    # -------------------------------------------------------------------------
    def type_is_current(self):
        """Method to test if the type attribute's value is "Current"
        """
        if self.cal_type == "Current":
            return True
        return False

    # -------------------------------------------------------------------------
    def body(self, master):
        """Method to create the dialog's body frame (overrides the parent class
           method)
        """
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-statements
        frame = ttk.Frame(master)

        # Add label with description text
        if self.type_is_current():
            desc_text = """
This current calibration uses two calibrated points to obtain both a
slope and an intercept for the calibration equation. It also supports
manual entry of the slope and intercept and it supports testing the
calibration values before committing them. Both EMR-based and SSR-based
IVS2s are supported, but an external switch is required for EMR-based
IVS2s."""
        else:
            desc_text = """
This voltage calibration uses two calibrated points to obtain both a
slope and an intercept for the calibration equation. It also supports
manual entry of the slope and intercept, and it supports testing the
calibration values before committing them."""
        desc_label = ttk.Label(master=frame, text=desc_text)

        # Add label and relay type radio buttons in their own container
        # box
        relay_type_radio_button_box = ttk.Frame(master=frame, padding=10)
        relay_type_label = ttk.Label(relay_type_radio_button_box,
                                     text="Relay type (required): ")
        ssr_radio_button = ttk.Radiobutton(relay_type_radio_button_box,
                                           text="Solid-state (SSR)",
                                           variable=self.relay_type,
                                           value="SSR")
        emr_radio_button = ttk.Radiobutton(relay_type_radio_button_box,
                                           text="Electromechanical (EMR)",
                                           variable=self.relay_type,
                                           value="EMR")
        self.relay_type.set(self.master.ivs2.relay_type)

        # Add Help button in its own container box
        help_button_box = ttk.Frame(master=frame, padding=10)
        help_button = ttk.Button(help_button_box,
                                 text="Help", width=8,
                                 command=self.show_adv_cal_help)

        ################
        #  Point 1
        ################
        # Add point 1 button and label in a container box
        pt_1_button_box = ttk.Frame(master=frame, padding=10)
        pt_1_button = ttk.Button(pt_1_button_box,
                                 text="Get Point 1",
                                 command=self.get_pt_1_uncal_value)
        pt_1_uncal_value_label = ttk.Label(pt_1_button_box,
                                           textvariable=self.pt_1_uncal_value)
        self.update_uncal_value(pt_1=True)

        # Add DMM labels and entry in their own container box
        pt_1_dmm_entry_box = ttk.Frame(master=frame)
        pt_1_dmm_label1 = ttk.Label(master=pt_1_dmm_entry_box,
                                    text="DMM measured Point 1 value: ")
        pt_1_dmm_entry = ttk.Entry(pt_1_dmm_entry_box,
                                   width=9,
                                   textvariable=self.pt_1_dmm_value)
        pt_1_dmm_entry.bind("<Return>", self.apply_pt_1_dmm_value)
        pt_1_dmm_label2 = ttk.Label(master=pt_1_dmm_entry_box,
                                    text="{}  ".format(self.unit_abbrev))

        ################
        #  Point 2
        ################
        # Add point 2 button and label in a container box
        pt_2_button_box = ttk.Frame(master=frame, padding=10)
        pt_2_button = ttk.Button(pt_2_button_box,
                                 text="Get Point 2",
                                 command=self.get_pt_2_uncal_value)
        pt_2_uncal_value_label = ttk.Label(pt_2_button_box,
                                           textvariable=self.pt_2_uncal_value)
        self.update_uncal_value(pt_1=False)

        # Add DMM labels and entry in their own container box
        pt_2_dmm_entry_box = ttk.Frame(master=frame)
        pt_2_dmm_label1 = ttk.Label(master=pt_2_dmm_entry_box,
                                    text="DMM measured Point 2 value: ")
        pt_2_dmm_entry = ttk.Entry(pt_2_dmm_entry_box,
                                   width=9,
                                   textvariable=self.pt_2_dmm_value)
        pt_2_dmm_entry.bind("<Return>", self.apply_pt_2_dmm_value)
        pt_2_dmm_label2 = ttk.Label(master=pt_2_dmm_entry_box,
                                    text="{}  ".format(self.unit_abbrev))

        ################
        #  Calibrate
        ################
        # Add calibrate button in its own container box
        calibrate_button_box = ttk.Frame(master=frame, padding=10)
        calibrate_button = ttk.Button(calibrate_button_box,
                                      text="Calibrate",
                                      command=self.calibrate)

        # Add slope labels and entry in their own container box
        slope_entry_box = ttk.Frame(master=frame)
        slope_label = ttk.Label(master=slope_entry_box,
                                text="Slope: ")
        slope_entry = ttk.Entry(slope_entry_box,
                                width=9,
                                textvariable=self.slope)
        slope_entry.bind("<Return>", self.apply_slope)
        self.slope_warning = ttk.Label(master=slope_entry_box,
                                       text="")
        self.update_slope()

        # Add intercept labels and entry in their own container box
        intercept_entry_box = ttk.Frame(master=frame)
        intercept_label = ttk.Label(master=intercept_entry_box,
                                    text="Intercept: ")
        intercept_entry = ttk.Entry(intercept_entry_box,
                                    width=9,
                                    textvariable=self.intercept)
        intercept_entry.bind("<Return>", self.apply_intercept)
        self.intercept_warning = ttk.Label(master=intercept_entry_box,
                                           text="")
        self.update_intercept()

        ################
        #  Test
        ################
        # Add test button in its own container box
        test_button_box = ttk.Frame(master=frame, padding=10)
        test_button = ttk.Button(test_button_box,
                                 text="Test",
                                 command=self.get_test_uncal_value)

        # Add calibrated value label
        test_cal_value_label = ttk.Label(master=frame,
                                         textvariable=self.test_cal_value)
        self.update_test_cal_value()

        # Add DMM labels and entry in their own container box
        test_entry_box = ttk.Frame(master=frame)
        test_label1 = ttk.Label(master=test_entry_box,
                                text="DMM measured value: ")
        test_entry = ttk.Entry(test_entry_box,
                               width=9,
                               textvariable=self.test_dmm_value)
        test_entry.bind("<Return>", self.apply_test_dmm_value)
        test_label2 = ttk.Label(master=test_entry_box,
                                text="{}  ".format(self.unit_abbrev))

        # Add test error label in its own container box
        test_err_label = ttk.Label(master=frame,
                                   textvariable=self.test_err)
        self.update_test_err_val()

        # Layout
        separators = [ttk.Separator(master=frame, orient=HORIZONTAL)
                      for _ in range(6)]
        row = 0
        sp = 0
        desc_label.grid(column=0, row=row, sticky=W)
        row += 1
        if self.type_is_current():
            separators[sp].grid(column=0, row=row, sticky=(E, W))
            sp += 1
            row += 1
            relay_type_radio_button_box.grid(column=0, row=row,
                                             sticky=(S, W), pady=4)
            relay_type_label.grid(column=0, row=0, sticky=(S, W), pady=4)
            ssr_radio_button.grid(column=0, row=1, sticky=(S, W), pady=4)
            emr_radio_button.grid(column=0, row=2, sticky=(S, W), pady=4)
            row += 1
        separators[sp].grid(column=0, row=row, sticky=(E, W))
        sp += 1
        row += 1
        help_button_box.grid(column=0, row=row, sticky=(S, W), pady=4)
        help_button.grid(column=0, row=0, sticky=W)
        row += 1
        separators[sp].grid(column=0, row=row, sticky=(E, W))
        sp += 1
        row += 1
        pt_1_button_box.grid(column=0, row=row, sticky=(S, W), pady=4)
        pt_1_button.grid(column=0, row=0, sticky=W)
        pt_1_uncal_value_label.grid(column=1, row=0, sticky=W)
        row += 1
        pt_1_dmm_entry_box.grid(column=0, row=row, sticky=(S, W), pady=4)
        pt_1_dmm_label1.grid(column=0, row=0, sticky=W)
        pt_1_dmm_entry.grid(column=1, row=0, sticky=W)
        pt_1_dmm_label2.grid(column=2, row=0, sticky=W)
        row += 1
        separators[sp].grid(column=0, row=row, sticky=(E, W))
        sp += 1
        row += 1
        pt_2_button_box.grid(column=0, row=row, sticky=(S, W), pady=4)
        pt_2_button.grid(column=0, row=0, sticky=W)
        pt_2_uncal_value_label.grid(column=1, row=0, sticky=W)
        row += 1
        pt_2_dmm_entry_box.grid(column=0, row=row, sticky=(S, W), pady=4)
        pt_2_dmm_label1.grid(column=0, row=0, sticky=W)
        pt_2_dmm_entry.grid(column=1, row=0, sticky=W)
        pt_2_dmm_label2.grid(column=2, row=0, sticky=W)
        row += 1
        separators[sp].grid(column=0, row=row, sticky=(E, W))
        sp += 1
        row += 1
        calibrate_button_box.grid(column=0, row=row, sticky=(S, W), pady=4)
        calibrate_button.grid(column=0, row=0, sticky=W)
        row += 1
        slope_entry_box.grid(column=0, row=row, sticky=(S, W), pady=4)
        slope_label.grid(column=0, row=0, sticky=W)
        slope_entry.grid(column=1, row=0, sticky=W)
        self.slope_warning.grid(column=2, row=0, sticky=W)
        row += 1
        intercept_entry_box.grid(column=0, row=row, sticky=(S, W), pady=4)
        intercept_label.grid(column=0, row=0, sticky=W)
        intercept_entry.grid(column=1, row=0, sticky=W)
        self.intercept_warning.grid(column=2, row=0, sticky=W)
        row += 1
        separators[sp].grid(column=0, row=row, sticky=(E, W))
        sp += 1
        row += 1
        test_button_box.grid(column=0, row=row, sticky=(S, W), pady=4)
        test_button.grid(column=0, row=0, sticky=W)
        row += 1
        test_cal_value_label.grid(column=0, row=row, sticky=W)
        row += 1
        test_entry_box.grid(column=0, row=row, sticky=(S, W), pady=4)
        test_label1.grid(column=0, row=0, sticky=W)
        test_entry.grid(column=1, row=0, sticky=W)
        test_label2.grid(column=2, row=0, sticky=W)
        row += 1
        test_err_label.grid(column=0, row=row, sticky=W)
        frame.pack()

    # ------------------------------------------------------------------------
    def show_adv_cal_help(self):
        """Display advanced current/voltage calibration help"""
        if self.type_is_current():
            if not self.relay_type_is_valid():
                return RC_FAILURE
            if self.ssr_mode:
                AdvSsrCurrentCalHelpDialog(self.master)
            else:
                AdvEmrCurrentCalHelpDialog(self.master)
        else:
            AdvVoltageCalHelpDialog(self.master)

        return RC_SUCCESS

    # ------------------------------------------------------------------------
    def relay_type_is_valid(self):
        """Check that the relay type has been set properly"""
        relay_type = self.relay_type.get()

        if relay_type == "Unknown":
            error_msg = """
ERROR: Please indicate the relay type (SSR/EMR) above"""
            tkmsg.showerror(message=error_msg)
            return False

        if (relay_type == "SSR" and not
                self.master.ivs2.arduino_sketch_supports_ssr_adv_current_cal):
            error_msg = """
ERROR: The Arduino sketch does not support
SSR current calibration. You must update it
to use this feature"""
            tkmsg.showerror(message=error_msg)
            return False

        # As a side-effect, set the self.ssr_mode attribute
        # appropriately
        self.ssr_mode = (relay_type == "SSR")
        self.master.ivs2.relay_type = relay_type

        return True

    # -------------------------------------------------------------------------
    def get_pt_1_uncal_value(self):
        """Method to get the uncalibrated value for point 1 from the hardware,
           set the x1 attribute with its value, and update the label
           after the button.
        """
        self.pt_1_dmm_value.set("")
        rc = self.get_uncal_value()
        if rc == RC_SUCCESS:
            if self.type_is_current():
                uncal_value_str = self.master.ivs2.get_adv_current_cal_amps()
            else:
                uncal_value_str = self.master.ivs2.get_adv_voltage_cal_volts()
            try:
                uncal_value = float(uncal_value_str)
                self.update_uncal_value(pt_1=True)
                if uncal_value > 0.0:
                    self.x1 = uncal_value
                else:
                    error_msg = """
ERROR: Hardware measured value must be greater than zero"""
                    tkmsg.showerror(message=error_msg)
            except ValueError:
                error_msg = """
ERROR: Hardware returned invalid measured value ("{}")
""".format(uncal_value_str)
                tkmsg.showerror(message=error_msg)

    # -------------------------------------------------------------------------
    def get_pt_2_uncal_value(self):
        """Method to get the uncalibrated value for point 2 from the hardware,
           set the x2 attribute with its value, and update the label
           after the button.
        """
        self.pt_2_dmm_value.set("")
        rc = self.get_uncal_value()
        if rc == RC_SUCCESS:
            if self.type_is_current():
                uncal_value_str = self.master.ivs2.get_adv_current_cal_amps()
            else:
                uncal_value_str = self.master.ivs2.get_adv_voltage_cal_volts()
            try:
                uncal_value = float(uncal_value_str)
                self.update_uncal_value(pt_1=False)
                if uncal_value > 0.0:
                    self.x2 = uncal_value
                else:
                    error_msg = """
ERROR: Hardware measured value must be greater than zero"""
                    tkmsg.showerror(message=error_msg)
            except ValueError:
                error_msg = """
ERROR: Hardware measured value must be valid"""
                tkmsg.showerror(message=error_msg)

    # -------------------------------------------------------------------------
    def get_uncal_value(self):
        """Method to get the uncalibrated value from the hardware
        """
        if self.type_is_current() and not self.relay_type_is_valid():
            return RC_FAILURE
        if self.type_is_current() and self.ssr_mode:
            rc = self.master.ivs2.request_ssr_adv_current_calibration_val()
            if rc == RC_SSR_HOT:
                error_msg = """
ERROR: SSR needs another moment
to cool down - try again"""
                tkmsg.showerror(message=error_msg)
                return rc
            if rc != RC_SUCCESS:
                error_msg = """
ERROR: Failed to send advanced SSR current
calibration request to Arduino
(rc = {})""".format(rc)
                tkmsg.showerror(message=error_msg)
                return rc
        else:
            rc = self.master.ivs2.request_adv_calibration_vals()
            if rc != RC_SUCCESS:
                if self.type_is_current() or rc != RC_ISC_TIMEOUT:
                    error_msg = """
ERROR: Failed to send advanced
calibration request to Arduino
(rc = {})""".format(rc)
                    tkmsg.showerror(message=error_msg)
                    return rc
            if self.type_is_current():
                self.master.ivs2.get_emr_adv_current_cal_adc_val()
            else:
                self.master.ivs2.get_adv_voltage_cal_adc_val()

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def update_uncal_value(self, pt_1=True):
        """Method to update the value displayed for the point 1 or point 2
           uncalibrated value.
        """
        try:
            adc = int(self.master.ivs2.adv_cal_adc_val)
            if self.type_is_current():
                units = float(self.master.ivs2.get_adv_current_cal_amps())
            else:
                units = float(self.master.ivs2.get_adv_voltage_cal_volts())
            val_str = "{:0.3f} {}  (ADC={})".format(units,
                                                    self.unit_abbrev,
                                                    adc)
        except ValueError:
            if self.type_is_current():
                val_str = self.master.ivs2.get_adv_current_cal_amps()
            else:
                val_str = self.master.ivs2.get_adv_voltage_cal_volts()
        label_str = "Uncalibrated value:  {}".format(val_str)
        if pt_1:
            self.pt_1_uncal_value.set(label_str)
        else:
            self.pt_2_uncal_value.set(label_str)

    # -------------------------------------------------------------------------
    def apply_pt_1_dmm_value(self, event=None):
        """Method to get the user-entered measured value from the DMM
           entry box for point 1 and apply it to the y1 attribute if it
           is a valid floating point number.
        """
        try:
            self.y1 = float(self.pt_1_dmm_value.get())
            if self.y1 == 0.0:
                error_msg = """
ERROR: A non-zero value must be entered
for the DMM measured Point 1 value"""
                tkmsg.showerror(message=error_msg)
                return RC_FAILURE
            if event is None:
                log_str = ("{} cal point 1 (uncal, dmm): {}, {:.6f}"
                           .format(self.cal_type, self.x1, self.y1))
                self.master.ivs2.logger.log(log_str)
        except ValueError:
            error_msg = """
ERROR: A numerical value must be entered
for the DMM measured Point 1 value"""
            tkmsg.showerror(message=error_msg)
            return RC_FAILURE
        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def apply_pt_2_dmm_value(self, event=None):
        """Method to get the user-entered measured value from the DMM
           entry box for point 2 and apply it to the y2 attribute if it
           is a valid floating point number.
        """
        try:
            self.y2 = float(self.pt_2_dmm_value.get())
            if self.y2 == 0.0:
                error_msg = """
ERROR: A non-zero value must be entered
for the DMM measured Point 2 value"""
                tkmsg.showerror(message=error_msg)
                return RC_FAILURE
            if event is None:
                log_str = ("{} cal point 2 (uncal, dmm): {}, {:.6f}"
                           .format(self.cal_type, self.x2, self.y2))
                self.master.ivs2.logger.log(log_str)
        except ValueError:
            error_msg = """
ERROR: A numerical value must be entered
for the DMM measured Point 2 value"""
            tkmsg.showerror(message=error_msg)
            return RC_FAILURE
        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def calibrate(self, event=None):
        """Method to calculate the slope and intercept based on the
           uncalibrated and measured values of point 1 and point 2 and
           to update their values in the entry boxes.
        """
        # pylint: disable=unused-argument

        # Check that both points have been measured by the hardware
        if self.x1 == "Unknown" or self.x2 == "Unknown":
            error_msg = """
ERROR: Cannot calibrate until both
point 1 and point 2 have been measured"""
            tkmsg.showerror(message=error_msg)
            return

        # Check that same uncalibrated value was not measured for both
        # points. This is an error because it would cause a
        # divide-by-zero exception.
        if self.x1 == self.x2:
            error_msg = """
ERROR: Point 1 and point 2 may not
have the same uncalibrated value"""
            tkmsg.showerror(message=error_msg)
            return

        # Apply the DMM measured values
        rc = self.apply_pt_1_dmm_value(None)
        if rc != RC_SUCCESS:
            return
        rc = self.apply_pt_2_dmm_value(None)
        if rc != RC_SUCCESS:
            return

        # Check that the DMM-measured values are not the same
        if self.y1 == self.y2:
            error_msg = """
ERROR: Point 1 and point 2 may not
have the same measured value"""
            tkmsg.showerror(message=error_msg)
            return

        # Check that the DMM-measured values are at least 3:1
        # one way or the other. This is a warning condition,
        # not an error.
        if ((self.y1 < self.y2 and self.y2 / self.y1 < 3) or
                (self.y2 < self.y1 and self.y1 / self.y2 < 3)):
            warning_msg = """
WARNING: There should be at least a
3:1 ratio between the two points for
good results"""
            tkmsg.showwarning(message=warning_msg)

        # Calculate slope (m) and intercept (b)
        self.m = (self.y2 - self.y1)/(self.x2 - self.x1)
        self.b = self.y1 - (self.m * self.x1)

        # Update values in entries
        self.update_slope()
        self.update_intercept()

    # -------------------------------------------------------------------------
    def apply_slope(self, event=None):
        """Method to get the maunually entered value from the slope
           entry box
        """
        # pylint: disable=unused-argument
        try:
            m = float(self.slope.get())
            if m != self.m:
                msg_str = """
Are you sure you want to manually set the slope value?"""
                answer_is_yes = tkmsg_askyesno(self.master,
                                               "Set slope?", msg_str,
                                               default=tkmsg.NO)
                if answer_is_yes:
                    self.m = m
                else:
                    return RC_FAILURE
        except ValueError:
            error_msg = """
ERROR: A numerical value must be entered
for the slope"""
            tkmsg.showerror(message=error_msg)
            return RC_FAILURE
        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def update_slope(self):
        """Method to update the value in the slope entry box
        """
        self.slope.set("{}".format(round(self.m, 6)))
        # Check that slope is between 0.85 and 1.15
        if self.m < 0.85 or self.m > 1.15:
            self.slope_warning["text"] = "  ** WARNING **"
            warning_msg = """
WARNING: Slope {}
doesn't look right. It should be between
0.85 and 1.15 (and that is being generous)""".format(round(self.m, 6))
            tkmsg.showwarning(message=warning_msg)
        else:
            self.slope_warning["text"] = ""

    # -------------------------------------------------------------------------
    def apply_intercept(self, event=None):
        """Method to get the maunually entered value from the
           intercept entry box
        """
        # pylint: disable=unused-argument
        try:
            b = float(self.intercept.get())
            if b != self.b:
                msg_str = """
Are you sure you want to manually set the intercept value?"""
                answer_is_yes = tkmsg_askyesno(self.master,
                                               "Set intercept?", msg_str,
                                               default=tkmsg.NO)
                if answer_is_yes:
                    self.b = b
                else:
                    return RC_FAILURE
        except ValueError:
            error_msg = """
ERROR: A numerical value must be entered
for the intercept"""
            tkmsg.showerror(message=error_msg)
            return RC_FAILURE
        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def update_intercept(self):
        """Method to update the value in the intercept entry box
        """
        self.intercept.set("{}".format(round(self.b, 6)))
        # Check that intercept is between -0.5 and 0.5
        if self.b < -0.5 or self.b > 0.5:
            self.intercept_warning["text"] = "  ** WARNING **"
            warning_msg = """
WARNING: Intercept {}
doesn't look right. It should be between
-0.5 and +0.5""".format(round(self.b, 6))
            tkmsg.showwarning(message=warning_msg)
        else:
            self.intercept_warning["text"] = ""

    # -------------------------------------------------------------------------
    def get_test_uncal_value(self):
        """Method to get the uncalibrated test value from the hardware and
           update the label.
        """
        self.test_dmm_value.set("")
        rc = self.get_uncal_value()
        if rc == RC_SUCCESS:
            self.update_test_cal_value()

    # -------------------------------------------------------------------------
    def update_test_cal_value(self):
        """Method to update the value in the calibrated value label
        """
        if self.type_is_current():
            uncal_units_str = self.master.ivs2.get_adv_current_cal_amps()
        else:
            uncal_units_str = self.master.ivs2.get_adv_voltage_cal_volts()
        try:
            uncal_units = float(uncal_units_str)
            self.test_cal_units = self.m * uncal_units + self.b
            val_str = "{:0.3f} {}".format(self.test_cal_units,
                                          self.unit_abbrev)
        except ValueError:
            val_str = uncal_units_str
        label_str = "Calibrated value:  {}".format(val_str)
        self.test_cal_value.set(label_str)

    # -------------------------------------------------------------------------
    def apply_test_dmm_value(self, event=None):
        """Method to get the user-entered measured value from the test
           DMM entry box and apply it to the test_dmm_units attribute
           and update the test error label if it is a valid floating
           point number
        """
        # pylint: disable=unused-argument
        if self.test_cal_units == "Unknown":
            error_msg = """
ERROR: The test must be run before
entering a DMM measured value"""
            tkmsg.showerror(message=error_msg)
            return RC_FAILURE
        if self.type_is_current():
            uncal_units_str = self.master.ivs2.get_adv_current_cal_amps()
        else:
            uncal_units_str = self.master.ivs2.get_adv_voltage_cal_volts()
        try:
            self.test_dmm_units = float(self.test_dmm_value.get())
            self.update_test_err_val()
            uncal_units = float(uncal_units_str)
            log_str = ("{} cal test (uncal, dmm): {}, {:.6f}"
                       .format(self.cal_type, uncal_units,
                               self.test_dmm_units))
            self.master.ivs2.logger.log(log_str)
        except ValueError:
            error_msg = """
ERROR: A numerical value must be entered
for the DMM measured test value"""
            tkmsg.showerror(message=error_msg)
            return RC_FAILURE
        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def update_test_err_val(self):
        """Method to update the values in the test error label
        """
        try:
            test_cal_milliunits = round(self.test_cal_units, 3) * 1000
            test_dmm_milliunits = round(self.test_dmm_units, 3) * 1000
            test_err_milliunits = test_cal_milliunits - test_dmm_milliunits
            err_sign = ""
            if test_err_milliunits > 0:
                err_sign = "+"
            if test_dmm_milliunits != 0:
                test_err_pct = ((test_cal_milliunits /
                                 test_dmm_milliunits) - 1) * 100
                label_str = ("Error:  {}{} m{}  ({}{} %)"
                             .format(err_sign, int(test_err_milliunits),
                                     self.unit_abbrev,
                                     err_sign, round(test_err_pct, 3)))
            else:
                label_str = ("Error:  {}{} m{}  (infinite %)"
                             .format(err_sign, int(test_err_milliunits),
                                     self.unit_abbrev))
        except TypeError:
            label_str = "Error:  Unknown"
        self.test_err.set(label_str)

    # -------------------------------------------------------------------------
    def validate(self):
        """Method to override validate() method of parent to sanity check the
           calibration values.
        """
        if self.m < 0.85 or self.m > 1.15:
            error_msg = """
ERROR: Slope {} is not between
0.85 and 1.15. Cannot commit.""".format(round(self.m, 6))
            tkmsg.showerror(message=error_msg)
            return False
        if self.b < -0.5 or self.b > 0.5:
            error_msg = """
ERROR: Intercept {} is not between
-0.5 and +0.5. Cannot commit.""".format(round(self.b, 6))
            tkmsg.showerror(message=error_msg)
            return False
        return True

    # -------------------------------------------------------------------------
    def apply(self):
        """Method to override apply() method of parent to update the
           calibration values
        """
        if self.type_is_current():
            self.master.ivs2.i_cal = self.m
            self.master.config.cfg_set("Calibration", "current", self.m)
            self.master.ivs2.i_cal_b = self.b
            self.master.config.cfg_set("Calibration", "current intercept",
                                       self.b)
        else:
            self.master.ivs2.v_cal = self.m
            self.master.config.cfg_set("Calibration", "voltage", self.m)
            self.master.ivs2.v_cal_b = self.b
            self.master.config.cfg_set("Calibration", "voltage intercept",
                                       self.b)

        # Update values in EEPROM
        self.master.menu_bar.update_values_in_eeprom()


# Advanced current calibration dialog
#
class AdvCurrentCalDialog(AdvCalDialog):
    """Class that is extended from the AdvCalDialog class and is used for
       the advanced current calibration dialog
    """
    # Initializer
    def __init__(self, master=None):
        AdvCalDialog.__init__(self, master=master, cal_type="Current")


# Advanced voltage calibration dialog
#
class AdvVoltageCalDialog(AdvCalDialog):
    """Class that is extended from the AdvCalDialog class and is used for
       the advanced voltage calibration dialog
    """
    # Initializer
    def __init__(self, master=None):
        AdvCalDialog.__init__(self, master=master, cal_type="Voltage")


# Resistor values dialog class
#
class ResistorValuesDialog(Dialog):
    """Class that is extended from the generic Dialog class and is used for
       the Resistor Values dialog
    """
    # Initializer
    def __init__(self, master=None):
        self.master = master
        self.r1_str = tk.StringVar()
        self.r2_str = tk.StringVar()
        self.rf_str = tk.StringVar()
        self.rg_str = tk.StringVar()
        self.shunt_str = tk.StringVar()
        title = "{} Resistor Values".format(APP_NAME)
        Dialog.__init__(self, master=master, title=title)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Method to create the dialog's body frame (overrides the parent class
           method)
        """
        # pylint: disable=too-many-locals
        frame = ttk.Frame(master)

        # Add label and entry box to select R1 resistance
        r1_label = ttk.Label(master=frame, text="R1 (ohms):")
        r1_entry = ttk.Entry(master=frame,
                             width=8,
                             textvariable=self.r1_str)
        r1_ohms = self.master.config.cfg.getfloat("Calibration", "r1 ohms")
        self.r1_str.set(r1_ohms)

        # Add label and entry box to select R2 resistance
        r2_label = ttk.Label(master=frame, text="R2 (ohms):")
        r2_entry = ttk.Entry(master=frame,
                             width=8,
                             textvariable=self.r2_str)
        r2_ohms = self.master.config.cfg.getfloat("Calibration", "r2 ohms")
        self.r2_str.set(r2_ohms)

        # Add label and entry box to select RF resistance
        rf_label = ttk.Label(master=frame, text="RF (ohms):")
        rf_entry = ttk.Entry(master=frame,
                             width=8,
                             textvariable=self.rf_str)
        rf_ohms = self.master.config.cfg.getfloat("Calibration", "rf ohms")
        self.rf_str.set(rf_ohms)

        # Add label and entry box to select RG resistance
        rg_label = ttk.Label(master=frame, text="RG (ohms):")
        rg_entry = ttk.Entry(master=frame,
                             width=8,
                             textvariable=self.rg_str)
        rg_ohms = self.master.config.cfg.getfloat("Calibration", "rg ohms")
        self.rg_str.set(rg_ohms)

        # Add label and entry box to select Shunt resistance
        shunt_label = ttk.Label(master=frame, text="Shunt (microohms):")
        shunt_entry = ttk.Entry(master=frame,
                                width=8,
                                textvariable=self.shunt_str)
        shunt_max_volts = self.master.config.cfg.getfloat("Calibration",
                                                          "shunt max volts")
        shunt_uohms = ((shunt_max_volts /
                        self.master.ivs2.amm_shunt_max_amps) * 1000000.0)
        self.shunt_str.set(shunt_uohms)

        # Add Restore Defaults button in its own container box
        restore_box = ttk.Frame(master=frame, padding=10)
        restore = ttk.Button(restore_box,
                             text="Restore Defaults",
                             command=self.restore_defaults)

        # Layout
        pady = 8
        frame.grid(column=0, row=0, sticky=W, columnspan=2)
        row = 0
        r1_label.grid(column=0, row=row, sticky=W, pady=pady)
        r1_entry.grid(column=1, row=row, pady=pady)
        row = 1
        r2_label.grid(column=0, row=row, sticky=W, pady=pady)
        r2_entry.grid(column=1, row=row, pady=pady)
        row = 2
        rf_label.grid(column=0, row=row, sticky=W, pady=pady)
        rf_entry.grid(column=1, row=row, pady=pady)
        row = 3
        rg_label.grid(column=0, row=row, sticky=W, pady=pady)
        rg_entry.grid(column=1, row=row, pady=pady)
        row = 4
        shunt_label.grid(column=0, row=row, sticky=W, pady=pady)
        shunt_entry.grid(column=1, row=row, pady=pady)
        row = 5
        restore_box.grid(column=2, row=row, sticky=W, pady=pady,
                         columnspan=2)
        restore.grid(column=0, row=0, sticky=W)
        frame.pack()

    # -------------------------------------------------------------------------
    def restore_defaults(self, event=None):
        """Method to restore resistor values to defaults"""
        # pylint: disable=unused-argument
        self.r1_str.set(str(R1_DEFAULT))
        self.r2_str.set(str(R2_DEFAULT))
        self.rf_str.set(str(RF_DEFAULT))
        self.rg_str.set(str(RG_DEFAULT))
        self.shunt_str.set(str(SHUNT_DEFAULT))

    # -------------------------------------------------------------------------
    def snapshot(self):
        """Method that overrides snapshot() method of parent to capture original
           configuration and property values
        """
        # Snapshot config
        self.master.config.get_snapshot()

        # Snapshot properties
        self.snapshot_values["vdiv_r1"] = self.master.ivs2.vdiv_r1
        self.snapshot_values["vdiv_r2"] = self.master.ivs2.vdiv_r2
        self.snapshot_values["amm_op_amp_rf"] = self.master.ivs2.amm_op_amp_rf
        self.snapshot_values["amm_op_amp_rg"] = self.master.ivs2.amm_op_amp_rg
        amm_shunt_max_volts = self.master.ivs2.amm_shunt_max_volts
        self.snapshot_values["amm_shunt_max_volts"] = amm_shunt_max_volts

    # -------------------------------------------------------------------------
    def validate(self):
        """Method that overrides validate() method of parent to check for legal
           values"""
        err_str = "ERROR:"
        try:
            r1_ohms = float(self.r1_str.get())
            r2_ohms = float(self.r2_str.get())
            rf_ohms = float(self.rf_str.get())
            rg_ohms = float(self.rg_str.get())
            shunt_uohms = float(self.shunt_str.get())
        except ValueError:
            err_str += "\n  All fields must be floating point"
        else:
            if r1_ohms < 0.0:
                err_str += "\n  R1 value must be zero or positive"
            if r2_ohms <= 0.0:
                err_str += "\n  R2 value must be positive"
            if rf_ohms < 0.0:
                err_str += "\n  RF value must be zero or positive"
            if rg_ohms <= 0.0:
                err_str += "\n  RG value must be positive"
            if shunt_uohms <= 1.0:
                err_str += "\n  Shunt value must be >1 (unit is microohms)"
        if len(err_str) > len("ERROR:"):
            self.show_resistor_error_dialog(err_str)
            return False
        return True

    # -------------------------------------------------------------------------
    def show_resistor_error_dialog(self, err_str):
        """Method to display an error dialog for bad resistor values"""
        tkmsg_showerror(self.master, message=err_str)

    # -------------------------------------------------------------------------
    def revert(self):
        """Method that overrides revert() method of parent to apply original
           values to properties and the config
        """
        # Restore config
        self.master.config.save_snapshot()
        self.master.config.get()

        # Restore properties
        self.master.ivs2.vdiv_r1 = self.snapshot_values["vdiv_r1"]
        self.master.ivs2.vdiv_r2 = self.snapshot_values["vdiv_r2"]
        self.master.ivs2.amm_op_amp_rf = self.snapshot_values["amm_op_amp_rf"]
        self.master.ivs2.amm_op_amp_rg = self.snapshot_values["amm_op_amp_rg"]
        amm_shunt_max_volts = self.snapshot_values["amm_shunt_max_volts"]
        self.master.ivs2.amm_shunt_max_volts = amm_shunt_max_volts

    # -------------------------------------------------------------------------
    def apply(self):
        """Method that overrides apply() method of parent to apply new values to
           properties and the config
        """
        resistance_opt_changed = False
        section = "Calibration"
        option = "r1 ohms"
        r1_ohms = float(self.r1_str.get())
        if r1_ohms != self.master.config.cfg.getfloat(section, option):
            self.master.config.cfg_set(section, option, r1_ohms)
            args = (section, option, CFG_FLOAT, self.master.ivs2.vdiv_r1)
            self.master.ivs2.vdiv_r1 = self.master.config.apply_one(*args)
            resistance_opt_changed = True
        option = "r2 ohms"
        r2_ohms = float(self.r2_str.get())
        if r2_ohms != self.master.config.cfg.getfloat(section, option):
            self.master.config.cfg_set(section, option, r2_ohms)
            args = (section, option, CFG_FLOAT, self.master.ivs2.vdiv_r2)
            self.master.ivs2.vdiv_r2 = self.master.config.apply_one(*args)
            resistance_opt_changed = True
        option = "rf ohms"
        rf_ohms = float(self.rf_str.get())
        if rf_ohms != self.master.config.cfg.getfloat(section, option):
            self.master.config.cfg_set(section, option, rf_ohms)
            args = (section, option, CFG_FLOAT,
                    self.master.ivs2.amm_op_amp_rf)
            val = self.master.config.apply_one(*args)
            self.master.ivs2.amm_op_amp_rf = val
            resistance_opt_changed = True
        option = "rg ohms"
        rg_ohms = float(self.rg_str.get())
        if rg_ohms != self.master.config.cfg.getfloat(section, option):
            self.master.config.cfg_set(section, option, rg_ohms)
            args = (section, option, CFG_FLOAT,
                    self.master.ivs2.amm_op_amp_rg)
            val = self.master.config.apply_one(*args)
            self.master.ivs2.amm_op_amp_rg = val
            resistance_opt_changed = True
        option = "shunt max volts"
        shunt_uohms = float(self.shunt_str.get())
        shunt_ohms = shunt_uohms / 1000000.0
        shunt_max_volts = self.master.ivs2.amm_shunt_max_amps * shunt_ohms
        if shunt_max_volts != self.master.config.cfg.getfloat(section, option):
            self.master.config.cfg_set(section, option, shunt_max_volts)
            args = (section, option, CFG_FLOAT,
                    self.master.ivs2.amm_shunt_max_volts)
            val = self.master.config.apply_one(*args)
            self.master.ivs2.amm_shunt_max_volts = val
            resistance_opt_changed = True

        # Update values in EEPROM (saves the config) if anything changed
        if resistance_opt_changed:
            self.master.menu_bar.update_values_in_eeprom()


# Bias battery dialog class
#
class BiasBatteryDialog(Dialog):
    """Class that is extended from the generic Dialog class and is used for
       the Bias Battery calibration dialog
    """
    # Initializer
    def __init__(self, master=None):
        self.master = master
        title = "{} Bias Battery".format(APP_NAME)
        self.ready_to_calibrate = False
        self.curve_looks_ok = False
        self.reestablish_arduino_comm_reqd = False
        self.bias_batt_csv_file = None
        self.dyn_cal_enable = tk.StringVar()
        Dialog.__init__(self, master=master, title=title)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Method to create the dialog's body frame (overrides the parent class
           method)
        """
        frame = ttk.Frame(master)

        desc_text = """
This calibration is used only for the cell version of IV Swinger 2
which sometimes requires a bias battery in series with the PV cell.

NOTE: BEFORE performing this calibration, NORMAL Current and Voltage
calibrations must be performed with the bias battery and PV cell in
series: battery (-) connected to bottom black binding post, battery (+)
connected to PV cell (-), PV cell (+) connected to lower red binding
post.

To perform a manual bias battery calibration:

  1. Connect the bias battery (-) to the bottom black binding post
  2. Connect the bias battery (+) to the top red binding post
  3. Click on the "Calibrate" button below.

After performing a manual calibration, you should enable dynamic bias
battery calibration below. When enabled, a bias battery calibration is
performed immediately before EVERY curve is swung."""

        # Add label with description text
        desc_label = ttk.Label(master=frame, text=desc_text)

        # Add Calibrate button in its own container box
        calibrate_button_box = ttk.Frame(master=frame, padding=10)
        calibrate_button = ttk.Button(calibrate_button_box,
                                      text="Calibrate",
                                      command=self.calibrate_battery_bias)
        # Add radio buttons to choose whether to enable dynamic bias
        # battery calibration
        pad = " " * 25
        title = "Dynamic calibration"
        dyn_cal_enable_label = ttk.Label(master=calibrate_button_box,
                                         text="{}{}".format(pad, title))
        dyn_cal_enable_off_rb = ttk.Radiobutton(master=calibrate_button_box,
                                                text="Off",
                                                variable=self.dyn_cal_enable,
                                                value="Off")
        dyn_cal_enable_on_rb = ttk.Radiobutton(master=calibrate_button_box,
                                               text="On",
                                               variable=self.dyn_cal_enable,
                                               value="On")
        self.dyn_cal_enable.set("Off")
        if self.master.config.cfg.getboolean("Calibration",
                                             "dynamic bias calibration"):
            self.dyn_cal_enable.set("On")

        # Layout
        frame.grid(column=0, row=0, sticky=W, columnspan=2)
        row = 0
        desc_label.grid(column=0, row=row, sticky=W)
        row = 1
        calibrate_button_box.grid(column=0, row=row, sticky=(S, W), pady=4)
        calibrate_button.grid(column=0, row=0, sticky=W)
        dyn_cal_enable_label.grid(column=1, row=0, sticky=W)
        dyn_cal_enable_off_rb.grid(column=2, row=0, sticky=W)
        dyn_cal_enable_on_rb.grid(column=3, row=0, sticky=W)
        frame.pack()

    # -------------------------------------------------------------------------
    def revert(self):
        """Override revert() method of parent to restore the Arduino
           configuration
        """
        # Restart Arduino if calibration was performed (to restore the
        # isc_stable_adc value, et al)
        if self.reestablish_arduino_comm_reqd:
            self.master.reestablish_arduino_comm()

    # -------------------------------------------------------------------------
    def apply(self):
        """Method to override apply() method of parent to copy the new bias
           battery CSV file to the parent directory
        """
        # Propagate the dynamic calibration setting to the IVS2 property
        # and config if it has changed
        dyn_bias_cal = (self.dyn_cal_enable.get() == "On")
        if (dyn_bias_cal and
                not self.master.ivs2.arduino_sketch_supports_dynamic_config):
            err_str = ("ERROR: The Arduino sketch does not support dynamic "
                       "bias calibration. You must update it to use this "
                       "feature.")
            tkmsg_showerror(self.master, message=err_str)
        elif dyn_bias_cal != self.master.ivs2.dyn_bias_cal:
            self.master.ivs2.dyn_bias_cal = dyn_bias_cal
            # Update and save config
            self.master.config.cfg_set("Calibration",
                                       "dynamic bias calibration",
                                       dyn_bias_cal)
            self.master.save_config()

        # Silently return if calibration was not performed
        if self.bias_batt_csv_file is None:
            return

        # Remove any previous bias battery calibration CSV
        # files from parent directory
        self.master.ivs2.remove_prev_bias_battery_csv()

        # Copy calibration CSV file to parent directory
        self.master.ivs2.copy_file_to_parent(self.bias_batt_csv_file)

        # Restart Arduino if calibration was performed (to restore the
        # isc_stable_adc value, et al)
        if self.reestablish_arduino_comm_reqd:
            self.master.reestablish_arduino_comm()

    # -------------------------------------------------------------------------
    def calibrate_battery_bias(self):
        """Method to swing an IV curve of the bias battery and generate a CSV
           file with the corrected ADC values
        """
        if not self.master.ivs2.arduino_ready:
            err_str = ("ERROR: The IV Swinger 2 is not connected.")
            tkmsg_showerror(self.master, message=err_str)
            return
        if not self.ready_to_calibrate:
            title_str = "Ready to calibrate bias battery?"
            msg_str = """
Is the bias battery connected to the IV
Swinger 2 bottom black and top red
binding posts WITHOUT THE PV CELL in
series?  Click YES to perform the
calibration, NO to cancel."""
            self.ready_to_calibrate = tkmsg_askyesno(self.master,
                                                     title_str,
                                                     msg_str,
                                                     default=tkmsg.YES)
        if self.ready_to_calibrate:
            if not self.master.ivs2.arduino_sketch_supports_dynamic_config:
                self.reestablish_arduino_comm_reqd = True
            rc = self.master.ivs2.swing_battery_calibration_curve()
            # Restore config file
            self.master.props.suppress_cfg_file_copy = True
            self.master.save_config()
            if rc == RC_SUCCESS:
                # Display curve
                self.master.display_img(self.master.ivs2.current_img)
                if not self.curve_looks_ok:
                    # Ask user if curve looks OK
                    title_str = "Good battery curve?"
                    msg_str = """
Click YES if ALL of the following are true of
the displayed curve:

   - The Voc point is close to the rated
     voltage of the battery

   - The curve is nearly a straight line
     between MPP and Voc

   - The curve crosses the maximum
     expected Isc of the PV cell at a
     voltage > 1.0V
"""
                    self.curve_looks_ok = tkmsg_askyesno(self.master,
                                                         title_str,
                                                         msg_str,
                                                         default=tkmsg.YES)
                if self.curve_looks_ok:
                    # Generate bias battery ADC CSV file
                    f = self.master.ivs2.gen_bias_batt_adc_csv()
                    self.bias_batt_csv_file = f

                # Clean up
                output_dir = self.master.ivs2.hdd_output_dir
                self.master.ivs2.clean_up_files(output_dir)
            else:
                err_str = ("ERROR: Failed to swing curve for bias battery")
                tkmsg_showerror(self.master, message=err_str)
                self.master.show_error_dialog(rc)
                # Clean up
                output_dir = self.master.ivs2.hdd_output_dir
                self.master.ivs2.clean_up_after_failure(output_dir)
                return


# Preferences dialog class
#
class PreferencesDialog(Dialog):
    """Class that is extended from the generic Dialog class and is used for
       the Preferences dialog
    """
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods

    # Initializer
    def __init__(self, master=None):
        self.master = master
        self.restore_looping = tk.StringVar()
        self.loop_stop_on_err = tk.StringVar()
        self.fancy_labels = tk.StringVar()
        self.interpolation_type = tk.StringVar()
        self.font_scale = tk.StringVar()
        self.line_scale = tk.StringVar()
        self.point_scale = tk.StringVar()
        self.correct_adc = tk.StringVar()
        self.fix_isc = tk.StringVar()
        self.fix_voc = tk.StringVar()
        self.comb_dupv_pts = tk.StringVar()
        self.reduce_noise = tk.StringVar()
        self.fix_overshoot = tk.StringVar()
        self.battery_bias = tk.StringVar()
        self.series_res_comp_milliohms_str = tk.StringVar()
        self.spi_clk_str = tk.StringVar()
        self.relay_active_high_str = tk.StringVar()
        self.max_iv_points_str = tk.StringVar()
        self.min_isc_adc_str = tk.StringVar()
        self.max_isc_poll_str = tk.StringVar()
        self.isc_stable_adc_str = tk.StringVar()
        self.max_discards_str = tk.StringVar()
        self.aspect_height_str = tk.StringVar()
        self.aspect_width_str = tk.StringVar()
        self.plot_props = PlottingProps(ivs2=master.ivs2)
        title = "{} Preferences".format(APP_NAME)
        Dialog.__init__(self, master=master, title=title)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Method to create body, which is a Notebook (tabbed frames)
        """
        self.nb = ttk.Notebook(master)
        self.plotting_tab = ttk.Frame(self.nb)
        self.looping_tab = ttk.Frame(self.nb)
        self.arduino_tab = ttk.Frame(self.nb)
        self.nb.add(self.plotting_tab, text="Plotting")
        self.nb.add(self.looping_tab, text="Looping")
        self.nb.add(self.arduino_tab, text="Arduino")
        self.populate_plotting_tab()
        self.populate_looping_tab()
        self.populate_arduino_tab()
        self.nb.pack()

    # -------------------------------------------------------------------------
    def populate_plotting_tab(self):
        """Method to add widgets to the Plotting tab"""
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-statements
        section = "Plotting"
        self.font_scale.set(self.master.config.cfg.getfloat(section,
                                                            "font scale"))
        self.line_scale.set(self.master.config.cfg.getfloat(section,
                                                            "line scale"))
        self.point_scale.set(self.master.config.cfg.getfloat(section,
                                                             "point scale"))
        # Add container box for widgets
        plotting_widget_box = ttk.Frame(master=self.plotting_tab, padding=20)

        # Add radio buttons to choose whether interpolation should be
        # "Straight" (linear) or "Smooth" (spline)
        line_type_label = ttk.Label(master=plotting_widget_box,
                                    text="Line type:")
        straight_rb = ttk.Radiobutton(master=plotting_widget_box,
                                      text="Straight",
                                      variable=self.interpolation_type,
                                      command=self.immediate_apply,
                                      value="Linear")
        smooth_rb = ttk.Radiobutton(master=plotting_widget_box,
                                    text="Smooth",
                                    variable=self.interpolation_type,
                                    command=self.immediate_apply,
                                    value="Spline")
        self.interpolation_type.set("Spline")
        if self.master.config.cfg.getboolean(section, "linear"):
            self.interpolation_type.set("Linear")

        # Add radio buttons to choose whether Isc, MPP, and Voc labels
        # should be plain or "fancy"
        label_style_label = ttk.Label(master=plotting_widget_box,
                                      text="Isc, MPP, Voc labels:")
        plain_rb = ttk.Radiobutton(master=plotting_widget_box,
                                   text="Plain",
                                   variable=self.fancy_labels,
                                   command=self.immediate_apply,
                                   value="Plain")
        fancy_rb = ttk.Radiobutton(master=plotting_widget_box,
                                   text="Fancy",
                                   variable=self.fancy_labels,
                                   command=self.immediate_apply,
                                   value="Fancy")
        self.fancy_labels.set("Plain")
        if self.master.config.cfg.getboolean(section, "fancy labels"):
            self.fancy_labels.set("Fancy")

        # Add scale slider and entry box for font scale. They both use
        # the same variable, so when the slider is moved, the value in
        # the entry box is changed and when the value in the entry box
        # is changed, the slider moves. This allows the user the choice
        # of whether to type in a value or to use the slider.
        font_scale_label = ttk.Label(master=plotting_widget_box,
                                     text="Font scale:")
        font_scale_slider = ttk.Scale(master=plotting_widget_box,
                                      orient=HORIZONTAL,
                                      length=200,
                                      from_=0.1,
                                      to=2.0,
                                      variable=self.font_scale,
                                      command=self.round_font_scale)
        font_scale_slider.bind("<ButtonRelease-1>", self.immediate_apply)
        font_scale_entry = ttk.Entry(master=plotting_widget_box,
                                     width=8,
                                     textvariable=self.font_scale)
        font_scale_entry.bind("<Return>", self.immediate_apply)

        # Same for line scale
        line_scale_label = ttk.Label(master=plotting_widget_box,
                                     text="Line scale:")
        line_scale_slider = ttk.Scale(master=plotting_widget_box,
                                      orient=HORIZONTAL,
                                      length=200,
                                      from_=0.0,
                                      to=5.0,
                                      variable=self.line_scale,
                                      command=self.round_line_scale)
        line_scale_slider.bind("<ButtonRelease-1>", self.immediate_apply)
        line_scale_entry = ttk.Entry(master=plotting_widget_box,
                                     width=8,
                                     textvariable=self.line_scale)
        line_scale_entry.bind("<Return>", self.immediate_apply)

        # Same for point scale
        point_scale_label = ttk.Label(master=plotting_widget_box,
                                      text="Point scale:")
        point_scale_slider = ttk.Scale(master=plotting_widget_box,
                                       orient=HORIZONTAL,
                                       length=200,
                                       from_=0.0,
                                       to=4.0,
                                       variable=self.point_scale,
                                       command=self.round_point_scale)
        point_scale_slider.bind("<ButtonRelease-1>", self.immediate_apply)
        point_scale_entry = ttk.Entry(master=plotting_widget_box,
                                      width=8,
                                      textvariable=self.point_scale)
        point_scale_entry.bind("<Return>", self.immediate_apply)

        # Add radio buttons to choose whether ADC values should be
        # corrected or not
        correct_adc_label = ttk.Label(master=plotting_widget_box,
                                      text="ADC correction:")
        correct_adc_off_rb = ttk.Radiobutton(master=plotting_widget_box,
                                             text="Off",
                                             variable=self.correct_adc,
                                             command=self.immediate_apply,
                                             value="Off")
        correct_adc_on_box = ttk.Frame(master=plotting_widget_box, padding=0)
        correct_adc_on_rb = ttk.Radiobutton(master=correct_adc_on_box,
                                            text="On",
                                            variable=self.correct_adc,
                                            command=self.immediate_apply,
                                            value="On")
        correct_adc_label2 = ttk.Label(master=correct_adc_on_box,
                                       text="   (Off overrides next 5)")
        correct_adc_on_rb.pack(side=LEFT)
        correct_adc_label2.pack(side=LEFT)
        self.correct_adc.set("Off")
        if self.master.config.cfg.getboolean(section, "correct adc"):
            self.correct_adc.set("On")

        # Add radio buttons to choose whether to apply fixes to the Isc point
        fix_isc_label = ttk.Label(master=plotting_widget_box,
                                  text="    Fix Isc point:")
        fix_isc_off_rb = ttk.Radiobutton(master=plotting_widget_box,
                                         text="Off",
                                         variable=self.fix_isc,
                                         command=self.immediate_apply,
                                         value="Off")
        fix_isc_on_rb = ttk.Radiobutton(master=plotting_widget_box,
                                        text="On",
                                        variable=self.fix_isc,
                                        command=self.immediate_apply,
                                        value="On")
        self.fix_isc.set("Off")
        if self.master.config.cfg.getboolean(section, "fix isc"):
            self.fix_isc.set("On")

        # Add radio buttons to choose whether to apply fixes to the Voc point
        fix_voc_label = ttk.Label(master=plotting_widget_box,
                                  text="    Fix Voc point:")
        fix_voc_off_rb = ttk.Radiobutton(master=plotting_widget_box,
                                         text="Off",
                                         variable=self.fix_voc,
                                         command=self.immediate_apply,
                                         value="Off")
        fix_voc_on_rb = ttk.Radiobutton(master=plotting_widget_box,
                                        text="On",
                                        variable=self.fix_voc,
                                        command=self.immediate_apply,
                                        value="On")
        self.fix_voc.set("Off")
        if self.master.config.cfg.getboolean(section, "fix voc"):
            self.fix_voc.set("On")

        # Add radio buttons to choose whether to combine consecutive
        # points with the same voltage
        comb_dupv_pts_label = ttk.Label(master=plotting_widget_box,
                                        text="    Combine =V points:")
        comb_dupv_pts_off_rb = ttk.Radiobutton(master=plotting_widget_box,
                                               text="Off",
                                               variable=self.comb_dupv_pts,
                                               command=self.immediate_apply,
                                               value="Off")
        comb_dupv_pts_on_rb = ttk.Radiobutton(master=plotting_widget_box,
                                              text="On",
                                              variable=self.comb_dupv_pts,
                                              command=self.immediate_apply,
                                              value="On")
        self.comb_dupv_pts.set("Off")
        if self.master.config.cfg.getboolean(section, "combine dupv points"):
            self.comb_dupv_pts.set("On")

        # Add radio buttons to choose whether noise reduction algorithm
        # should be applied or not
        reduce_noise_label = ttk.Label(master=plotting_widget_box,
                                       text="    Reduce noise:")
        reduce_noise_off_rb = ttk.Radiobutton(master=plotting_widget_box,
                                              text="Off",
                                              variable=self.reduce_noise,
                                              command=self.immediate_apply,
                                              value="Off")
        reduce_noise_on_rb = ttk.Radiobutton(master=plotting_widget_box,
                                             text="On",
                                             variable=self.reduce_noise,
                                             command=self.immediate_apply,
                                             value="On")
        self.reduce_noise.set("Off")
        if self.master.config.cfg.getboolean(section, "reduce noise"):
            self.reduce_noise.set("On")

        # Add radio buttons to choose whether to correct for the Voc
        # overshoot
        fix_overshoot_label = ttk.Label(master=plotting_widget_box,
                                        text="    Fix overshoot:")
        fix_overshoot_off_rb = ttk.Radiobutton(master=plotting_widget_box,
                                               text="Off",
                                               variable=self.fix_overshoot,
                                               command=self.immediate_apply,
                                               value="Off")
        fix_overshoot_on_rb = ttk.Radiobutton(master=plotting_widget_box,
                                              text="On",
                                              variable=self.fix_overshoot,
                                              command=self.immediate_apply,
                                              value="On")
        self.fix_overshoot.set("Off")
        if self.master.config.cfg.getboolean(section, "fix overshoot"):
            self.fix_overshoot.set("On")

        # Add radio buttons to choose whether a battery bias should be
        # applied or not
        battery_bias_label = ttk.Label(master=plotting_widget_box,
                                       text="Battery bias:")
        battery_bias_off_rb = ttk.Radiobutton(master=plotting_widget_box,
                                              text="Off",
                                              variable=self.battery_bias,
                                              command=self.turn_off_batt_bias,
                                              value="Off")
        battery_bias_on_rb = ttk.Radiobutton(master=plotting_widget_box,
                                             text="On",
                                             variable=self.battery_bias,
                                             command=self.turn_on_batt_bias,
                                             value="On")
        self.battery_bias.set("Off")
        if self.master.config.cfg.getboolean(section, "battery bias"):
            self.battery_bias.set("On")

        # Add label and entry box to specify the series resistance
        # compensation
        label_text = "Series resistance \ncompensation:"
        series_res_comp_label = ttk.Label(master=plotting_widget_box,
                                          text=label_text)
        textvar = self.series_res_comp_milliohms_str
        series_res_comp_entry = ttk.Entry(master=plotting_widget_box,
                                          width=8,
                                          textvariable=textvar)
        series_res_comp_label2 = ttk.Label(master=plotting_widget_box,
                                           text="milliohms")
        if self.master.config.cfg.getboolean(section, "battery bias"):
            value = "bias series resistance comp"
        else:
            value = "series resistance comp"
        series_res_comp_ohms = self.master.config.cfg.getfloat(section, value)
        series_res_comp_milliohms = round(series_res_comp_ohms * 1000.0, 3)
        self.series_res_comp_milliohms_str.set(series_res_comp_milliohms)
        series_res_comp_entry.bind("<Return>", self.apply_new_series_res_comp)

        # Add Restore Defaults button in its own container box
        plotting_restore_box = ttk.Frame(master=self.plotting_tab, padding=10)
        plotting_restore = ttk.Button(plotting_restore_box,
                                      text="Restore Defaults",
                                      command=self.restore_plotting_defaults)

        # Add Help button in its own container box
        plotting_help_box = ttk.Frame(master=self.plotting_tab, padding=10)
        plotting_help = ttk.Button(plotting_help_box,
                                   text="Help", width=8,
                                   command=self.show_plotting_help)

        # Layout
        plotting_widget_box.grid(column=0, row=0, sticky=W, columnspan=2)
        pady = 8
        row = 0
        line_type_label.grid(column=0, row=row, sticky=W)
        straight_rb.grid(column=1, row=row, sticky=W)
        smooth_rb.grid(column=2, row=row, sticky=W)
        row = 1
        label_style_label.grid(column=0, row=row, sticky=W, pady=pady)
        plain_rb.grid(column=1, row=row, sticky=W, pady=pady)
        fancy_rb.grid(column=2, row=row, sticky=W, pady=pady)
        row = 2
        font_scale_label.grid(column=0, row=row, sticky=W, pady=pady)
        font_scale_entry.grid(column=1, row=row, sticky=W, pady=pady)
        font_scale_slider.grid(column=2, row=row, sticky=W, pady=pady)
        row = 3
        line_scale_label.grid(column=0, row=row, sticky=W, pady=pady)
        line_scale_entry.grid(column=1, row=row, sticky=W, pady=pady)
        line_scale_slider.grid(column=2, row=row, sticky=W, pady=pady)
        row = 4
        point_scale_label.grid(column=0, row=row, sticky=W, pady=pady)
        point_scale_entry.grid(column=1, row=row, sticky=W, pady=pady)
        point_scale_slider.grid(column=2, row=row, sticky=W, pady=pady)
        # Suppress displaying ADC correction and battery bias widgets if
        # the adc_pairs property is not populated (unless we're still at
        # the splash screen)
        if (self.master.ivs2.adc_pairs is not None or
                self.master.img_pane.splash_img_showing):
            row += 1
            correct_adc_label.grid(column=0, row=row, sticky=W, pady=pady)
            correct_adc_off_rb.grid(column=1, row=row, sticky=W, pady=pady)
            correct_adc_on_box.grid(column=2, row=row, sticky=W, pady=pady)
            row += 1
            fix_isc_label.grid(column=0, row=row, sticky=W, pady=pady)
            fix_isc_off_rb.grid(column=1, row=row, sticky=W, pady=pady)
            fix_isc_on_rb.grid(column=2, row=row, sticky=W, pady=pady)
            row += 1
            fix_voc_label.grid(column=0, row=row, sticky=W, pady=pady)
            fix_voc_off_rb.grid(column=1, row=row, sticky=W, pady=pady)
            fix_voc_on_rb.grid(column=2, row=row, sticky=W, pady=pady)
            row += 1
            comb_dupv_pts_label.grid(column=0, row=row, sticky=W, pady=pady)
            comb_dupv_pts_off_rb.grid(column=1, row=row, sticky=W, pady=pady)
            comb_dupv_pts_on_rb.grid(column=2, row=row, sticky=W, pady=pady)
            row += 1
            reduce_noise_label.grid(column=0, row=row, sticky=W, pady=pady)
            reduce_noise_off_rb.grid(column=1, row=row, sticky=W, pady=pady)
            reduce_noise_on_rb.grid(column=2, row=row, sticky=W, pady=pady)
            row += 1
            fix_overshoot_label.grid(column=0, row=row, sticky=W, pady=pady)
            fix_overshoot_off_rb.grid(column=1, row=row, sticky=W, pady=pady)
            fix_overshoot_on_rb.grid(column=2, row=row, sticky=W, pady=pady)
            row += 1
            battery_bias_label.grid(column=0, row=row, sticky=W, pady=pady)
            battery_bias_off_rb.grid(column=1, row=row, sticky=W, pady=pady)
            battery_bias_on_rb.grid(column=2, row=row, sticky=W, pady=pady)
        row += 1
        series_res_comp_label.grid(column=0, row=row, sticky=W, pady=pady)
        series_res_comp_entry.grid(column=1, row=row, sticky=W, pady=pady)
        series_res_comp_label2.grid(column=2, row=row, sticky=W, pady=pady)
        row += 1
        plotting_help_box.grid(column=0, row=row, sticky=W, pady=pady,
                               columnspan=2)
        plotting_help.grid(column=0, row=0, sticky=W)
        plotting_restore_box.grid(column=1, row=row, sticky=E)
        plotting_restore.grid(column=0, row=0, sticky=W)

    # -------------------------------------------------------------------------
    def turn_off_batt_bias(self, event=None):
        """Method to turn off battery bias mode"""
        # pylint: disable=unused-argument
        series_res_comp_ohms = self.master.ivs2.series_res_comp
        series_res_comp_milliohms = round(series_res_comp_ohms * 1000.0, 3)
        self.series_res_comp_milliohms_str.set(series_res_comp_milliohms)
        self.immediate_apply()

    # -------------------------------------------------------------------------
    def turn_on_batt_bias(self, event=None):
        """Method to turn on battery bias mode"""
        # pylint: disable=unused-argument
        series_res_comp_ohms = self.master.ivs2.bias_series_res_comp
        series_res_comp_milliohms = round(series_res_comp_ohms * 1000.0, 3)
        self.series_res_comp_milliohms_str.set(series_res_comp_milliohms)
        self.immediate_apply()

    # -------------------------------------------------------------------------
    def apply_new_series_res_comp(self, event=None):
        """Method to apply new series resistance compensation value"""
        # pylint: disable=unused-argument
        self.immediate_apply()

    # -------------------------------------------------------------------------
    def restore_plotting_defaults(self, event=None):
        """Method to restore Plotting tab values to defaults"""
        # pylint: disable=unused-argument
        self.fancy_labels.set(str(FANCY_LABELS_DEFAULT))
        self.interpolation_type.set(str(INTERPOLATION_TYPE_DEFAULT))
        self.font_scale.set(str(FONT_SCALE_DEFAULT))
        self.line_scale.set(str(LINE_SCALE_DEFAULT))
        self.point_scale.set(str(POINT_SCALE_DEFAULT))
        self.correct_adc.set(str(CORRECT_ADC_DEFAULT))
        self.fix_isc.set(str(FIX_ISC_DEFAULT))
        self.fix_voc.set(str(FIX_VOC_DEFAULT))
        self.comb_dupv_pts.set(str(COMB_DUPV_PTS_DEFAULT))
        self.reduce_noise.set(str(REDUCE_NOISE_DEFAULT))
        self.fix_overshoot.set(str(FIX_OVERSHOOT_DEFAULT))
        # NOTE: battery_bias is not restored since that is usually not
        # what the user would expect.
        if self.master.config.cfg.getboolean("Plotting", "battery bias"):
            default_ohms = BIAS_SERIES_RES_COMP_DEFAULT
        else:
            default_ohms = SERIES_RES_COMP_DEFAULT
        default_milliohms = round(default_ohms * 1000.0, 3)
        self.series_res_comp_milliohms_str.set(str(default_milliohms))
        self.immediate_apply()

    # -------------------------------------------------------------------------
    def show_plotting_help(self):
        """Method to display Plotting tab help"""
        PlottingHelpDialog(self.master)

    # -------------------------------------------------------------------------
    def populate_looping_tab(self):
        """Method to add widgets to the Looping tab"""
        # Add container box for widgets
        looping_widget_box = ttk.Frame(master=self.looping_tab, padding=20)

        # Add checkbutton to choose whether to restore looping settings
        # at startup
        restore_looping_cb_text = "Restore looping settings at startup"
        restore_looping_cb = ttk.Checkbutton(master=looping_widget_box,
                                             text=restore_looping_cb_text,
                                             variable=self.restore_looping,
                                             onvalue="Enabled",
                                             offvalue="Disabled")

        # Add checkbutton to choose whether to stop on non-fatal errors
        # while looping
        loop_stop_on_err_cb_text = "Stop on non-fatal errors when looping"
        loop_stop_on_err_cb = ttk.Checkbutton(master=looping_widget_box,
                                              text=loop_stop_on_err_cb_text,
                                              variable=self.loop_stop_on_err,
                                              onvalue="Enabled",
                                              offvalue="Disabled")

        # If the config contains a Looping section ...
        section = "Looping"
        if self.master.config.cfg.has_section(section):
            # Invoke the checkbutton if "restore values" is True
            option = "restore values"
            if self.master.config.cfg.getboolean(section, option):
                restore_looping_cb.invoke()
            # Set the stop on error checkbutton according to the value
            option = "stop on error"
            self.loop_stop_on_err.set("Enabled")
            if self.master.config.cfg.has_option(section, option):
                if not self.master.config.cfg.getboolean(section, option):
                    self.loop_stop_on_err.set("Disabled")

        # Add Help button in its own container box
        looping_help_box = ttk.Frame(master=self.looping_tab, padding=10)
        looping_help = ttk.Button(looping_help_box,
                                  text="Help", width=8,
                                  command=self.show_looping_help)

        # Layout
        pady = 8
        looping_widget_box.grid(column=0, row=0, sticky=W, columnspan=2)
        restore_looping_cb.grid(column=0, row=0, sticky=W)
        loop_stop_on_err_cb.grid(column=0, row=1, sticky=W)
        looping_help_box.grid(column=0, row=2, sticky=W,
                              pady=pady, columnspan=2)
        looping_help.grid(column=0, row=0, sticky=W)

    # -------------------------------------------------------------------------
    def show_looping_help(self):
        """Method to display Looping tab help"""
        LoopingHelpDialog(self.master)

    # -------------------------------------------------------------------------
    def populate_arduino_tab(self):
        """Method to add widgets to the Arduino tab"""
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-statements

        # Add container box for widgets
        arduino_widget_box = ttk.Frame(master=self.arduino_tab, padding=20)

        # Add label and combobox to select SPI clock frequency
        spi_clk_label = ttk.Label(master=arduino_widget_box,
                                  text="SPI clock freq:")
        spi_clk_combo = SpiClkCombo(master=arduino_widget_box,
                                    gui=self.master,
                                    textvariable=self.spi_clk_str)

        # Add label and entry box to select maximum IV points
        max_iv_label = ttk.Label(master=arduino_widget_box,
                                 text="Max IV points:")
        max_iv_entry = ttk.Entry(master=arduino_widget_box,
                                 width=8,
                                 textvariable=self.max_iv_points_str)
        label_txt = "(< {})".format(MAX_IV_POINTS_MAX + 1)
        max_iv_constraint_label = ttk.Label(master=arduino_widget_box,
                                            text=label_txt)
        max_iv_points = self.master.config.cfg.getint("Arduino",
                                                      "max iv points")
        self.max_iv_points_str.set(max_iv_points)

        # Add label and entry box to select minimum Isc ADC
        min_isc_adc_label = ttk.Label(master=arduino_widget_box,
                                      text="Min Isc ADC:")
        min_isc_adc_entry = ttk.Entry(master=arduino_widget_box,
                                      width=8,
                                      textvariable=self.min_isc_adc_str)
        label_txt = "(< {})".format(ADC_MAX + 1)
        min_isc_adc_constraint_label = ttk.Label(master=arduino_widget_box,
                                                 text=label_txt)
        min_isc_adc = self.master.config.cfg.getint("Arduino", "min isc adc")
        self.min_isc_adc_str.set(min_isc_adc)

        # Add label and entry box to select maximum Isc polling loops
        max_isc_poll_label = ttk.Label(master=arduino_widget_box,
                                       text="Max Isc poll:")
        max_isc_poll_entry = ttk.Entry(master=arduino_widget_box,
                                       width=8,
                                       textvariable=self.max_isc_poll_str)
        label_txt = "(< {})".format(ARDUINO_MAX_INT + 1)
        max_isc_poll_constraint_label = ttk.Label(master=arduino_widget_box,
                                                  text=label_txt)
        max_isc_poll = self.master.config.cfg.getint("Arduino", "max isc poll")
        self.max_isc_poll_str.set(max_isc_poll)

        # Add label and entry box to select Isc stable ADC
        isc_stable_adc_label = ttk.Label(master=arduino_widget_box,
                                         text="Isc stable ADC:")
        isc_stable_adc_entry = ttk.Entry(master=arduino_widget_box,
                                         width=8,
                                         textvariable=self.isc_stable_adc_str)
        label_txt = "(< {})".format(ADC_MAX + 1)
        isc_stable_constraint_label = ttk.Label(master=arduino_widget_box,
                                                text=label_txt)
        isc_stable_adc = self.master.config.cfg.getint("Arduino",
                                                       "isc stable adc")
        self.isc_stable_adc_str.set(isc_stable_adc)

        # Add label and entry box to select max discards
        max_discards_label = ttk.Label(master=arduino_widget_box,
                                       text="Max discards:")
        max_discards_entry = ttk.Entry(master=arduino_widget_box,
                                       width=8,
                                       textvariable=self.max_discards_str)
        label_txt = "(< {})".format(ARDUINO_MAX_INT + 1)
        max_discards_constraint_label = ttk.Label(master=arduino_widget_box,
                                                  text=label_txt)
        max_discards = self.master.config.cfg.getint("Arduino", "max discards")
        self.max_discards_str.set(max_discards)

        # Add label and entry box to select aspect height
        aspect_height_label = ttk.Label(master=arduino_widget_box,
                                        text="Aspect height:")
        aspect_height_entry = ttk.Entry(master=arduino_widget_box,
                                        width=8,
                                        textvariable=self.aspect_height_str)
        label_txt = "(< {})".format(MAX_ASPECT + 1)
        aspect_height_constraint_label = ttk.Label(master=arduino_widget_box,
                                                   text=label_txt)
        aspect_height = self.master.config.cfg.getint("Arduino",
                                                      "aspect height")
        self.aspect_height_str.set(aspect_height)

        # Add label and entry box to select aspect width
        aspect_width_label = ttk.Label(master=arduino_widget_box,
                                       text="Aspect width:")
        aspect_width_entry = ttk.Entry(master=arduino_widget_box,
                                       width=8,
                                       textvariable=self.aspect_width_str)
        label_txt = "(< {})".format(MAX_ASPECT + 1)
        aspect_width_constraint_label = ttk.Label(master=arduino_widget_box,
                                                  text=label_txt)
        aspect_width = self.master.config.cfg.getint("Arduino", "aspect width")
        self.aspect_width_str.set(aspect_width)

        # Add checkbutton to choose active-high relay
        active_high_cb = ttk.Checkbutton(master=arduino_widget_box,
                                         text="Relay is active-high",
                                         command=self.relay_active_warn,
                                         variable=self.relay_active_high_str,
                                         onvalue="Enabled",
                                         offvalue="Disabled")
        if self.master.ivs2.relay_active_high:
            self.relay_active_high_str.set("Enabled")

        # Add Restore Defaults button in its own container box
        arduino_restore_box = ttk.Frame(master=self.arduino_tab, padding=10)
        arduino_restore = ttk.Button(arduino_restore_box,
                                     text="Restore Defaults",
                                     command=self.restore_arduino_defaults)

        # Add Help button in its own container box
        arduino_help_box = ttk.Frame(master=self.arduino_tab, padding=10)
        arduino_help = ttk.Button(arduino_help_box,
                                  text="Help", width=8,
                                  command=self.show_arduino_help)

        # Layout
        pady = 8
        arduino_widget_box.grid(column=0, row=0, sticky=W, columnspan=2)
        row = 0
        spi_clk_label.grid(column=0, row=row, sticky=W)
        spi_clk_combo.grid(column=1, row=row, sticky=W)
        row = 1
        max_iv_label.grid(column=0, row=row, sticky=W, pady=pady)
        max_iv_entry.grid(column=1, row=row, pady=pady)
        max_iv_constraint_label.grid(column=2, row=row, sticky=W,
                                     pady=pady)
        row = 2
        min_isc_adc_label.grid(column=0, row=row, sticky=W, pady=pady)
        min_isc_adc_entry.grid(column=1, row=row, pady=pady)
        min_isc_adc_constraint_label.grid(column=2, row=row, sticky=W,
                                          pady=pady)
        row = 3
        max_isc_poll_label.grid(column=0, row=row, sticky=W, pady=pady)
        max_isc_poll_entry.grid(column=1, row=row, pady=pady)
        max_isc_poll_constraint_label.grid(column=2, row=row, sticky=W,
                                           pady=pady)
        row = 4
        isc_stable_adc_label.grid(column=0, row=row, sticky=W, pady=pady)
        isc_stable_adc_entry.grid(column=1, row=row, pady=pady)
        isc_stable_constraint_label.grid(column=2, row=row, sticky=W,
                                         pady=pady)
        row = 5
        max_discards_label.grid(column=0, row=row, sticky=W, pady=pady)
        max_discards_entry.grid(column=1, row=row, pady=pady)
        max_discards_constraint_label.grid(column=2, row=row, sticky=W,
                                           pady=pady)
        row = 6
        aspect_height_label.grid(column=0, row=row, sticky=W, pady=pady)
        aspect_height_entry.grid(column=1, row=row, pady=pady)
        aspect_height_constraint_label.grid(column=2, row=row, sticky=W,
                                            pady=pady)
        row = 7
        aspect_width_label.grid(column=0, row=row, sticky=W, pady=pady)
        aspect_width_entry.grid(column=1, row=row, pady=pady)
        aspect_width_constraint_label.grid(column=2, row=row, sticky=W,
                                           pady=pady)
        row = 8
        active_high_cb.grid(column=0, row=row, sticky=W, pady=pady)
        row = 9
        arduino_help_box.grid(column=0, row=row, sticky=W, pady=pady,
                              columnspan=2)
        arduino_help.grid(column=0, row=0, sticky=W)
        arduino_restore_box.grid(column=2, row=row, sticky=W, pady=pady,
                                 columnspan=2)
        arduino_restore.grid(column=0, row=0, sticky=W)

    # -------------------------------------------------------------------------
    def restore_arduino_defaults(self, event=None):
        """Method to restore Arduino tab values to defaults"""
        # pylint: disable=unused-argument
        self.spi_clk_str.set(str(SPI_COMBO_VALS[SPI_CLK_DEFAULT]))
        self.max_iv_points_str.set(str(MAX_IV_POINTS_DEFAULT))
        self.min_isc_adc_str.set(str(MIN_ISC_ADC_DEFAULT))
        self.max_isc_poll_str.set(str(MAX_ISC_POLL_DEFAULT))
        self.isc_stable_adc_str.set(str(ISC_STABLE_DEFAULT))
        self.max_discards_str.set(str(MAX_DISCARDS_DEFAULT))
        self.aspect_height_str.set(str(ASPECT_HEIGHT_DEFAULT))
        self.aspect_width_str.set(str(ASPECT_WIDTH_DEFAULT))
        # NOTE: relay_active_high is not restored

    # -------------------------------------------------------------------------
    def relay_active_warn(self):
        """Method to display a warning dialog when the relay active high
           checkbutton value is changed. Display an error dialog if the
           Arduino sketch is downlevel
        """
        if not self.master.ivs2.arduino_ready:
            error_str = """
ERROR: Arduino is not connected
or not ready. Cannot change this
value now.
"""
            self.relay_active_high_str.set("Disabled")
            if self.master.ivs2.relay_active_high:
                self.relay_active_high_str.set("Enabled")
            tkmsg_showerror(self.master, message=error_str)
        elif self.master.ivs2.arduino_sketch_supports_active_high_relay:
            warning_str = """
WARNING: Changing the "Relay is
active-high" value WILL prevent
the IV Swinger 2 from tracing IV
curves if it is changed to the
wrong value! This box should be
unchecked unless you KNOW that
this IV Swinger 2 was built with
a relay that has an active-high
trigger pin. It should NEVER be
checked for an IV Swinger 2 that
uses SSRs or damage could result!
"""
            tkmsg_showwarning(self.master, message=warning_str)
        else:  # sketch does not support
            error_str = """
ERROR: This version of the Arduino
software supports active-low relays
only. Changing this value has no
effect. Please upgrade.
"""
            self.relay_active_high_str.set("Disabled")
            tkmsg_showerror(self.master, message=error_str)

    # -------------------------------------------------------------------------
    def show_arduino_help(self):
        """Method to display Arduino tab help"""
        ArduinoHelpDialog(self.master)

    # -------------------------------------------------------------------------
    def immediate_apply(self, event=None):
        """Method to apply configuration immediately"""
        try:
            event.widget.tk_focusNext().focus()  # move focus out
        except:  # pylint: disable=bare-except
            pass
        self.update_idletasks()
        self.apply()

    # -------------------------------------------------------------------------
    def round_font_scale(self, event=None):
        """Method to emulate a resolution of 0.05 for font scale
           slider (no resolution option in ttk Scale class)
        """
        # pylint: disable=unused-argument
        new_val = round(20.0*float(self.font_scale.get()))/20.0
        self.font_scale.set(str(new_val))

    # -------------------------------------------------------------------------
    def round_line_scale(self, event=None):
        """Method to emulate a resolution of 0.05 for line scale
           slider (no resolution option in ttk Scale class)
        """
        # pylint: disable=unused-argument
        new_val = round(20.0*float(self.line_scale.get()))/20.0
        self.line_scale.set(str(new_val))

    # -------------------------------------------------------------------------
    def round_point_scale(self, event=None):
        """Method to emulate a resolution of 0.05 for point scale
           slider (no resolution option in ttk Scale class)
        """
        # pylint: disable=unused-argument
        new_val = round(20.0*float(self.point_scale.get()))/20.0
        self.point_scale.set(str(new_val))

    # -------------------------------------------------------------------------
    def snapshot(self):
        """Method to override snapshot() method of parent to capture original
           configuration and property values
        """
        # Snapshot config
        self.master.config.get_snapshot()

        # Snapshot properties
        self.snapshot_values["linear"] = self.master.ivs2.linear
        self.snapshot_values["fancy_labels"] = self.master.ivs2.fancy_labels
        self.snapshot_values["font_scale"] = self.master.ivs2.font_scale
        self.snapshot_values["line_scale"] = self.master.ivs2.line_scale
        self.snapshot_values["point_scale"] = self.master.ivs2.point_scale
        self.snapshot_values["correct_adc"] = self.master.ivs2.correct_adc
        self.snapshot_values["fix_isc"] = self.master.ivs2.fix_isc
        self.snapshot_values["fix_voc"] = self.master.ivs2.fix_voc
        self.snapshot_values["comb_dupv_pts"] = self.master.ivs2.comb_dupv_pts
        self.snapshot_values["reduce_noise"] = self.master.ivs2.reduce_noise
        self.snapshot_values["fix_overshoot"] = self.master.ivs2.fix_overshoot
        self.snapshot_values["battery_bias"] = self.master.ivs2.battery_bias
        series_res_comp = self.master.ivs2.series_res_comp
        bias_series_res_comp = self.master.ivs2.series_res_comp
        self.snapshot_values["series_res_comp"] = series_res_comp
        self.snapshot_values["bias_series_res_comp"] = bias_series_res_comp

    # -------------------------------------------------------------------------
    def validate(self):
        """Method to override validate() method of parent to check for legal
           values
        """
        # pylint: disable=too-many-branches

        # Assumption: user is only changing values on one tab
        err_str = "ERROR:"
        # ----------------------- Plotting --------------------------
        try:
            font_scale = float(self.font_scale.get())
            line_scale = float(self.line_scale.get())
            point_scale = float(self.point_scale.get())
        except ValueError:
            err_str += "\n  All fields must be floating point"
        else:
            if font_scale <= 0.0:
                err_str += "\n  Font scale value must be positive"
            if line_scale < 0.0:
                err_str += "\n  Line scale value must be zero or positive"
            if point_scale < 0.0:
                err_str += "\n  Point scale value must be zero or positive"
            if line_scale == 0.0 and point_scale == 0.0:
                err_str += "\n  Line and Point scale cannot both be zero"
        try:
            float(self.series_res_comp_milliohms_str.get())
        except ValueError:
            err_str += "\n  Series resistance Value must be floating point"
        # ------------------------ Arduino --------------------------
        try:
            max_iv_points = int(self.max_iv_points_str.get())
            min_isc_adc = int(self.min_isc_adc_str.get())
            max_isc_poll = int(self.max_isc_poll_str.get())
            isc_stable_adc = int(self.isc_stable_adc_str.get())
            max_discards = int(self.max_discards_str.get())
            aspect_height = int(self.aspect_height_str.get())
            aspect_width = int(self.aspect_width_str.get())
        except ValueError:
            err_str += "\n  All fields must be integers"
        else:
            if max_iv_points > MAX_IV_POINTS_MAX:
                err_str += ("\n  Max IV points must be no more than {}"
                            .format(MAX_IV_POINTS_MAX))
            if max_iv_points < 1:
                err_str += "\n  Max IV points must greater than 0"
            if min_isc_adc > ADC_MAX:
                err_str += ("\n  Min Isc ADC must be no more than {}"
                            .format(ADC_MAX))
            if max_isc_poll > ARDUINO_MAX_INT:
                err_str += ("\n  Max Isc poll must be no more than {}"
                            .format(ARDUINO_MAX_INT))
            if isc_stable_adc > ADC_MAX:
                err_str += ("\n  Isc stable ADC must be no more than {}"
                            .format(ADC_MAX))
            if max_discards > ARDUINO_MAX_INT:
                err_str += ("\n  Max discards must be no more than {}"
                            .format(ARDUINO_MAX_INT))
            if aspect_height > MAX_ASPECT:
                err_str += ("\n  Aspect height must be no more than {}"
                            .format(MAX_ASPECT))
            if aspect_width > MAX_ASPECT:
                err_str += ("\n  Aspect width must be no more than {}"
                            .format(MAX_ASPECT))
        if len(err_str) > len("ERROR:"):
            self.show_arduino_error_dialog(err_str)
            return False
        return True

    # -------------------------------------------------------------------------
    def show_arduino_error_dialog(self, err_str):
        """Method to display an error dialog for bad Arduino values"""
        tkmsg_showerror(self.master, message=err_str)

    # -------------------------------------------------------------------------
    def revert(self):
        """Method to override revert() method of parent to apply original
           values to properties and the config
        """
        # Restore config
        self.master.config.save_snapshot()
        self.master.config.get()

        # Restore properties
        self.master.ivs2.linear = self.snapshot_values["linear"]
        self.master.ivs2.fancy_labels = self.snapshot_values["fancy_labels"]
        self.master.ivs2.font_scale = self.snapshot_values["font_scale"]
        self.master.ivs2.line_scale = self.snapshot_values["line_scale"]
        self.master.ivs2.point_scale = self.snapshot_values["point_scale"]
        self.master.ivs2.correct_adc = self.snapshot_values["correct_adc"]
        self.master.ivs2.fix_isc = self.snapshot_values["fix_isc"]
        self.master.ivs2.fix_voc = self.snapshot_values["fix_voc"]
        self.master.ivs2.comb_dupv_pts = self.snapshot_values["comb_dupv_pts"]
        self.master.ivs2.reduce_noise = self.snapshot_values["reduce_noise"]
        self.master.ivs2.fix_overshoot = self.snapshot_values["fix_overshoot"]
        self.master.ivs2.battery_bias = self.snapshot_values["battery_bias"]
        series_res_comp = self.snapshot_values["series_res_comp"]
        bias_series_res_comp = self.snapshot_values["bias_series_res_comp"]
        self.master.ivs2.series_res_comp = series_res_comp
        self.master.ivs2.bias_series_res_comp = bias_series_res_comp

        # Redisplay image if anything changed (saves config)
        if self.plot_props.prop_vals_changed():
            reprocess_adc = self.plot_props.adc_prop_changed()
            if self.plot_props.battery_bias_prop_changed():
                self.master.unlock_axes()
            self.master.redisplay_img(reprocess_adc=reprocess_adc)
            self.plot_props.update_prop_vals()

    # -------------------------------------------------------------------------
    def apply(self):
        """Method to override apply() method of parent to apply new values to
           properties and the config
        """
        if not self.validate():
            return

        # Apply config from each tab
        self.plotting_apply()
        self.looping_apply()
        self.arduino_apply()

    # -------------------------------------------------------------------------
    def plotting_apply(self):
        """Method to apply plotting config"""
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-statements
        section = "Plotting"
        # Line type
        linear = (self.interpolation_type.get() == "Linear")
        self.master.config.cfg_set(section, "linear", linear)
        self.master.ivs2.linear = linear
        # Label type
        fancy_labels = (self.fancy_labels.get() == "Fancy")
        self.master.config.cfg_set(section, "fancy labels", fancy_labels)
        self.master.ivs2.fancy_labels = fancy_labels
        # Font scale
        font_scale = float(self.font_scale.get())
        self.master.config.cfg_set(section, "font scale", font_scale)
        self.master.ivs2.font_scale = font_scale
        # Line scale
        line_scale = float(self.line_scale.get())
        self.master.config.cfg_set(section, "line scale", line_scale)
        self.master.ivs2.line_scale = line_scale
        # Point scale
        point_scale = float(self.point_scale.get())
        self.master.config.cfg_set(section, "point scale", point_scale)
        self.master.ivs2.point_scale = point_scale
        # Correct ADC
        correct_adc = (self.correct_adc.get() == "On")
        self.master.config.cfg_set(section, "correct adc", correct_adc)
        self.master.ivs2.correct_adc = correct_adc
        # Fix Isc point
        fix_isc = (self.fix_isc.get() == "On")
        self.master.config.cfg_set(section, "fix isc", fix_isc)
        self.master.ivs2.fix_isc = fix_isc
        # Fix Voc point
        fix_voc = (self.fix_voc.get() == "On")
        self.master.config.cfg_set(section, "fix voc", fix_voc)
        self.master.ivs2.fix_voc = fix_voc
        # Combine =V points
        comb_dupv_pts = (self.comb_dupv_pts.get() == "On")
        self.master.config.cfg_set(section, "combine dupv points",
                                   comb_dupv_pts)
        self.master.ivs2.comb_dupv_pts = comb_dupv_pts
        # Reduce noise
        reduce_noise = (self.reduce_noise.get() == "On")
        self.master.config.cfg_set(section, "reduce noise", reduce_noise)
        self.master.ivs2.reduce_noise = reduce_noise
        # Fix overshoot
        fix_overshoot = (self.fix_overshoot.get() == "On")
        self.master.config.cfg_set(section, "fix overshoot", fix_overshoot)
        self.master.ivs2.fix_overshoot = fix_overshoot
        # Battery bias
        battery_bias = (self.battery_bias.get() == "On")
        self.master.config.cfg_set(section, "battery bias", battery_bias)
        self.master.ivs2.battery_bias = battery_bias
        # Series resistance compensation
        series_res_comp = (float(self.series_res_comp_milliohms_str.get()) /
                           1000.0)
        if battery_bias:
            self.master.config.cfg_set(section, "bias series resistance comp",
                                       series_res_comp)
            self.master.ivs2.bias_series_res_comp = series_res_comp
        else:
            self.master.config.cfg_set(section, "series resistance comp",
                                       series_res_comp)
            self.master.ivs2.series_res_comp = series_res_comp

        # Redisplay image if anything changed (saves config)
        if self.plot_props.prop_vals_changed():
            reprocess_adc = self.plot_props.adc_prop_changed()
            if self.plot_props.battery_bias_prop_changed():
                if self.master.results_wiz is not None:
                    # Only redisplay and update properties on change of
                    # battery bias if Wizard is active - pretty
                    # confusing otherwise
                    self.master.unlock_axes()
                    self.master.redisplay_img(reprocess_adc=reprocess_adc)
                    self.plot_props.update_prop_vals()
                else:
                    # Have to save config explicitly in that case, however
                    self.master.save_config()
            else:
                self.master.redisplay_img(reprocess_adc=reprocess_adc)
                self.plot_props.update_prop_vals()

    # -------------------------------------------------------------------------
    def looping_apply(self):
        """Method to apply looping config"""
        section = "Looping"
        if self.master.config.cfg.has_section(section):
            looping_opt_changed = False
            # Restore values
            option = "restore values"
            restore_values = (self.restore_looping.get() == "Enabled")
            if (restore_values != self.master.config.cfg.getboolean(section,
                                                                    option)):
                self.master.config.cfg_set(section, option, restore_values)
                looping_opt_changed = True
            # Stop on error
            option = "stop on error"
            stop_on_err = (self.loop_stop_on_err.get() == "Enabled")
            if self.master.config.cfg.has_option(section, option):
                if (stop_on_err != self.master.config.cfg.getboolean(section,
                                                                     option)):
                    self.master.config.cfg_set(section, option, stop_on_err)
                    self.master.props.loop_stop_on_err = stop_on_err
                    looping_opt_changed = True
            if looping_opt_changed:
                # Save config
                self.master.save_config()

    # -------------------------------------------------------------------------
    def arduino_apply(self):
        """Method to apply Arduino config"""
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements
        arduino_opt_changed = False
        section = "Arduino"
        option = "spi clock div"
        spi_clk_div = SPI_COMBO_VALS_INV[self.spi_clk_str.get()]
        if spi_clk_div != self.master.config.cfg.getint(section, option):
            self.master.config.cfg_set(section, option, spi_clk_div)
            arduino_opt_changed = True
        option = "max iv points"
        max_iv_points = int(self.max_iv_points_str.get())
        if max_iv_points != self.master.config.cfg.getint(section, option):
            self.master.config.cfg_set(section, option, max_iv_points)
            arduino_opt_changed = True
        option = "min isc adc"
        min_isc_adc = int(self.min_isc_adc_str.get())
        if min_isc_adc != self.master.config.cfg.getint(section, option):
            self.master.config.cfg_set(section, option, min_isc_adc)
            arduino_opt_changed = True
        option = "max isc poll"
        max_isc_poll = int(self.max_isc_poll_str.get())
        if max_isc_poll != self.master.config.cfg.getint(section, option):
            self.master.config.cfg_set(section, option, max_isc_poll)
            arduino_opt_changed = True
        option = "isc stable adc"
        isc_stable_adc = int(self.isc_stable_adc_str.get())
        if isc_stable_adc != self.master.config.cfg.getint(section, option):
            self.master.config.cfg_set(section, option, isc_stable_adc)
            arduino_opt_changed = True
        option = "max discards"
        max_discards = int(self.max_discards_str.get())
        if max_discards != self.master.config.cfg.getint(section, option):
            self.master.config.cfg_set(section, option, max_discards)
            arduino_opt_changed = True
        option = "aspect height"
        aspect_height = int(self.aspect_height_str.get())
        if aspect_height != self.master.config.cfg.getint(section, option):
            self.master.config.cfg_set(section, option, aspect_height)
            arduino_opt_changed = True
        option = "aspect width"
        aspect_width = int(self.aspect_width_str.get())
        if aspect_width != self.master.config.cfg.getint(section, option):
            self.master.config.cfg_set(section, option, aspect_width)
            arduino_opt_changed = True

        # The relay active high flag is different from the others. It is
        # not stored in the config, but is saved in the Arduino EEPROM.
        if self.master.ivs2.arduino_ready:
            relay_active_high = (self.relay_active_high_str.get() == "Enabled")
            if relay_active_high != self.master.ivs2.relay_active_high:
                self.master.ivs2.relay_active_high = relay_active_high
                rc = self.master.ivs2.write_relay_active_high_val_to_eeprom()
                if rc != RC_SUCCESS:
                    error_msg = """
ERROR: The relay_active_high value could not be
written to Arduino EEPROM.
"""
                    tkmsg_showerror(self.master, error_msg)

        # Apply and save the config if anything changed
        if arduino_opt_changed:
            self.master.config.apply_arduino()
            if not self.master.ivs2.arduino_sketch_supports_dynamic_config:
                # Have to reset Arduino if sketch is old
                self.master.reestablish_arduino_comm()
            self.master.save_config()


# Plotting properties class
#
class PlottingProps(object):
    """Class that holds a copy of the state of all of the properties related
       to plotting and provides a method for comparing their current
       values with the current copy.
    """
    # Initializer
    def __init__(self, ivs2):
        self.ivs2 = ivs2
        self.prop_vals = {}
        self.update_prop_vals()

    # -------------------------------------------------------------------------
    def update_prop_vals(self):
        """Method to capture current values of properties"""
        # Capture current properties
        self.prop_vals["linear"] = self.ivs2.linear
        self.prop_vals["fancy_labels"] = self.ivs2.fancy_labels
        self.prop_vals["font_scale"] = self.ivs2.font_scale
        self.prop_vals["line_scale"] = self.ivs2.line_scale
        self.prop_vals["point_scale"] = self.ivs2.point_scale
        self.prop_vals["correct_adc"] = self.ivs2.correct_adc
        self.prop_vals["fix_isc"] = self.ivs2.fix_isc
        self.prop_vals["fix_voc"] = self.ivs2.fix_voc
        self.prop_vals["comb_dupv_pts"] = self.ivs2.comb_dupv_pts
        self.prop_vals["reduce_noise"] = self.ivs2.reduce_noise
        self.prop_vals["fix_overshoot"] = self.ivs2.fix_overshoot
        self.prop_vals["battery_bias"] = self.ivs2.battery_bias
        self.prop_vals["series_res_comp"] = self.ivs2.series_res_comp
        self.prop_vals["bias_series_res_comp"] = self.ivs2.bias_series_res_comp

    # -------------------------------------------------------------------------
    def prop_vals_changed(self):
        """Method to compare current values of properties with previously
           captured values to see if anything has changed
        """
        return ((self.prop_vals["linear"] != self.ivs2.linear) or
                (self.prop_vals["fancy_labels"] != self.ivs2.fancy_labels) or
                (self.prop_vals["font_scale"] != self.ivs2.font_scale) or
                (self.prop_vals["line_scale"] != self.ivs2.line_scale) or
                (self.prop_vals["point_scale"] != self.ivs2.point_scale) or
                (self.prop_vals["correct_adc"] != self.ivs2.correct_adc) or
                (self.prop_vals["fix_isc"] != self.ivs2.fix_isc) or
                (self.prop_vals["fix_voc"] != self.ivs2.fix_voc) or
                (self.prop_vals["comb_dupv_pts"] != self.ivs2.comb_dupv_pts) or
                (self.prop_vals["reduce_noise"] != self.ivs2.reduce_noise) or
                (self.prop_vals["fix_overshoot"] != self.ivs2.fix_overshoot) or
                (self.prop_vals["battery_bias"] != self.ivs2.battery_bias) or
                (self.prop_vals["series_res_comp"] !=
                 self.ivs2.series_res_comp) or
                (self.prop_vals["bias_series_res_comp"] !=
                 self.ivs2.bias_series_res_comp))

    # -------------------------------------------------------------------------
    def adc_prop_changed(self):
        """Method to compare current values of correct_adc, fix_isc, fix_voc,
           comb_dupv_pts, reduce_noise, fix_overshoot, battery_bias,
           series_res_comp and bias_series_res_comp properties with
           previously captured values to see if any have changed
        """
        return ((self.prop_vals["correct_adc"] != self.ivs2.correct_adc) or
                (self.prop_vals["fix_isc"] != self.ivs2.fix_isc) or
                (self.prop_vals["fix_voc"] != self.ivs2.fix_voc) or
                (self.prop_vals["comb_dupv_pts"] != self.ivs2.comb_dupv_pts) or
                (self.prop_vals["reduce_noise"] != self.ivs2.reduce_noise) or
                (self.prop_vals["fix_overshoot"] != self.ivs2.fix_overshoot) or
                (self.prop_vals["battery_bias"] != self.ivs2.battery_bias) or
                (self.prop_vals["series_res_comp"] !=
                 self.ivs2.series_res_comp) or
                (self.prop_vals["bias_series_res_comp"] !=
                 self.ivs2.bias_series_res_comp))

    # -------------------------------------------------------------------------
    def battery_bias_prop_changed(self):
        """Method to compare current value of battery_bias property with
           previously captured value to see if it has changed
        """
        return self.prop_vals["battery_bias"] != self.ivs2.battery_bias


# Plotting help dialog class
#
class PlottingHelpDialog(Dialog):
    """Class that is extended from the generic Dialog class and is used for
       the Plotting Help dialog
    """
    # Initializer
    def __init__(self, master=None):
        title = "Plotting Help"
        Dialog.__init__(self, master=master, title=title,
                        has_cancel_button=False, return_ok=True,
                        parent_is_modal=True,
                        resizable=True,
                        min_height=HELP_DIALOG_MIN_HEIGHT_PIXELS,
                        max_height=HELP_DIALOG_MAX_HEIGHT_PIXELS)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Method to create the dialog body, which is just a Text widget"""
        help_text_1 = """
The configuration options on the Plotting tab control the appearance of the IV
curve plot, both on screen and in the generated PDF. Changes made to these
options are applied immediately to the current plot (if there is one), so you
can experiment and see the effect of your changes. Clicking OK will save the
new values, and they will be used from that point forward. Clicking Cancel will
revert to the previous values.  Here is a brief explanation of each option:

Line type:
  The curve interpolated between the measured points may either be "Straight"
  or "Smooth". The default is "Straight" because most IV Swinger 2 runs have so
  many points that there is virtually no advantage to a smooth curve, which
  takes longer to generate. When "Smooth" is selected, Catmull-Rom spline
  interpolation is used.

Isc, MPP, Voc labels:
  Two styles are available for the labels: "Plain" and "Fancy". Plain labels
  are text only. Fancy labels are enclosed in a box with a yellow background,
  and there are arrows indicating the point.

Font scale, Line scale, and Point scale:
  The default font size, line thickness, and size of the "dots" indicating the
  measured points are chosen automatically based on the size/resolution of the
  graph. These options allow the user to scale those up or down, according to
  taste. The sliders can be used, or the values can be typed in manually. If
  Line scale is set to 0.0, the interpolated curve is not plotted. If Point
  scale is set to 0.0, the measured points are not plotted.

ADC correction:
  By default, several "corrections" are made to the raw values read by the
  analog to digital converter (ADC) chip to correct for noise and other effects
  that affect the proper rendering of the IV curve and the calculation of the
  maximum power. If "Off" is selected, these corrections are not performed.
  Note that the values written to the ADC CSV file are the uncorrected values,
  regardless of this setting. Also note that the current and voltage
  calibration settings are used regardless of this setting.

  The next five options are relevant only if the "ADC correction" option
  is "On", and provide independent control of each of the correction
  actions.

  Fix Isc point:
    If "ADC correction" is "On", this controls whether the first point of the
    curve should be modified (or even removed in some cases). This point is the
    Arduino code's attempt at approximating the Isc point, but its simplistic
    algorithm often gets it wrong. When this control is "On", the Isc point is
    removed if the first measured point after it has a voltage value more than
    20% of the Voc voltage value (in which case implying that we know Isc is
    misleading). Otherwise, it is extrapolated from the beginning of the curve
    using a more sophisticated algorithm than the Arduino code uses.

  Fix Voc point:
    If "ADC correction" is "On", this controls whether the last point of the
    curve should be modified. The Arduino code records the actual ADC values
    for both channels. Due to noise, however, the value on the channel
    measuring current is usually not zero. This correction simply zeros out
    that value.

  Combine =V points:
    If "ADC correction" is "On", this controls whether consecutive points that
    have equal ADC values on the voltage channel will be combined to a single
    point using the average of the ADC values on the current channel for those
    points.

  Reduce noise:
    If "ADC correction" is "On", this controls whether the noise reduction
    algorithm is applied.

  Fix overshoot:
    If "ADC correction" is "On", this controls whether the curve is corrected
    to fix the phemomenon where the tail of the IV curve overshoots the voltage
    that was measured when the circuit was actually open, before charging the
    capacitor. The voltage of all points is scaled such that the tail of the
    curve hits the I=0 point at the measured Voc voltage. This phenomenon was a
    mystery. It is now understood to be due to the +5V supply (from USB)
    drooping when the relay is active. The reduced reference voltage to the ADC
    results in voltage measurements that are too high. Negative overshoot
    (i.e. undershoot) is also corrected; this can be due to SSR current draw in
    the SSR version.

Battery bias:
  The cell version of IV Swinger 2 may require a bias battery to be placed in
  series with the PV cell in order to trace the curve properly.  A calibration
  of the bias battery must be performed before swinging a cell IV curve using
  the bias battery.  Once that has been done, this control enables the software
  to "subtract" the bias such that the rendered IV curve is that of the PV cell
  alone.

Series resistance compensation (milliohms):
  This control may be used to negate the effect of any resistance that is in
  series with the PV module or cell under test upstream from the point where
  the voltage is measured. If this value is positive, the voltage at each
  plotted point is increased by an amount equal to I * series_res_comp. This
  could be used, for example, to factor out the effect of a long cable with
  known resistance. The resulting curve will have a steeper slope (and higher
  power MPP), as it would without the long cable. A negative value has the
  opposite effect. Different values may be specified for the normal and battery
  bias modes.
"""
        font = HELP_DIALOG_FONT
        self.text = ScrolledText(master, height=1, borderwidth=10)
        self.text.tag_configure("body_tag", font=font)
        self.text.tag_configure("heading_tag", font=font, underline=True)
        self.text.insert("end", help_text_1, ("body_tag"))
        self.text.pack(fill=BOTH, expand=True)


# SPI clock combobox class
#
class SpiClkCombo(ttk.Combobox):
    """Class that implements the Combobox used to select Arduino SPI clock
       frequency
    """
    # pylint: disable=too-many-ancestors

    # Initializer
    def __init__(self, master=None, gui=None, textvariable=None):
        ttk.Combobox.__init__(self, master=master, textvariable=textvariable)
        self.gui = gui
        spi_clk_div = self.gui.config.cfg.getint("Arduino", "spi clock div")
        textvariable.set(SPI_COMBO_VALS[spi_clk_div])
        self["values"] = (SPI_COMBO_VALS[SPI_CLOCK_DIV2],
                          SPI_COMBO_VALS[SPI_CLOCK_DIV4],
                          SPI_COMBO_VALS[SPI_CLOCK_DIV8],
                          SPI_COMBO_VALS[SPI_CLOCK_DIV16],
                          SPI_COMBO_VALS[SPI_CLOCK_DIV32],
                          SPI_COMBO_VALS[SPI_CLOCK_DIV64],
                          SPI_COMBO_VALS[SPI_CLOCK_DIV128])
        self.state(["readonly"])
        self["width"] = 13


# Looping help dialog class
#
class LoopingHelpDialog(Dialog):
    """Class that is extended from the generic Dialog class and is used for
       the Looping Help dialog
    """
    # Initializer
    def __init__(self, master=None):
        title = "Looping Help"
        Dialog.__init__(self, master=master, title=title,
                        has_cancel_button=False, return_ok=True,
                        parent_is_modal=True,
                        resizable=True,
                        min_height=HELP_DIALOG_MIN_HEIGHT_PIXELS,
                        max_height=HELP_DIALOG_MAX_HEIGHT_PIXELS)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Method to create the dialog body, which is just a Text widget"""
        help_text_1 = """
There are currently only two options on the Preferences Looping tab. The main
options controlling looping behavior are on the main IV Swinger 2 window to
the right of the "Swing!" button. The first Preferences option is to choose
whether the settings on the main screen should be retained after the program is
closed and restored the next time it is opened.  The second is to choose
whether or not looping should stop on non-fatal errors.
"""
        font = HELP_DIALOG_FONT
        self.text = ScrolledText(master, height=1, borderwidth=10)
        self.text.tag_configure("body_tag", font=font)
        self.text.tag_configure("heading_tag", font=font, underline=True)
        self.text.insert("end", help_text_1, ("body_tag"))
        self.text.pack(fill=BOTH, expand=True)


# Arduino help dialog class
#
class ArduinoHelpDialog(Dialog):
    """Class that is extended from the generic Dialog class and is used for
       the Arduino Help dialog
    """
    # Initializer
    def __init__(self, master=None):
        title = "Arduino Help"
        Dialog.__init__(self, master=master, title=title,
                        has_cancel_button=False, return_ok=True,
                        parent_is_modal=True,
                        resizable=True,
                        min_height=HELP_DIALOG_MIN_HEIGHT_PIXELS,
                        max_height=HELP_DIALOG_MAX_HEIGHT_PIXELS)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Method to create the dialog body, which is just a Text widget"""
        help_text_1 = """
The configuration options on the Arduino tab are for advanced users who are
familiar with the code that runs on the IV Swinger 2 Arduino microcontroller.
Normally the default values should be used. Any changes made here are sent to
the Arduino when the OK button is pressed and take effect starting with the
next run. Here are very brief descriptions of each option:

SPI clock freq:
  Clock frequency of the SPI bus. The SPI bus is used to communicate with the
  MCP3202 ADC.  At 5V, the MCP3202 is specified to work up to 1.8 MHz, but
  current parts have been shown to operate fine with faster clocks.  A higher
  SPI clock frequency results in more closely spaced points on the IV
  curve. The default is 2 MHz.

Max IV points:
  Maximum number of I/V pairs to capture.  The actual number will always be
  less (sometimes substantially less).

Min Isc ADC:
  Minimum ADC value the channel measuring current must reach before starting to
  poll for stable Isc.

Max Isc poll:
  Maximum number of loops waiting for Isc to stabilize before giving up.

Isc stable ADC:
  Three consecutive measurements must vary less than this amount for Isc to be
  considered stable.

Max discards:
  Maximum consecutive points that may be discarded because they are too close
  together before recording a point anyway.

Aspect height:
  Height of graph's aspect ratio (max 8). Used for "distance" calculation in
  the discard algorithm.

Aspect width:
  Width of graph's aspect ratio (max 8). Used for "distance" calculation in the
  discard algorithm.

Relay is active-high:
  Check ONLY if the IV Swinger 2 was constructed with a (non-standard) relay
  module that has an active-high trigger pin. This value will be saved in the
  Arduino EEPROM so the hardware "remembers" what type of relay it has. NEVER
  check for an IV Swinger 2 that uses solid-state relays (SSRs); damage could
  result.
"""
        font = HELP_DIALOG_FONT
        self.text = ScrolledText(master, height=1, borderwidth=10)
        self.text.tag_configure("body_tag", font=font)
        self.text.tag_configure("heading_tag", font=font, underline=True)
        self.text.insert("end", help_text_1, ("body_tag"))
        self.text.pack(fill=BOTH, expand=True)


# Overlay help dialog class
#
class OverlayHelpDialog(Dialog):
    """Class that is extended from the generic Dialog class and is used for
       the Overlay Help dialog
    """
    # Initializer
    def __init__(self, master=None):
        title = "Overlay Help"
        Dialog.__init__(self, master=master, title=title,
                        has_cancel_button=False, return_ok=True,
                        resizable=True,
                        min_height=HELP_DIALOG_MIN_HEIGHT_PIXELS,
                        max_height=HELP_DIALOG_MAX_HEIGHT_PIXELS)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Method to create the dialog body, which is just a Text widget"""
        help_text_intro = """
Up to 8 curves may be overlaid. The curves that are selected when the Overlay
button is pressed are plotted and listed in the "Overlay Runs" pane.
"""
        help_heading_1 = """
Adding and removing:"""
        help_text_1 = """
Curves may be added to or removed from the current overlay by changing the
selection in the main Results Wizard tree view pane (Shift-click and
Control-click are useful).
"""
        help_heading_2 = """
Naming:"""
        help_text_2 = """
By default the curves inherit their titles from the Results Wizard tree view
pane or are named for the date and time they were captured if they are
untitled.  This name can be changed on the overlay by double-clicking it in the
"Overlay Runs" pane. The new name will remain associated with that run only
until the application is closed.
"""
        help_heading_3 = """
Ordering:"""
        help_text_3 = """
Initially the selected curves are ordered from oldest to newest. The order can
be changed by dragging entries in the "Overlay Runs" pane to the desired
position. Curves that are added to the overlay are added at the bottom of the
list. Clicking on the "Date/Time" heading sorts the curves chronologically,
reversing direction each time it is clicked.
"""
        help_heading_4 = """
Labels:"""
        help_text_4 = """
By default, the Isc, MPP, and Voc points are only labeled for the curve at the
top of the list. There are checkbuttons to enable labeling these points on all
curves. For the MPPs, there is another checkbutton to display only the power
(and not the V x I values). There is no support for designating specific curves
for labeling. When all Isc points are labeled, the labels are ordered from left
to right (leftmost label is for curve at the top of the list, rightmost label
is for the curve at the bottom of the list). MPP and Voc labels are ordered
from top to bottom, matching the list order.
"""
        help_heading_5 = """
Finishing:"""
        help_text_5 = """
When the "Finished" button is pressed, the overlay is finalized. The "Overlay
Runs" pane closes and the new overlay is added to the "Overlays" group in the
main Results Wizard tree view pane. The "Copy" button may then be used to copy
the overlay PDF (and GIF) to a USB drive or elsewhere. Note that once an
overlay is finalized, only the images are saved; it is not possible to modify
an overlay after it is finalized.
"""
        font = HELP_DIALOG_FONT
        self.text = ScrolledText(master, height=1, borderwidth=10)
        self.text.tag_configure("body_tag", font=font)
        self.text.tag_configure("heading_tag", font=font, underline=True)
        self.text.insert("end", help_text_intro, ("body_tag"))
        self.text.insert("end", help_heading_1, ("heading_tag"))
        self.text.insert("end", help_text_1, ("body_tag"))
        self.text.insert("end", help_heading_2, ("heading_tag"))
        self.text.insert("end", help_text_2, ("body_tag"))
        self.text.insert("end", help_heading_3, ("heading_tag"))
        self.text.insert("end", help_text_3, ("body_tag"))
        self.text.insert("end", help_heading_4, ("heading_tag"))
        self.text.insert("end", help_text_4, ("body_tag"))
        self.text.insert("end", help_heading_5, ("heading_tag"))
        self.text.insert("end", help_text_5, ("body_tag"))
        self.text.pack(fill=BOTH, expand=True)


# Image pane class
#
class ImagePane(ttk.Label):
    """Class that implements the image pane"""
    # pylint: disable=too-many-ancestors

    # In Tkinter, the way to display an image is in a "Label" widget,
    # which makes it sound small. In our case it takes up the majority
    # of the GUI, so we'll call it a "pane" instead of a label. But it's
    # really a Label.

    # Initializer
    def __init__(self, master=None):
        ttk.Label.__init__(self, master=master, compound="center")
        self.master = master
        self.font = tkFont.Font(family='TkDefaultFont')
        self.img_file = None
        self.current_img = None
        self.image = None
        self.splash_img_showing = False
        self.display_splash_img()

    # -------------------------------------------------------------------------
    def display_img(self, text=None):
        """Method to display the appropriately-sized image"""
        x_pixels = self.master.ivs2.x_pixels
        y_pixels = int(round(self.master.ivs2.x_pixels *
                             self.master.ivs2.plot_y_inches /
                             self.master.ivs2.plot_x_inches))
        img = Image.open(self.img_file).resize((x_pixels, y_pixels))
        self.current_img = ImageTk.PhotoImage(img)
        if text is not None:
            self.font.configure(size=int(-y_pixels/20))  # neg => pixel height
            self["font"] = self.font
            self["justify"] = "center"
            self["text"] = text
        else:
            self["text"] = ""
        self["image"] = self.current_img
        self.image = self.current_img

    # -------------------------------------------------------------------------
    def display_splash_img(self):
        """Method to display the splash image"""
        self.img_file = os.path.join(self.master.app_dir, SPLASH_IMG)
        if not os.path.exists(self.img_file):
            err_msg = """
FATAL ERROR: file {} does not exist

This is most likely a problem with the
installation. Please make sure that you
have write permission to the application
folder. An Administrator account should
be used for the install.
""".format(self.img_file)
            tkmsg_showerror(self.master, message=err_msg)
            sys.exit()
        else:
            self.display_img()
            self.splash_img_showing = True

    # -------------------------------------------------------------------------
    def display_error_img(self, text="ERROR"):
        """Method to display an error message image on the screen"""
        self.img_file = os.path.join(self.master.app_dir, BLANK_IMG)
        self["foreground"] = "red"
        self.font.configure(slant="italic")
        self.display_img(text=text)


# Go/Stop button class
#
class GoStopButton(ttk.Button):
    """Class that implements the Button widget used for the go button and
       stop button
    """
    # pylint: disable=too-many-ancestors

    # Initializer
    def __init__(self, master=None, text=None):
        ttk.Button.__init__(self, master=master)
        self["text"] = "Swing!"
        if text is not None:
            self["text"] = text
        self["style"] = "go_stop_button.TButton"


# Plot power checkbutton class
#
class PlotPower(ttk.Checkbutton):
    """Class that implements the Checkbutton widget used to choose whether
       to include the power curve on the plot
    """
    # pylint: disable=too-many-ancestors

    # Initializer
    def __init__(self, master=None, variable=None):
        ttk.Checkbutton.__init__(self, master=master, text="Plot Power",
                                 command=self.update_plot_power,
                                 variable=variable,
                                 onvalue="Plot", offvalue="DontPlot")
        self.master = master
        self.plot_power = variable
        if self.master.config.cfg.getboolean("Plotting", "plot power"):
            self.invoke()

    # -------------------------------------------------------------------------
    def update_plot_power(self, event=None):
        """Method to update and apply the plot power option"""
        # pylint: disable=unused-argument

        # Replace config from saved config of displayed image
        run_dir = self.master.ivs2.hdd_output_dir
        config_dir = os.path.dirname(self.master.config.cfg_filename)
        if run_dir is not None and run_dir != config_dir:
            cfg_file = os.path.join(run_dir, "{}.cfg".format(APP_NAME))
            if os.path.exists(cfg_file):
                # Snapshot current config
                original_cfg_file = self.master.config.cfg_filename
                self.master.config.get_snapshot()
                # Get config from run_dir
                self.master.config.cfg_filename = cfg_file
                self.master.config.get_old_result(cfg_file)

        # Update IVS2 property
        self.master.ivs2.plot_power = (self.plot_power.get() == "Plot")

        # Update the "plot power" config option
        self.master.config.cfg_set("Plotting", "plot power",
                                   self.master.ivs2.plot_power)

        # Redisplay the image (with power plotted) - saves config
        self.master.redisplay_img(reprocess_adc=False)

        # Restore the config file from the snapshot
        if (run_dir is not None and run_dir != config_dir and
                os.path.exists(cfg_file)):
            self.master.config.cfg_filename = original_cfg_file
            self.master.config.save_snapshot()

        # Unlock the axes
        if self.master.axes_locked.get() == "Unlock":
            self.master.unlock_axes()


# Lock axes checkbutton class
#
class LockAxes(ttk.Checkbutton):
    """Class that implements the Checkbutton widget used to lock the axis ranges
    """
    # pylint: disable=too-many-ancestors

    # Initializer
    def __init__(self, master=None, gui=None, variable=None):
        ttk.Checkbutton.__init__(self, master=master, text="Lock",
                                 command=self.update_axis_lock,
                                 variable=variable,
                                 onvalue="Lock", offvalue="Unlock")
        self.gui = gui
        self.axes_locked = variable

    # -------------------------------------------------------------------------
    def update_axis_lock(self, event=None):
        """Method to update and apply the axis lock"""
        # pylint: disable=unused-argument
        axes_are_locked = (self.axes_locked.get() == "Lock")
        # Update IVS2 property
        self.gui.ivs2.plot_lock_axis_ranges = axes_are_locked
        # Update values in range boxes
        self.gui.update_axis_ranges()
        # (Optionally) redisplay the image with the new settings (saves
        # config)
        if self.gui.props.redisplay_after_axes_unlock:
            self.gui.redisplay_img(reprocess_adc=False)


# Loop mode checkbutton class
#
class LoopMode(ttk.Checkbutton):
    """Class that implements the Checkbutton widget used to enable loop mode
    """
    # pylint: disable=too-many-ancestors

    # Initializer
    def __init__(self, master=None, gui=None, variable=None,
                 rate_limit=None, save_results=None, lock_axes=None):
        # pylint: disable=too-many-arguments
        ttk.Checkbutton.__init__(self, master=master, text="Loop Mode",
                                 command=self.update_loop_mode,
                                 variable=variable,
                                 onvalue="On", offvalue="Off")
        self.gui = gui
        self.loop_mode = variable
        self.rate_limit = rate_limit
        self.save_results = save_results
        self.lock_axes = lock_axes
        self.axes_already_locked = False
        if (self.gui.config.cfg.getboolean("Looping", "restore values") and
                self.gui.config.cfg.getboolean("Looping", "loop mode")):
            self.invoke()

    # -------------------------------------------------------------------------
    def update_loop_mode(self, event=None):
        """Method to update and apply the loop mode option"""
        # pylint: disable=unused-argument
        if self.loop_mode.get() == "On":
            self.gui.loop_mode.set("On")
            self.gui.props.loop_mode_active = True
            self.rate_limit.state(["!disabled"])
            self.save_results.state(["!disabled"])
            if self.lock_axes.instate(["selected"]):
                self.axes_already_locked = True
            else:
                self.axes_already_locked = False
                self.lock_axes.invoke()  # Lock axes
                # But clear axis ranges so they lock on the first run of
                # the loop
                self.gui.ivs2.plot_max_x = None
                self.gui.ivs2.plot_max_y = None
            self.lock_axes.state(["disabled"])
        else:
            self.gui.loop_mode.set("Off")
            self.gui.props.loop_mode_active = False
            self.rate_limit.state(["disabled"])
            self.save_results.state(["disabled"])
            self.lock_axes.state(["!disabled"])
            if not self.axes_already_locked:
                self.gui.props.redisplay_after_axes_unlock = False
                self.lock_axes.invoke()  # Unlock axes
                self.gui.props.redisplay_after_axes_unlock = True

        # Save values to config
        self.gui.config.cfg_set("Looping", "loop mode",
                                self.gui.props.loop_mode_active)
        self.gui.props.suppress_cfg_file_copy = True
        self.gui.save_config()


# Loop rate limit checkbutton class
#
class LoopRateLimit(ttk.Checkbutton):
    """Class that implements the Checkbutton widget used to rate limit loop
       mode
    """
    # pylint: disable=too-many-ancestors

    # Initializer
    def __init__(self, master=None, gui=None, variable=None):
        ttk.Checkbutton.__init__(self, master=master, text="Rate Limit",
                                 command=self.update_loop_rate_limit,
                                 variable=variable,
                                 onvalue="On", offvalue="Off")
        self.master = master
        self.gui = gui
        self.loop_rate_limit = variable
        self.value_label_obj = None
        self.state(["disabled"])

    # -------------------------------------------------------------------------
    def update_loop_rate_limit(self, event=None):
        """Method to update and apply the loop rate limit option"""
        # pylint: disable=unused-argument
        if self.value_label_obj is not None:
            self.value_label_obj.destroy()
        if self.loop_rate_limit.get() == "On":
            curr_loop_delay = self.gui.props.loop_delay
            prompt_str = "Enter seconds to delay between loops:"
            new_loop_delay = tksd_askinteger(self.gui,
                                             title="Loop delay",
                                             prompt=prompt_str,
                                             initialvalue=curr_loop_delay)
            if new_loop_delay:
                self.gui.props.loop_rate_limit = True
                self.gui.props.loop_delay = new_loop_delay
                self.update_value_str()
            else:
                self.gui.props.loop_rate_limit = False
                self.gui.props.loop_delay = 0
                self.state(["!selected"])
        else:
            self.gui.props.loop_rate_limit = False

        # Save values to config
        self.gui.config.cfg_set("Looping", "rate limit",
                                self.gui.props.loop_rate_limit)
        self.gui.config.cfg_set("Looping", "delay",
                                self.gui.props.loop_delay)
        self.gui.save_config()

    # -------------------------------------------------------------------------
    def update_value_str(self):
        """Method to update the string in the rate limit label"""
        value_str = "= {}s".format(self.gui.props.loop_delay)
        self.value_label_obj = ttk.Label(self.master, text=value_str)
        self.value_label_obj.pack(side=LEFT)


# Loop save results checkbutton class
#
class LoopSaveResults(ttk.Checkbutton):
    """Class that implements the Checkbutton widget used to enable/disable
       saving loop mode results
    """
    # pylint: disable=too-many-ancestors

    # Initializer
    def __init__(self, master=None, gui=None, variable=None):
        ttk.Checkbutton.__init__(self, master=master, text="Save Results",
                                 command=self.update_loop_save_results,
                                 variable=variable,
                                 onvalue="On", offvalue="Off")
        self.master = master
        self.gui = gui
        self.loop_save_results = variable
        self.value_label_obj = None
        self.state(["disabled"])

    # -------------------------------------------------------------------------
    def update_loop_save_results(self, event=None):
        """Method to update and apply the loop save results options"""
        # pylint: disable=unused-argument
        if self.value_label_obj is not None:
            self.value_label_obj.destroy()
        if self.loop_save_results.get() == "On":
            self.gui.props.loop_save_results = True
            include_graphs = tkmsg_askyesno(self.gui,
                                            "Include graphs?",
                                            "Default is to save CSV files "
                                            "only. Do you want to save PDFs"
                                            " and GIFs too?",
                                            default=tkmsg.NO)
            self.gui.props.loop_save_graphs = include_graphs
            self.update_value_str()
        else:
            self.gui.props.loop_save_results = False
            self.configure(text="Save Results")

        # Save values to config
        self.gui.config.cfg_set("Looping", "save results",
                                self.gui.props.loop_save_results)
        self.gui.config.cfg_set("Looping", "save graphs",
                                self.gui.props.loop_save_graphs)
        self.gui.save_config()

    # -------------------------------------------------------------------------
    def update_value_str(self):
        """Method to update the string in the save results label"""
        if self.gui.props.loop_save_graphs:
            value_str = "(All)"
        else:
            value_str = "(CSV only)"
        self.value_label_obj = ttk.Label(self.master, text=value_str)
        self.value_label_obj.pack(side=LEFT)


############
#   Main   #
############
def main():
    """Main function"""
    try:
        gui = GraphicalUserInterface()
        gui.run()
    except SystemExit:
        gui.close_gui()
    except:  # pylint: disable=bare-except
        handle_early_exception()


# Boilerplate main() call
if __name__ == "__main__":
    main()
