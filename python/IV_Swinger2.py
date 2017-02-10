#!/usr/bin/env python
"""IV Swinger 2 user interface module"""
#
###############################################################################
#
# IV_Swinger2.py: IV Swinger 2 host application module
#
# Copyright (C) 2016  Chris Satterlee
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
# host application.  It provides the interface between the user and the
# IV Swinger 2 hardware via the Arduino firmware.
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
# running Python and supports the Tkinter GUI toolset (which is built
# into Python).
#
import argparse
import ConfigParser
import datetime as dt
import glob
import io
import os
import re
try:
    # Mac/Unix only
    import resource
except ImportError:
    # Used only for memory leak debug, so just skip import on Windows
    pass
import serial
import serial.tools.list_ports
import shutil
import subprocess
import sys
import time
import ttk
import Tkinter as tk
import tkFileDialog
import tkMessageBox as tkmsg
import tkSimpleDialog as tksd
from PIL import Image, ImageTk
try:
    # Mac only
    from AppKit import NSSearchPathForDirectoriesInDomains as get_mac_dir
    from AppKit import NSApplicationSupportDirectory as mac_app_sup_dir
    from AppKit import NSUserDomainMask as mac_domain_mask
except:
    pass
import IV_Swinger
import IV_Swinger_plotter
from Tooltip import Tooltip

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
SPLASH_IMG = "Splash_Screen.png"
CFG_STRING = 0
CFG_FLOAT = 1
CFG_INT = 2
CFG_BOOLEAN = 3
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
# Tk constants
N = tk.N
S = tk.S
W = tk.W
E = tk.E
TOP = tk.TOP
BOTTOM = tk.BOTTOM
LEFT = tk.LEFT
RIGHT = tk.RIGHT
HORIZONTAL = tk.HORIZONTAL
VERTICAL = tk.VERTICAL
X = tk.X
Y = tk.Y
BOTH = tk.BOTH
# From Arduino SPI.h:
SPI_CLOCK_DIV4 = 0x00
SPI_CLOCK_DIV16 = 0x01
SPI_CLOCK_DIV64 = 0x02
SPI_CLOCK_DIV128 = 0x03
SPI_CLOCK_DIV2 = 0x04
SPI_CLOCK_DIV8 = 0x05
SPI_CLOCK_DIV32 = 0x06
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
FONT_SCALE_DEFAULT = 1.0
LINE_SCALE_DEFAULT = 1.0
POINT_SCALE_DEFAULT = 1.0
CORRECT_ADC_DEFAULT = "On"
# Default Arduino config
SPI_CLK_DEFAULT = SPI_CLOCK_DIV8
MAX_IV_POINTS_DEFAULT = 275
MIN_ISC_ADC_DEFAULT = 100
MAX_ISC_POLL_DEFAULT = 5000
ISC_STABLE_DEFAULT = 5
MAX_DISCARDS_DEFAULT = 300
ASPECT_HEIGHT_DEFAULT = 2
ASPECT_WIDTH_DEFAULT = 3
# Other Arduino constants
MAX_MSG_LEN_TO_ARDUINO = 30
ARDUINO_MAX_INT = (1 << 15) - 1
ADC_MAX = 4095
MAX_ASPECT = 8
# Debug constants
DEBUG_CONFIG = False
DEBUG_MEMLEAK = False


########################
#   Global functions   #
########################
def debug_memleak(str):
    """Global function to print the current memory usage at a give place in the
       code or point in time. Not supported on Windows.
    """
    if DEBUG_MEMLEAK:
        date_time_str = IV_Swinger.DateTimeStr.get_date_time_str()
        print ("%s: Memory usage (%s): %s (kb)" %
               (date_time_str, str,
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))


def get_app_dir():
    """Global function to return the directory where the application is
       located, regardless of whether it is a script or a frozen
       executable (e.g. built with pyinstaller).
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    elif __file__:
        return os.path.dirname(__file__)


#################
#   Classes     #
#################


# Tkinter/ttk GUI class
#
class GraphicalUserInterface(ttk.Frame):
    """Provides GUI for user interaction with the IV Swinger 2"""

    # Initializer
    def __init__(self, ivs2=None):
        self.root = tk.Tk()
        self.set_root_options()
        ttk.Frame.__init__(self, self.root)
        self.memory_monitor()
        self.ivs2 = ivs2
        self.init_instance_vars()
        self.set_grid()
        self.get_config()
        self.start_to_right()
        self.set_style()
        self.create_menu_bar()
        self.menu_bar.disable_calibration()
        self.create_widgets()
        self.ivs2.log_initial_debug_info()
        self.after(100, lambda: self.attempt_arduino_handshake())

    def memory_monitor(self):
        debug_memleak("memory_monitor")
        self.after(1000, lambda: self.memory_monitor())

    def init_instance_vars(self):
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
        self.grid_args = {}
        self.results_wiz = None
        self.img_file = None
        self._restore_loop = False
        self._loop_mode_active = False
        self._loop_rate_limit = False
        self._loop_delay = 0
        self._loop_save_results = False
        self._loop_save_graphs = False
        self._suppress_cfg_file_copy = False
        self._plot_title = None
        self._overlay_names = {}
        self._overlay_dir = None
        self._overlay_mode = False
        self._spi_clk_div = SPI_CLK_DEFAULT
        self._max_iv_points = MAX_IV_POINTS_DEFAULT
        self._min_isc_adc = MIN_ISC_ADC_DEFAULT
        self._max_isc_poll = MAX_ISC_POLL_DEFAULT
        self._isc_stable_adc = ISC_STABLE_DEFAULT
        self._max_discards = MAX_DISCARDS_DEFAULT
        self._aspect_height = ASPECT_HEIGHT_DEFAULT
        self._aspect_width = ASPECT_WIDTH_DEFAULT

    # ---------------------------------
    @property
    def restore_loop(self):
        """True if loop settings should be restored on next startup,
        false otherwise
        """
        return self._restore_loop

    @restore_loop.setter
    def restore_loop(self, value):
        if value not in set([True, False]):
            raise ValueError("restore_loop must be boolean")
        self._restore_loop = value

    # ---------------------------------
    @property
    def loop_mode_active(self):
        """True if loop mode is active, false otherwise
        """
        return self._loop_mode_active

    @loop_mode_active.setter
    def loop_mode_active(self, value):
        if value not in set([True, False]):
            raise ValueError("loop_mode_active must be boolean")
        self._loop_mode_active = value

    # ---------------------------------
    @property
    def loop_rate_limit(self):
        """True if loop rate limiting is in effect, false otherwise
        """
        return self._loop_rate_limit

    @loop_rate_limit.setter
    def loop_rate_limit(self, value):
        if value not in set([True, False]):
            raise ValueError("loop_rate_limit must be boolean")
        self._loop_rate_limit = value

    # ---------------------------------
    @property
    def loop_delay(self):
        """Seconds to delay between loops
        """
        return self._loop_delay

    @loop_delay.setter
    def loop_delay(self, value):
        self._loop_delay = value

    # ---------------------------------
    @property
    def loop_save_results(self):
        """True if results should be saved while looping, false otherwise
        """
        return self._loop_save_results

    @loop_save_results.setter
    def loop_save_results(self, value):
        if value not in set([True, False]):
            raise ValueError("loop_save_results must be boolean")
        self._loop_save_results = value

    # ---------------------------------
    @property
    def loop_save_graphs(self):
        """True if graphs should be saved while looping, false otherwise
        """
        return self._loop_save_graphs

    @loop_save_graphs.setter
    def loop_save_graphs(self, value):
        if value not in set([True, False]):
            raise ValueError("loop_save_graphs must be boolean")
        self._loop_save_graphs = value

    # ---------------------------------
    @property
    def suppress_cfg_file_copy(self):
        """True if copying the config file should be suppressed
        """
        return self._suppress_cfg_file_copy

    @suppress_cfg_file_copy.setter
    def suppress_cfg_file_copy(self, value):
        if value not in set([True, False]):
            raise ValueError("suppress_cfg_file_copy must be boolean")
        self._suppress_cfg_file_copy = value

    # ---------------------------------
    @property
    def plot_title(self):
        """Title of plot
        """
        return self._plot_title

    @plot_title.setter
    def plot_title(self, value):
        self._plot_title = value

    # ---------------------------------
    @property
    def overlay_names(self):
        """Dict containing mapping of dts to name for overlay curves
        """
        return self._overlay_names

    @overlay_names.setter
    def overlay_names(self, value):
        self._overlay_names = value

    # ---------------------------------
    @property
    def overlay_dir(self):
        """Name of directory for current overlay
        """
        return self._overlay_dir

    @overlay_dir.setter
    def overlay_dir(self, value):
        self._overlay_dir = value

    # ---------------------------------
    @property
    def overlay_mode(self):
        """True if the Results Wizard is in overlay mode
        """
        return self._overlay_mode

    @overlay_mode.setter
    def overlay_mode(self, value):
        if value not in set([True, False]):
            raise ValueError("overlay_mode must be boolean")
        self._overlay_mode = value

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

    # -------------------------------------------------------------------------
    def get_adc_pairs_from_csv(self, adc_csv_file):
        return self.ivs2.read_adc_pairs_from_csv_file(adc_csv_file)

    # -------------------------------------------------------------------------
    def set_root_options(self):
        # Disable resizing, at least for now
        self.root.resizable(width=False, height=False)
        # No dotted line in menus
        self.root.option_add('*tearOff', False)
        self.root.title('IV Swinger 2')

    # -------------------------------------------------------------------------
    def set_style(self):
        self.style = ttk.Style()
        font = ("Arial " +
                str(max(int(round(self.ivs2.x_pixels / 43.0)), 19)) +
                " bold italic")
        self.style.configure("go_stop_button.TButton",
                             foreground="red",
                             background="gray",
                             padding=10,
                             font=font)

    # -------------------------------------------------------------------------
    def set_grid(self):
        self.grid(column=0, row=0, sticky=(N, S, E, W))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    # -------------------------------------------------------------------------
    def create_menu_bar(self):
        """Method to create the menu bar
        """
        self.menu_bar = MenuBar(master=self)

    # -------------------------------------------------------------------------
    def get_dialog_width(self, dialog):
        """Method to parse the width of a dialog from its current geometry"""
        m = re.match("(\d+)x(\d+)",  dialog.geometry())
        width = int(m.group(1))
        return width

    # -------------------------------------------------------------------------
    def set_dialog_geometry(self, dialog, min_height=None):
        """Method to set the size and position of a dialog. If min_height is
           specified, the window will be sized to that value initially
           with a fixed maximum height of its height when this method
           was called. This is used for the Results Wizard. Otherwise,
           the height and width are not changed, only the
           offsets. This is used for other dialogs.
        """
        # Run update_idletasks to get the geometry manager to size the
        # window to fit the widgets
        self.update_idletasks()

        # Get current window width
        width = self.get_dialog_width(dialog)

        if min_height is not None:
            # Disable width resizing by setting min and max width to
            # the width that it comes up. This is a workaround for the
            # fact that (at least on Mac) the "resizable" option
            # doesn't work for width only.
            max_height = dialog.winfo_height()
            dialog.minsize(width, min_height)
            dialog.maxsize(width, max_height)

        # Calculate offset of wizard from the root window. If there
        # are enough screen pixels to the left of the root window,
        # then put it there (with 10 pixels of overlap). Second choice
        # is to the right of the root window. Last choice is whichever
        # side has more space, overlapping root window by as much as
        # necessary to leave 10 pixels of screen.
        m = re.match(".*([-+]\d+)([-+]\d+)", self.root.geometry())
        left_pixels_avail = int(m.group(1))
        m = re.match("(\d+)x(\d+)", self.root.geometry())
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
            dialog.geometry("+%d+%d" % (self.winfo_rootx()-left_offset,
                                        self.winfo_rooty()+10))
        else:
            # Set the geometry to the initial (fixed) width, minimum
            # height, and offset from main window determined above
            dialog.geometry("%dx%d+%d+%d" % (width, min_height,
                                             self.winfo_rootx()-left_offset,
                                             self.winfo_rooty()+10))

        # Run update_idletasks to prevent momentary appearance of pre-resized
        # window
        self.update_idletasks()

    # -------------------------------------------------------------------------
    def create_widgets(self):
        total_cols = 12
        pad_cols = 2
        column = 1
        row = 1
        # Grid layout
        self.grid_args['img_size_combo'] = {"column": column,
                                            "row": row,
                                            "sticky": (W)}
        row += 1
        self.grid_args['img_pane'] = {"column": column,
                                      "row": row,
                                      "columnspan": total_cols}
        row += 1
        self.grid_args['prefs_results_buttons'] = {"column": column,
                                                   "row": row,
                                                   "rowspan": 3}
        column += pad_cols
        self.grid_args['axis_ranges_box'] = {"column": column,
                                             "row": row,
                                             "rowspan": 3,
                                             "sticky": (W)}
        column += pad_cols
        self.grid_args['go_button'] = {"column": column,
                                       "row": row,
                                       "rowspan": 3}
        column += pad_cols
        self.grid_args['plot_power_cb'] = {"column": column,
                                           "row": row,
                                           "rowspan": 3}
        column += 1
        remaining_cols = total_cols - column + 1
        self.grid_args['looping_controls_box'] = {"column": column,
                                                  "row": row,
                                                  "sticky": (S, W),
                                                  "columnspan": remaining_cols}
        # Create them
        self.create_img_size_combo()
        self.create_img_pane()
        self.create_prefs_results_button_box()
        self.create_go_button()
        self.create_plot_power_cb()
        self.create_axis_ranges_box()
        self.create_looping_controls()

    # -------------------------------------------------------------------------
    def create_img_size_combo(self):
        """Method to create the image size combo box and its bindings
        """
        self.img_size_combo = ImgSizeCombo(master=self,
                                           textvariable=self.resolution_str)
        aspect = "%sx%s" % (str(self.ivs2.plot_x_inches),
                            str(self.ivs2.plot_y_inches))
        tt_text = ("Pull down to select desired display size or type in "
                   "desired size and hit Enter. Must be an apect ratio of "
                   "%s (height will be modified if not)" % aspect)
        Tooltip(self.img_size_combo, text=tt_text, **TOP_TT_KWARGS)
        self.img_size_combo.bind('<<ComboboxSelected>>', self.update_img_size)
        self.img_size_combo.bind('<Return>', self.update_img_size)
        self.img_size_combo.grid(**self.grid_args['img_size_combo'])

    # -------------------------------------------------------------------------
    def create_img_pane(self):
        """Method to create the image pane
        """
        self.img_pane = ImagePane(master=self)
        self.img_pane.grid(**self.grid_args['img_pane'])

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
        self.preferences_button.bind('<Button-1>', self.show_preferences)
        self.preferences_button.pack()

        self.results_button = ttk.Button(master=self.prefs_results_bb,
                                         text="Results Wizard")
        # Tooltip
        tt_text = ("View results of previous runs, combine multiple curves on "
                   "the same plot, modify their title and appearance, copy "
                   "them to USB (or elsewhere), and more ...")
        Tooltip(self.results_button, text=tt_text, **BOT_TT_KWARGS)
        self.results_button.bind('<Button-1>', self.results_actions)
        self.results_button.pack(pady=(8, 0))

        self.prefs_results_bb.grid(**self.grid_args['prefs_results_buttons'])

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
        self.v_range_entry.bind('<Return>', self.apply_new_ranges)
        self.i_range_entry.bind('<Return>', self.apply_new_ranges)
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
        axis_ranges_box.grid(**self.grid_args['axis_ranges_box'])

    # -------------------------------------------------------------------------
    def create_go_button(self, text=None):
        """Method to create the go button and its associated bindings
        """
        self.go_button = GoStopButton(master=self, text=text)
        self.go_button['width'] = 9
        # Tooltip
        tt_text = ("Trigger an IV curve trace (if ready). If loop mode is "
                   "selected, this button changes to a STOP button and curve "
                   "tracing continues until stopped.")
        Tooltip(self.go_button, text=tt_text, **BOT_TT_KWARGS)

        # Left-clicking go button and hitting Return or space bar do the
        # same thing
        self.go_button.bind('<Button-1>', self.go_actions)
        self.root.bind('<Return>', self.go_actions)
        self.root.bind('<space>', self.go_actions)
        self.go_button.grid(**self.grid_args['go_button'])

    # -------------------------------------------------------------------------
    def create_plot_power_cb(self):
        """Method to create the plt power checkbutton
        """
        self.plot_power_cb = PlotPower(master=self,
                                       variable=self.plot_power)
        # Tooltip
        tt_text = "Check to add the power curve to the plot"
        Tooltip(self.plot_power_cb, text=tt_text, **BOT_TT_KWARGS)
        self.plot_power_cb.grid(**self.grid_args['plot_power_cb'])

    # -------------------------------------------------------------------------
    def create_looping_controls(self):
        """Method to create the looping control widgets
        """
        grid_args = {}
        grid_args['loop_mode_cb'] = {"column": 1,
                                     "row": 1,
                                     "sticky": (W),
                                     "columnspan": 2}
        grid_args['loop_rate_box'] = {"column": 2,
                                      "row": 2,
                                      "sticky": (W),
                                      "columnspan": 1}
        grid_args['loop_save_box'] = {"column": 2,
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
        if self.ivs2.cfg.getboolean('Looping', 'restore values'):
            if self.loop_rate_limit:
                self.loop_rate_cb.state(['selected'])
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
        if (self.ivs2.cfg.getboolean('Looping', 'restore values') and
                self.ivs2.cfg.getboolean('Looping', 'loop mode')):
            if self.loop_save_results:
                self.loop_save_cb.state(['selected'])
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
        self.loop_mode_cb.grid(**grid_args['loop_mode_cb'])
        loop_rate_box.grid(**grid_args['loop_rate_box'])
        loop_save_box.grid(**grid_args['loop_save_box'])

        # Grid placement within main GUI
        looping_controls_box.grid(**self.grid_args['looping_controls_box'])

    # -------------------------------------------------------------------------
    def update_plot_power_cb(self):
        """Method to set the plot_power StringVar to the correct value, based
           on the value in the config
        """
        if self.ivs2.cfg.getboolean('Plotting', 'plot power'):
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
        self.v_range_entry.state(['disabled'])
        self.i_range_entry.state(['disabled'])
        if axes_are_locked:
            self.v_range_entry.state(['!disabled'])
            self.i_range_entry.state(['!disabled'])
            if self.ivs2.plot_max_x is not None:
                v_range_entry = str(self.ivs2.plot_max_x)
            if self.ivs2.plot_max_y is not None:
                i_range_entry = str(self.ivs2.plot_max_y)
        self.v_range.set(str(v_range_entry))
        self.i_range.set(str(i_range_entry))

    # -------------------------------------------------------------------------
    def apply_new_ranges(self, event=None):
        """Method to apply a new voltage or current range (max value on axis)
           when entered by the user
        """
        try:
            self.ivs2.plot_max_x = float(self.v_range.get())
            self.ivs2.plot_max_y = float(self.i_range.get())
            event.widget.tk_focusNext().focus()  # move focus out
        except:
            # Silently reject invalid values
            pass
        self.update_axis_ranges()
        self.update_idletasks()
        # Redisplay the image with the new settings (saves config)
        self.redisplay_img(reprocess_adc=False)

    # -------------------------------------------------------------------------
    def get_config(self):
        """Method to get the saved preferences and other configuration from the
           .cfg file if it exists, and apply the values to the
           associated properties
        """
        if DEBUG_CONFIG:
            dbg_str = ("get_config: Reading config from " +
                       self.ivs2.cfg_filename)
            self.ivs2.logger.print_and_log(dbg_str)
        self.ivs2.cfg = ConfigParser.SafeConfigParser()
        try:
            with open(self.ivs2.cfg_filename, "r") as cfg_fp:
                self.ivs2.cfg.readfp(cfg_fp)
        except IOError:
            # File doesn't exist
            self.ivs2.find_arduino_port()
            self.populate_config()
            self.save_config()
        else:
            # File does exist ...
            self.apply_all_config()

    # -------------------------------------------------------------------------
    def get_snapshot_config(self):
        """Method to get the saved preferences and other configuration
           from the .cfg file and store them in the snapshot config
        """
        if DEBUG_CONFIG:
            dbg_str = ("get_snapshot_config: Reading config from " +
                       self.ivs2.cfg_filename)
            self.ivs2.logger.print_and_log(dbg_str)
        self.ivs2.cfg_snapshot = ConfigParser.SafeConfigParser()
        with open(self.ivs2.cfg_filename, "r") as cfg_fp:
            self.ivs2.cfg_snapshot.readfp(cfg_fp)

    # -------------------------------------------------------------------------
    def get_old_result_config(self, cfg_file):
        """Method to get the preferences and other configuration from the
           specified .cfg file and apply the values to the associated
           properties. This includes the axes and title configurations,
           which are not applied in other cases. But it excludes the USB
           and Arduino configurations.
        """
        if DEBUG_CONFIG:
            dbg_str = "get_old_result_config: Reading config from " + cfg_file
            self.ivs2.logger.print_and_log(dbg_str)
        with open(cfg_file, "r") as cfg_fp:
            # Blow away old config and create new one
            self.ivs2.cfg = ConfigParser.SafeConfigParser()
            # Read values from file
            self.ivs2.cfg.readfp(cfg_fp)
            # Apply selected values to properties
            self.apply_general_config()
            self.apply_calibration_config()
            self.apply_plotting_config()
            self.apply_looping_config()
            self.apply_axes_config()
            self.apply_title_config()

    # -------------------------------------------------------------------------
    def get_old_title_config(self, cfg_file):
        """Method to get the title configuration from the specified .cfg file
           and apply its value to the current config and its
           associated property.
        """
        if DEBUG_CONFIG:
            dbg_str = "get_old_title_config: Reading config from " + cfg_file
            self.ivs2.logger.print_and_log(dbg_str)
        my_cfg = ConfigParser.SafeConfigParser()
        with open(cfg_file, "r") as cfg_fp:
            section = "Plotting"
            option = "title"
            # Read values from file
            my_cfg.readfp(cfg_fp)
            try:
                # Get title config
                title = my_cfg.get(section, option)
            except ConfigParser.NoOptionError:
                title = None
            # Update title in current config
            self.ivs2.cfg_set(section, option, title)
            # Apply title config only
            self.apply_title_config()

    # -------------------------------------------------------------------------
    def apply_one_config(self, section, option, config_type, old_prop_val):
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
                cfg_value = self.ivs2.cfg.getfloat(section, option)
                return float(cfg_value)
            elif config_type == CFG_INT:
                cfg_value = self.ivs2.cfg.getint(section, option)
                return int(cfg_value)
            elif config_type == CFG_BOOLEAN:
                cfg_value = self.ivs2.cfg.getboolean(section, option)
                return bool(cfg_value)
            elif config_type == CFG_STRING:
                cfg_value = self.ivs2.cfg.get(section, option)
                if cfg_value == "None":
                    cfg_value = None
                return cfg_value
            else:
                return old_prop_val
        except ConfigParser.NoOptionError:
            err_str = full_name + " not found in cfg file"
            self.ivs2.logger.print_and_log(err_str)
            self.ivs2.cfg_set(section, option, old_prop_val)
            return old_prop_val
        except ValueError:
            err_str = full_name + " invalid in cfg file"
            self.ivs2.logger.print_and_log(err_str)
            self.ivs2.cfg_set(section, option, old_prop_val)
            return old_prop_val

    # -------------------------------------------------------------------------
    def apply_all_config(self):
        """Method to apply the config read from the .cfg file to the
           associated object properties for all sections and options
        """
        # General section
        self.apply_general_config()

        # USB section
        self.apply_usb_config()

        # Calibration section
        self.apply_calibration_config()

        # Plotting section
        self.apply_plotting_config()

        # Looping section
        self.apply_looping_config()

        # Arduino section
        self.apply_arduino_config()

    # -------------------------------------------------------------------------
    def apply_general_config(self):
        """Method to apply the General section options read from the
           .cfg file to the associated object properties
        """
        section = 'General'

        # X pixels
        args = (section, 'x pixels', CFG_INT, self.ivs2.x_pixels)
        self.ivs2.x_pixels = self.apply_one_config(*args)

    # -------------------------------------------------------------------------
    def apply_usb_config(self):
        """Method to apply the USB section options read from the .cfg
           file to the associated object properties
        """
        section = 'USB'

        # Port
        option = 'port'
        full_name = section + " " + option
        try:
            cfg_value = self.ivs2.cfg.get(section, option)
        except ConfigParser.NoOptionError:
            err_str = full_name + " not found in cfg file"
            self.ivs2.logger.print_and_log(err_str)
            self.ivs2.find_arduino_port()
            self.ivs2.cfg_set(section, option, self.ivs2.usb_port)
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
                self.ivs2.cfg_set(section, option, self.ivs2.usb_port)
        # Baud
        args = (section, 'baud', CFG_INT, self.ivs2.usb_baud)
        self.ivs2.usb_baud = self.apply_one_config(*args)

    # -------------------------------------------------------------------------
    def apply_calibration_config(self):
        """Method to apply the Calibration section options read from the
           .cfg file to the associated object properties
        """
        section = 'Calibration'

        # Voltage
        args = (section, 'voltage', CFG_FLOAT, self.ivs2.v_cal)
        self.ivs2.v_cal = self.apply_one_config(*args)

        # Current
        args = (section, 'current', CFG_FLOAT, self.ivs2.i_cal)
        self.ivs2.i_cal = self.apply_one_config(*args)

    # -------------------------------------------------------------------------
    def apply_plotting_config(self):
        """Method to apply the Plotting section options read from the
           .cfg file to the associated object properties
        """
        section = 'Plotting'

        # Plot power
        args = (section, 'plot power', CFG_BOOLEAN, self.ivs2.plot_power)
        self.ivs2.plot_power = self.apply_one_config(*args)

        # Fancy labels
        args = (section, 'fancy labels', CFG_BOOLEAN, self.ivs2.fancy_labels)
        self.ivs2.fancy_labels = self.apply_one_config(*args)

        # Interpolation
        args = (section, 'linear', CFG_BOOLEAN, self.ivs2.linear)
        self.ivs2.linear = self.apply_one_config(*args)

        # Font scale
        args = (section, 'font scale', CFG_FLOAT, self.ivs2.font_scale)
        self.ivs2.font_scale = self.apply_one_config(*args)

        # Line scale
        args = (section, 'line scale', CFG_FLOAT, self.ivs2.line_scale)
        self.ivs2.line_scale = self.apply_one_config(*args)

        # Point scale
        args = (section, 'point scale', CFG_FLOAT, self.ivs2.point_scale)
        self.ivs2.point_scale = self.apply_one_config(*args)

        # ADC correction
        args = (section, 'correct adc', CFG_BOOLEAN, self.ivs2.correct_adc)
        self.ivs2.correct_adc = self.apply_one_config(*args)

    # -------------------------------------------------------------------------
    def apply_axes_config(self):
        """Method to apply the Plotting section "plot max x" and "plot max y"
           options read from the .cfg file to the associated object
           properties
        """
        section = 'Plotting'

        # Max x
        args = (section, 'plot max x', CFG_FLOAT, self.ivs2.plot_max_x)
        self.ivs2.plot_max_x = self.apply_one_config(*args)

        # Max y
        args = (section, 'plot max y', CFG_FLOAT, self.ivs2.plot_max_y)
        self.ivs2.plot_max_y = self.apply_one_config(*args)

        # Set the axis lock property so the values are used when the
        # plot is generated
        self.ivs2.plot_lock_axis_ranges = True

    # -------------------------------------------------------------------------
    def apply_title_config(self):
        """Method to apply the Plotting section "title" option read from the
           .cfg file to the associated object property
        """
        section = 'Plotting'
        args = (section, 'title', CFG_STRING, self.ivs2.plot_title)
        self.ivs2.plot_title = self.apply_one_config(*args)

    # -------------------------------------------------------------------------
    def apply_looping_config(self):
        """Method to apply the Looping section options read from the
           .cfg file to the associated object properties
        """
        section = 'Looping'

        # Restore values
        args = (section, 'restore values', CFG_BOOLEAN, self.restore_loop)
        self.restore_loop = self.apply_one_config(*args)

        if self.restore_loop:
            # Loop mode
            args = (section, 'loop mode', CFG_BOOLEAN, self.loop_mode_active)
            self.loop_mode_active = self.apply_one_config(*args)

            # Rate limit
            args = (section, 'rate limit', CFG_BOOLEAN, self.loop_rate_limit)
            self.loop_rate_limit = self.apply_one_config(*args)

            # Delay
            args = (section, 'delay', CFG_INT, self.loop_delay)
            self.loop_delay = self.apply_one_config(*args)

            # Save results
            args = (section, 'save results', CFG_BOOLEAN,
                    self.loop_save_results)
            self.loop_save_results = self.apply_one_config(*args)

            # Save graphs
            args = (section, 'save graphs', CFG_BOOLEAN, self.loop_save_graphs)
            self.loop_save_graphs = self.apply_one_config(*args)

    # -------------------------------------------------------------------------
    def apply_arduino_config(self):
        """Method to apply the Arduino section options read from the
           .cfg file to the associated object properties
        """
        section = 'Arduino'

        # SPI clock divider
        args = (section, 'spi clock div', CFG_INT, self.spi_clk_div)
        self.spi_clk_div = self.apply_one_config(*args)

        # Max IV points
        args = (section, 'max iv points', CFG_INT, self.max_iv_points)
        self.max_iv_points = self.apply_one_config(*args)

        # Min Isc ADC
        args = (section, 'min isc adc', CFG_INT, self.min_isc_adc)
        self.min_isc_adc = self.apply_one_config(*args)

        # Max Isc poll
        args = (section, 'max isc poll', CFG_INT, self.max_isc_poll)
        self.max_isc_poll = self.apply_one_config(*args)

        # Isc stable ADC
        args = (section, 'isc stable adc', CFG_INT, self.isc_stable_adc)
        self.isc_stable_adc = self.apply_one_config(*args)

        # Max discards
        args = (section, 'max discards', CFG_INT, self.max_discards)
        self.max_discards = self.apply_one_config(*args)

        # Aspect height
        args = (section, 'aspect height', CFG_INT, self.aspect_height)
        self.aspect_height = self.apply_one_config(*args)

        # Aspect width
        args = (section, 'aspect width', CFG_INT, self.aspect_width)
        self.aspect_width = self.apply_one_config(*args)

    # -------------------------------------------------------------------------
    def save_config(self):
        """Method to save preferences and other configuration to the
           .cfg file
        """
        if DEBUG_CONFIG:
            dbg_str = ("save_config: Writing config to " +
                       self.ivs2.cfg_filename)
            self.ivs2.logger.print_and_log(dbg_str)
        # Attempt to open the file for writing
        try:
            with open(self.ivs2.cfg_filename, "wb") as cfg_fp:
                # Write config to file
                self.ivs2.cfg.write(cfg_fp)
        except IOError:
            # Failed to open file for writing
            err_str = "Couldn't open config file for writing"
            self.ivs2.logger.print_and_log(err_str)
            return

        # Copy the file to the output directory unless supressed
        if (not self.suppress_cfg_file_copy and
                (self.loop_save_results or
                 not self.loop_mode_active) and
                self.ivs2.hdd_output_dir is not None and
                os.path.isdir(self.ivs2.hdd_output_dir)):
            self.copy_config_file(self.ivs2.hdd_output_dir)

    # -------------------------------------------------------------------------
    def save_snapshot_config(self):
        """Method to save preferences and other configuration to the
           .cfg file from the snapshot copy
        """
        if DEBUG_CONFIG:
            dbg_str = ("save_snapshot_config: Writing snapshot config to " +
                       self.ivs2.cfg_filename)
            self.ivs2.logger.print_and_log(dbg_str)
        # Attempt to open the file for writing
        try:
            with open(self.ivs2.cfg_filename, "wb") as cfg_fp:
                self.ivs2.cfg_snapshot.write(cfg_fp)
        except IOError:
            # Failed to open file for writing
            err_str = "Couldn't open config file for writing"
            self.ivs2.logger.print_and_log(err_str)

    # -------------------------------------------------------------------------
    def copy_config_file(self, dir):
        """Method to copy the current .cfg file to the specified directory
        """
        if os.path.dirname(self.ivs2.cfg_filename) == dir:
            # Return without doing anything if the property is already
            # pointing to the specified directory
            return
        if DEBUG_CONFIG:
            dbg_str = ("copy_config_file: Copying config from " +
                       self.ivs2.cfg_filename + " to " + dir)
            self.ivs2.logger.print_and_log(dbg_str)
        try:
            shutil.copy(self.ivs2.cfg_filename, dir)
        except shutil.Error as e:
            err_str = "Couldn't copy config file to " + dir
            err_str += " ({})".format(e)
            self.ivs2.logger.print_and_log(err_str)

    # -------------------------------------------------------------------------
    def populate_config(self):
        """Method to populate the ConfigParser object from the current
           property values
        """
        # General config
        section = "General"
        self.ivs2.cfg.add_section(section)
        self.ivs2.cfg_set(section, 'x pixels', self.ivs2.x_pixels)

        # USB port config
        section = "USB"
        self.ivs2.cfg.add_section(section)
        self.ivs2.cfg_set(section, 'port', self.ivs2.usb_port)
        self.ivs2.cfg_set(section, 'baud', self.ivs2.usb_baud)

        # Calibration
        section = "Calibration"
        self.ivs2.cfg.add_section(section)
        self.ivs2.cfg_set(section, 'voltage', self.ivs2.v_cal)
        self.ivs2.cfg_set(section, 'current', self.ivs2.i_cal)

        # Plotting config
        section = "Plotting"
        self.ivs2.cfg.add_section(section)
        self.ivs2.cfg_set(section, 'plot power', self.ivs2.plot_power)
        self.ivs2.cfg_set(section, 'fancy labels', self.ivs2.fancy_labels)
        self.ivs2.cfg_set(section, 'linear', self.ivs2.linear)
        self.ivs2.cfg_set(section, 'font scale', self.ivs2.font_scale)
        self.ivs2.cfg_set(section, 'line scale', self.ivs2.line_scale)
        self.ivs2.cfg_set(section, 'point scale', self.ivs2.point_scale)
        self.ivs2.cfg_set(section, 'correct adc', self.ivs2.correct_adc)

        # Looping config
        section = "Looping"
        self.ivs2.cfg.add_section(section)
        self.ivs2.cfg_set(section, 'restore values', self.restore_loop)
        self.ivs2.cfg_set(section, 'loop mode', self.loop_mode_active)
        self.ivs2.cfg_set(section, 'rate limit', self.loop_rate_limit)
        self.ivs2.cfg_set(section, 'delay', self.loop_delay)
        self.ivs2.cfg_set(section, 'save results', self.loop_save_results)
        self.ivs2.cfg_set(section, 'save graphs', self.loop_save_graphs)

        # Arduino config
        section = "Arduino"
        self.ivs2.cfg.add_section(section)
        self.ivs2.cfg_set(section, 'spi clock div', self.spi_clk_div)
        self.ivs2.cfg_set(section, 'max iv points', self.max_iv_points)
        self.ivs2.cfg_set(section, 'min isc adc', self.min_isc_adc)
        self.ivs2.cfg_set(section, 'max isc poll', self.max_isc_poll)
        self.ivs2.cfg_set(section, 'isc stable adc', self.isc_stable_adc)
        self.ivs2.cfg_set(section, 'max discards', self.max_discards)
        self.ivs2.cfg_set(section, 'aspect height', self.aspect_height)
        self.ivs2.cfg_set(section, 'aspect width', self.aspect_width)

    # -------------------------------------------------------------------------
    def attempt_arduino_handshake(self):
        """This method is a 'best-effort' attempt to reset the Arduino
        and perform the initial handshake when the GUI comes up. If this
        succeeds, there will be no delay when the go button is pressed
        for the first time. If it fails, it might be because the IVS2
        hardware is not connected yet, which isn't a requirement, so it
        should fail silently. In that case, it retries itself once a
        second.  If and when the IVS2 hardware is connected, it will
        bring up the interface.
        """
        # Bail out now if Arduino ready flag is set
        if self.ivs2.arduino_ready:
            self.go_button['text'] = "Swing!"
            return

        # Find new serial ports, if any
        old_serial_ports = self.ivs2.serial_ports
        self.ivs2.find_serial_ports()
        if old_serial_ports != self.ivs2.serial_ports:
            self.ivs2.find_arduino_port()
            # If the list of serial ports changed, we need to update the
            # list for the USB Port menu. Simplest way is to just
            # destroy and re-create the whole menu bar.
            self.menu_bar.destroy()
            self.create_menu_bar()

        if self.ivs2.usb_port is not None:
            self.go_button['text'] = "Not Ready"
            self.go_button.state(['disabled'])
            self.update_idletasks()
            # Reset Arduino
            rc = self.ivs2.reset_arduino()
            if rc == RC_SUCCESS:
                # Wait for Arduino ready message
                rc = self.ivs2.wait_for_arduino_ready_and_ack()
                if rc == RC_SUCCESS:
                    self.go_button['text'] = "Swing!"
                    self.go_button.state(['!disabled'])
                    if self.ivs2.cfg.get('USB', 'port') != self.ivs2.usb_port:
                        self.ivs2.cfg_set('USB', 'port', self.ivs2.usb_port)
                        self.save_config()
                    return

        # If any of the above failed, try again in 1 second
        self.after(1000, lambda: self.attempt_arduino_handshake())

    # -------------------------------------------------------------------------
    def update_img_size(self, event=None):
        res_str = self.resolution_str.get()

        # The first number in the input is x_pixels
        res_re = re.compile('(\d+)')
        match = res_re.search(res_str)
        if match:
            # Use x_pixels, calculate y_pixels
            x_pixels = int(match.group(1))
            y_pixels = int(round(x_pixels *
                                 self.ivs2.plot_y_inches /
                                 self.ivs2.plot_x_inches))
            new_res_str = str(x_pixels) + "x" + str(y_pixels)
            self.ivs2.logger.log("New resolution: " + new_res_str)
            # Set the resolution string to the new value
            self.resolution_str.set(new_res_str)
            # Set the x_pixels property of the IVS2 object to the new value
            self.ivs2.x_pixels = x_pixels
            # Update config
            self.ivs2.cfg_set('General', 'x pixels', self.ivs2.x_pixels)
            # Update style and recreate go_button
            self.set_style()
            curr_go_txt = self.go_button['text']
            self.go_button.destroy()
            self.create_go_button(text=curr_go_txt)
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
            new_res_str = str(x_pixels) + "x" + str(y_pixels)
            self.ivs2.logger.log("Keeping old resolution: " + new_res_str)
            self.resolution_str.set(new_res_str)
        event.widget.selection_clear()  # remove annoying highlight
        event.widget.tk_focusNext().focus()  # move focus out so Return works

    # -------------------------------------------------------------------------
    def get_curr_x_pixels(self):
        res_str = self.resolution_str.get()
        res_re = re.compile('(\d+)')
        match = res_re.search(res_str)
        x_pixels = int(match.group(1))
        return x_pixels

    # -------------------------------------------------------------------------
    def redisplay_img(self, reprocess_adc=False):
        # If we're still displaying a splash screen, update it to
        # the new size. If an IV curve is showing, regenerate it..
        if self.img_pane.splash_img_showing:
            self.img_pane.display_splash_img()
        elif (self.overlay_mode):
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
                self.ivs2.plot_title = self.plot_title
                self.ivs2.plot_results()
                self.display_img(self.ivs2.current_img)
            if remove_directory:
                if self.ivs2.hdd_output_dir == os.getcwd():
                    os.chdir("..")
                shutil.rmtree(self.ivs2.hdd_output_dir)
            else:
                self.clean_up_files(self.ivs2.hdd_output_dir,
                                    loop_mode=False)
        # Save the config
        self.save_config()

    # -------------------------------------------------------------------------
    def show_preferences(self, event=None):
        # Create the Preferences dialog
        PreferencesDialog(self)

        # FIXME: There's a weird bug where the button takes its "pressed"
        # appearance and never turns back to its normal appearance when the
        # dialog is closed. The current workaround is to re-create the button
        # (actually the whole box containing both buttons) and then destroy the
        # previous button box. Another workaround is to use
        # "self.wait_window(self)" to block this method from ever returning,
        # but it is not understood why that works, and it doesn't seem like a
        # great idea.
        self.recreate_prefs_results_button_box()

    # -------------------------------------------------------------------------
    def results_actions(self, event=None):
        if self.results_button.instate(['disabled']):
            # Mystery why this is necessary ...
            return
        self.results_wiz = ResultsWizard(self)

    # -------------------------------------------------------------------------
    def go_actions(self, event=None):
        if self.go_button.instate(['disabled']):
            # Mystery why this is necessary ...
            return

        if (event.widget == self.img_size_combo or
                event.widget == self.v_range_entry or
                event.widget == self.i_range_entry):
            # When Return key is hit in any of these widgets, it's to
            # change their value, so bail out without doing anything
            return

        # Change button to "pressed" appearance
        self.go_button.state(['pressed'])
        self.update_idletasks()

        # Swing the IV curve, possibly looping
        rc = self.swing_loop(loop_mode=self.loop_mode.get() == "On",
                             first_loop=True)
        if rc == RC_SERIAL_EXCEPTION:
            self.reestablish_arduino_comm()

        # Enable calibration
        if rc == RC_SUCCESS:
            self.menu_bar.enable_calibration()

        # Restore button to "unpressed" appearance
        self.go_button.state(['!pressed'])

    # -------------------------------------------------------------------------
    def reestablish_arduino_comm(self):
        self.ivs2.arduino_ready = False
        self.attempt_arduino_handshake()

    # -------------------------------------------------------------------------
    def swing_loop(self, loop_mode=False, first_loop=False):
        """This method invokes the IVS2 object method to swing the IV
        curve, and then it displays the generated GIF in the image
        pane. In loop mode it ends by scheduling another call of itself
        after the programmed delay. In that sense it appears to be a
        loop. Unlike an actual loop, however, it is non-blocking.  This
        is essential in order for the GUI not to lock up.
        """
        # Capture the start time
        loop_start_time = dt.datetime.now()

        # Add the stop button if needed. Also disable the loop mode
        # checkbuttons.
        self.swing_loop_id = None
        if loop_mode and first_loop:
            self.add_stop_button()
            self.loop_mode_cb.state(['disabled'])
            self.loop_rate_cb.state(['disabled'])
            self.loop_save_cb.state(['disabled'])

        # Allow copying the .cfg file to the run directory
        self.suppress_cfg_file_copy = False

        # Call the IVS2 method to swing the curve
        if loop_mode and (not self.loop_save_results or
                          not self.loop_save_graphs):
            self.ivs2.generate_pdf = False
        rc = self.ivs2.swing_iv_curve(loop_mode=loop_mode,
                                      first_loop=first_loop)
        self.ivs2.generate_pdf = True

        # Return without generating graphs if it failed, displaying
        # reason in a dialog
        if rc != RC_SUCCESS:
            if rc == RC_BAUD_MISMATCH:
                self.show_baud_mismatch_dialog()
            if rc == RC_TIMEOUT:
                self.show_timeout_dialog()
            if rc == RC_SERIAL_EXCEPTION:
                self.show_serial_exception_dialog()
            if rc == RC_ZERO_VOC:
                self.show_zero_voc_dialog()
            if rc == RC_ZERO_ISC:
                self.show_zero_isc_dialog()
            if loop_mode:
                self.stop_actions(event=None)
            self.clean_up_after_failure(self.ivs2.hdd_output_dir)
            return rc

        # Update the image pane with the new curve GIF
        self.display_img(self.ivs2.current_img)

        # Schedule another call with "after" if looping
        if loop_mode:
            elapsed_time = dt.datetime.now() - loop_start_time
            elapsed_ms = int(round(elapsed_time.total_seconds() * 1000))
            delay_ms = self.loop_delay * 1000 - elapsed_ms
            if not self.loop_rate_limit or delay_ms <= 0:
                delay_ms = 1
            id = self.after(delay_ms,
                            lambda: self.swing_loop(loop_mode=True,
                                                    first_loop=False))
            # Captured id is used to cancel when stop button is pressed
            self.swing_loop_id = id

        # Save the config to capture current max x,y values
        self.save_config()

        # Clean up files, depending on mode and options
        self.clean_up_files(self.ivs2.hdd_output_dir, loop_mode)

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def display_img(self, img_file):
        self.img_file = img_file
        new_img = tk.PhotoImage(file=img_file)
        self.img_pane.configure(image=new_img)
        self.img_pane.image = new_img
        self.img_pane.splash_img_showing = False
        # Update values in range boxes
        self.update_axis_ranges()
        self.update_idletasks()

    # -------------------------------------------------------------------------
    def clean_up_after_failure(self, dir):
        """Method to remove the run directory after a failed run if it contains
           fewer than two files (which would be the ADC CSV file and
           the data points CSV file)
        """
        files = glob.glob(dir + '/*')
        if len(files) < 2:
            for f in files:
                self.clean_up_file(f)
            if dir == os.getcwd():
                os.chdir("..")
            os.rmdir(dir)
            msg_str = "Removed " + dir
            self.ivs2.logger.log(msg_str)

    # -------------------------------------------------------------------------
    def clean_up_files(self, dir, loop_mode=False):
        # Return without doing anything if directory doesn't exist
        if not os.path.exists(dir):
            return

        # Always remove the plt_ file(s)
        plt_files = glob.glob(dir + '/plt_*')
        for f in plt_files:
            self.clean_up_file(f)

        # Always remove the PNG file(s)
        png_files = glob.glob(dir + '/*.png')
        for f in png_files:
            self.clean_up_file(f)

        # Selectively remove other files in loop mode
        if loop_mode:
            if not self.loop_save_results:
                # Remove all files in loop directory
                loop_files = glob.glob(dir + '/*')
                for f in loop_files:
                    self.clean_up_file(f)
                # Remove the (now empty) directory
                if dir == os.getcwd():
                    os.chdir("..")
                os.rmdir(dir)

            elif not self.loop_save_graphs:
                # Remove GIF only
                self.clean_up_file(self.ivs2.current_img)

    # -------------------------------------------------------------------------
    def clean_up_file(self, f):
            os.remove(f)
            msg_str = "Removed " + f
            self.ivs2.logger.log(msg_str)

    # -------------------------------------------------------------------------
    def add_stop_button(self):
        """This method creates the stop button. The stop button is only
        created when we're in loop mode. Its size and location are
        the same as the go button, so it just covers up the go
        button (from the user's point of view it just looks like
        the label on the button changes). When the stop button is
        pressed, the looping is stopped, and the button is
        removed.

        """
        self.stop_button = GoStopButton(master=self, text='STOP')
        self.stop_button['width'] = self.go_button['width']
        # Tooltip
        tt_text = "Press button to stop looping"
        Tooltip(self.stop_button, text=tt_text, **BOT_TT_KWARGS)
        self.stop_button.bind('<Button-1>', self.stop_actions)
        self.root.bind('<Return>', self.stop_actions)
        self.root.bind('<space>', self.stop_actions)
        self.stop_button.grid(**self.grid_args['go_button'])
        self.update_idletasks()

    # -------------------------------------------------------------------------
    def stop_actions(self, event=None):
        # Restore normal bindings of return key and space bar
        self.root.bind('<Return>', self.go_actions)
        self.root.bind('<space>', self.go_actions)

        # Cancel scheduled swing loop
        if self.swing_loop_id is not None:
            self.after_cancel(self.swing_loop_id)

        # Remove the stop button
        self.stop_button.destroy()

        # Re-enable loop checkbuttons
        self.loop_mode_cb.state(['!disabled'])
        self.loop_rate_cb.state(['!disabled'])
        self.loop_save_cb.state(['!disabled'])

    # -------------------------------------------------------------------------
    def show_baud_mismatch_dialog(self):
        baud_mismatch_str = """
ERROR: Decode error on serial data from
Arduino

This is mostly likely a baud rate
mismatch. The baud rate is hardcoded in
the Arduino sketch, and this must match
the rate specified in Preferences.
"""
        tkmsg.showinfo(message=baud_mismatch_str)

    # -------------------------------------------------------------------------
    def show_timeout_dialog(self):
        timeout_str = """
ERROR: Timed out waiting for message
from Arduino

Check that the IV Swinger 2 is connected
to a USB port and the green LED on the
Arduino is lit.

Check that the correct port is selected
on the "USB Port" menu.
"""
        tkmsg.showinfo(message=timeout_str)

    # -------------------------------------------------------------------------
    def show_serial_exception_dialog(self):
        serial_exception_str = """
ERROR: problem opening USB port to
communicate with Arduino

Check that the IV Swinger 2 is connected
to a USB port and the green LED on the
Arduino is lit.

Check that the correct port is selected
on the "USB Port" menu.
"""
        tkmsg.showinfo(message=serial_exception_str)

    # -------------------------------------------------------------------------
    def show_zero_voc_dialog(self):
        zero_voc_str = """
ERROR: Voc is zero volts

Check that the IV Swinger 2 is connected
properly to the PV module
"""
        tkmsg.showinfo(message=zero_voc_str)

    # -------------------------------------------------------------------------
    def show_zero_isc_dialog(self):
        zero_isc_str = """
ERROR: Isc is zero amps

Check that the IV Swinger 2 is connected
properly to the PV module
"""
        tkmsg.showinfo(message=zero_isc_str)

    # -------------------------------------------------------------------------
    def sys_view_file(self, file):
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

    # -------------------------------------------------------------------------
    def start_on_top(self):
        # Causes app to open on top of existing windows
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after_idle(self.root.attributes, '-topmost', False)

    # -------------------------------------------------------------------------
    def start_centered(self):
        # Causes app to open centered (side-to-side) on screen, aligned to top
        self.root.geometry('+%d+0' % ((self.root.winfo_screenwidth()/2) -
                                      (self.ivs2.x_pixels/2)))

    # -------------------------------------------------------------------------
    def start_to_right(self):
        # Causes app to open to the right of the screen (with 20
        # pixels left), aligned to top
        self.root.geometry('+%d+0' % (self.root.winfo_screenwidth() -
                                      self.ivs2.x_pixels - 20))

    # -------------------------------------------------------------------------
    def start_to_left(self):
        # Causes app to open to the left of the screen (with 20
        # pixels left), aligned to top
        self.root.geometry('+20+0')

    # -------------------------------------------------------------------------
    def close_gui(self):
        # Clean up before closing
        if self.overlay_dir is not None:
            self.clean_up_files(self.overlay_dir)
        if self.ivs2.hdd_output_dir is not None:
            self.clean_up_files(self.ivs2.hdd_output_dir)
        IV_Swinger.IV_Swinger.close_plots()
        self.root.destroy()

    # -------------------------------------------------------------------------
    def start(self):
        self.start_on_top()
        self.root.protocol("WM_DELETE_WINDOW", self.close_gui)
        self.root.mainloop()


# Image size combobox class
#
class ImgSizeCombo(ttk.Combobox):
    """Combobox used to select image size"""

    # Initializer
    def __init__(self, master=None, textvariable=None):
        ttk.Combobox.__init__(self, master=master, textvariable=textvariable)
        y_pixels = int(round(master.ivs2.x_pixels *
                             master.ivs2.plot_y_inches /
                             master.ivs2.plot_x_inches))
        curr_size = (str(master.ivs2.x_pixels) + "x" + str(y_pixels))
        textvariable.set(curr_size)
        self['values'] = ('550x425',
                          '750x580',
                          '971x750',
                          '1085x838',
                          '1100x850')
        self['width'] = 10


# Results wizard class
#
class ResultsWizard(tk.Toplevel):
    """Results wizard class. Unlike other dialogs that are extensions of
       the generic Dialog class, this is NOT a 'modal window', so it
       does not completely block access to the main window. This is so
       the user can still do things like changing preferences. However,
       certain actions are disallowed in the main window such as the Go
       button and the Results Wizard button since allowing those
       actions while the results wizard is open is not useful or at
       least the expected behavior if they were allowed is not obvious.
    """
    # Initializer
    def __init__(self, master=None):
        tk.Toplevel.__init__(self, master=master)
        self.title("Results Wizard")
        self.results_dir = self.master.ivs2.app_data_dir
        self.copy_dest = None
        self.selected_csv_files = []
        self.overlay_img = None
        self.overlay_iid = None
        self.overlay_title = None
        self.master = master

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
        self.master.results_button.state(['disabled'])
        self.master.go_button.state(['disabled'])
        self.master.menu_bar.disable_calibration()

    # -------------------------------------------------------------------------
    def change_min_height(self, min_height):
        """Method to change the minimum height of the dialog to the specified
        value
        """
        # Get current window width
        width = self.master.get_dialog_width(self)

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
        copy_button = ttk.Button(self.right_buttonbox,
                                 text="Copy",
                                 width=width,
                                 command=self.copy_selected)

        # Add button tooltips
        tt_text = "Expand all date groupings"
        Tooltip(expand_button, text=tt_text,  **TOP_TT_KWARGS)
        tt_text = "Collapse all date groupings"
        Tooltip(collapse_button, text=tt_text, **TOP_TT_KWARGS)
        tt_text = "Change the title of the current plot"
        Tooltip(title_button, text=tt_text,  **TOP_TT_KWARGS)
        tt_text = "Combine up to 8 curves on the same plot"
        Tooltip(overlay_button, text=tt_text,  **TOP_TT_KWARGS)
        tt_text = "Open the PDF in a viewer"
        Tooltip(pdf_button, text=tt_text,  **TOP_TT_KWARGS)
        tt_text = ("Apply current plotting options (including size) to all "
                   "selected runs.  IMPORTANT: Select runs BEFORE making "
                   "changes to plotting options.")
        Tooltip(update_button, text=tt_text,  **TOP_TT_KWARGS)
        tt_text = "Copy one or more runs or overlays to USB or elsewhere"
        Tooltip(copy_button, text=tt_text,  **TOP_TT_KWARGS)

        # Pack buttons into containing box
        expand_button.pack()
        collapse_button.pack()
        title_button.pack()
        overlay_button.pack()
        pdf_button.pack()
        update_button.pack()
        copy_button.pack()

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
        self.tree = ttk.Treeview(self.treebox, selectmode='extended')
        self.treescroll = ttk.Scrollbar(self.treebox, command=self.tree.yview)
        self.tree.configure(yscroll=self.treescroll.set)
        self.tree.bind('<<TreeviewSelect>>', self.select)
        self.populate_tree()
        tt_text = ("Click on path at the top to change. Shift-click and "
                   "Control-click can be used to selected multiple runs "
                   "for copying or overlaying.")
        Tooltip(self.tree, text=tt_text, **TOP_TT_KWARGS)
        self.tree.pack(side=LEFT)
        self.treescroll.pack(side=LEFT, fill=Y)

    # -------------------------------------------------------------------------
    def populate_tree(self):
        """Method to populate the Treeview. The top level is the date, and each
        of those can be opened (expanded) to see the runs from that day.
        There is also a top level item for the overlays, and it has all
        of the overlays under it.
        """
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
            if subdir == 'overlays':
                self.populate_overlays(subdir)

            # Then filter out anything that isn't a directory in the
            # canonical date/time string format - these are the runs
            if IV_Swinger.DateTimeStr.is_date_time_str(subdir):
                self.populate_runs(subdir)

        # If there are no overlays or run directories, insert a dummy item
        if not self.tree.exists('overlays') and not len(self.dates):
            self.tree.insert('', 'end', 'err_msg', text='NO RUNS HERE')

        # Configure a large height so it is never shorter than the
        # window
        self.tree.configure(height=WIZARD_TREE_HEIGHT)

        # Configure the column width to be large enough for a fairly
        # long path in the heading
        self.tree.column('#0', width=WIZARD_TREE_WIDTH)
        self.tree.heading('#0', text=self.results_dir,
                          command=self.change_folder)
        self.update_idletasks()

    # -------------------------------------------------------------------------
    def populate_overlays(self, subdir):
        """Method to populate the overlays part of the Treeview.
        """
        # Add overlays parent to Treeview if it doesn't already exist
        if not self.tree.exists(subdir):
            self.tree.insert('', 0, subdir, text="Overlays")

        # Get a list of the overlay subdirectories, newest first
        overlays = sorted(os.listdir(os.path.join(self.results_dir, subdir)),
                          reverse=True)

        # Step through them
        for overlay in overlays:
            # Full path
            overlay_dir = os.path.join(self.results_dir, subdir, overlay)

            # Then filter out anything that isn't a directory in the
            # canonical date/time string format - these are the overlays
            if (IV_Swinger.DateTimeStr.is_date_time_str(overlay) and
                    os.path.isdir(overlay_dir)):

                # Skip empty directories
                if not os.listdir(overlay_dir):
                    continue

                # Translate to human readable date and time
                xlated = IV_Swinger.DateTimeStr.xlate_date_time_str(overlay)
                (xlated_date, xlated_time) = xlated

                # Add to tree
                iid = "overlay_" + overlay
                text = ("Created on " + xlated_date + " at " +
                        xlated_time)
                self.tree.insert(subdir, 'end', iid, text=text)

    # -------------------------------------------------------------------------
    def populate_runs(self, subdir):
        """Method to populate the runs part of the Treeview.
        """
        # Translate to human readable date and time
        xlated = IV_Swinger.DateTimeStr.xlate_date_time_str(subdir)
        (xlated_date, xlated_time) = xlated
        date = subdir.split('_')[0]

        # Add a date item (parent to time items) if it doesn't already
        # exist
        if not self.tree.exists(date):
            self.tree.insert('', 'end', date, text=xlated_date)
            # Add it to the list of all dates for the expand_all
            # and collapse_all methods
            self.dates.append(date)

        # Add child time item (iid is full date_time_str)
        self.tree.insert(date, 'end', subdir, text=xlated_time)

    # -------------------------------------------------------------------------
    def done(self, event=None):
        """Method called when wizard is closed
        """
        # If we're in overlay mode ask user if they want to save the
        # overlay
        if self.master.overlay_mode:
            msg_str = "Save overlay before quitting Results Wizard?"
            save_overlay = tkmsg.askyesno("Save overlay?", msg_str,
                                          default=tkmsg.NO)
            if save_overlay:
                # Yes: same as if Finished button had been pressed
                self.overlay_finished(event=None)
                return
            else:
                # No: turn off overlay mode and display non-overlaid
                # image
                self.master.overlay_mode = False
                self.overlay_title = None
                self.master.redisplay_img()
        # Remove incomplete overlay
        self.rm_overlay_if_unfinished()
        self.restore_master()
        self.destroy()

    # -------------------------------------------------------------------------
    def restore_master(self):
        """Method to restore focus to the master, re-enable its widgets that
           were disabled while the wizard was open, and restore the
           original configuration
        """
        self.master.focus_set()
        self.master.results_button.state(['!disabled'])
        self.master.go_button.state(['!disabled'])
        self.master.ivs2.cfg_filename = None  # property will restore
        self.master.get_config()
        self.master.update_plot_power_cb()
        # If the user has explicitly checked the Lock checkbutton, keep
        # the axes locked to the values from the last result that was
        # browsed. Otherwise unlock the axes.
        if self.master.axes_locked.get() == "Unlock":
            self.unlock_axes()

    # -------------------------------------------------------------------------
    def unlock_axes(self):
        """Method to unlock the axes"""
        self.master.ivs2.plot_lock_axis_ranges = False
        self.master.ivs2.plot_max_x = None
        self.master.ivs2.plot_max_y = None
        self.master.range_lock_cb.update_axis_lock(None)
        self.master.axes_locked.set("Unlock")

    # -------------------------------------------------------------------------
    def select(self, event=None):
        """Method to handle a select event from the Treeview"""
        selections = self.tree.selection()
        if not len(selections):
            return
        # If multiple items are selected, last one (oldest) is
        # displayed
        selection = selections[-1]
        if self.master.overlay_mode:
            self.overlay_runs(event=None)
        elif selection.startswith('overlay_'):
            self.overlay_select_actions(selection)
        elif IV_Swinger.DateTimeStr.is_date_time_str(selection):
            self.non_overlay_select_actions(selection)

    # -------------------------------------------------------------------------
    def overlay_select_actions(self, selection):
        """Method to display an existing overlay and perform related actions
        """
        dts = IV_Swinger.DateTimeStr.extract_date_time_str(selection)
        overlay_dir = os.path.join(self.results_dir, 'overlays', dts)
        gif_leaf_name = ("overlaid_" + dts + ".gif")
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
        if csv_data_point_file is None:
            return

        # If GIF file exists, display it now
        gif_exists = False
        if os.path.exists(gif_file):
            self.master.display_img(gif_file)
            gif_exists = True

        # Prepare IVS2 object for regeneration of plot with modified
        # options
        self.prep_ivs2_for_redisplay(run_dir, adc_csv_file)

        # If config file exists, read it in and update the config
        self.update_to_selected_config(run_dir)

        # If GIF file doesn't exist, generate it from data point CSV
        # file and display it
        if not gif_exists:
            self.master.img_pane.splash_img_showing = False
            self.master.redisplay_img(reprocess_adc=False)

    # -------------------------------------------------------------------------
    def get_run_dir(self, selection):
        """Method to determine the path to the run directory for the selection
           and check that it is really a directory
        """
        run_dir = os.path.join(self.results_dir, selection)
        if not os.path.isdir(run_dir):
            err_str = "ERROR: directory " + run_dir + " does not exist"
            self.master.ivs2.logger.print_and_log(err_str)
            tkmsg.showinfo(message=err_str)
            return None
        return run_dir

    # -------------------------------------------------------------------------
    def get_csv_and_gif_names(self, run_dir, selection):
        """Method to determine the full paths to the two CSV files and the GIF
           file based on the run directory and the selection. Also
           checks that the data point CSV file exists
        """
        self.master.ivs2.get_csv_filenames(run_dir, selection)
        csv_data_point_file = self.master.ivs2.hdd_csv_data_point_filename
        adc_csv_file = self.master.ivs2.hdd_adc_pairs_csv_filename
        gif_leaf_name = (self.master.ivs2.file_prefix + selection + ".gif")
        gif_file = os.path.join(run_dir, gif_leaf_name)

        # Check that data point CSV file exists (others are optional)
        if not os.path.exists(csv_data_point_file):
            # Check for IVS1 CSV file
            ivs1_csv_file = os.path.join(self.results_dir, selection,
                                         "data_points_" + selection + ".csv")
            if os.path.exists(ivs1_csv_file):
                csv_data_point_file = ivs1_csv_file
                self.master.ivs2.hdd_csv_data_point_filename = ivs1_csv_file
            else:
                err_str = ("ERROR: file " + csv_data_point_file +
                           " does not exist")
                self.master.ivs2.logger.print_and_log(err_str)
                tkmsg.showinfo(message=err_str)
                return (None, None, None)

        return (csv_data_point_file, adc_csv_file, gif_file)

    # -------------------------------------------------------------------------
    def prep_ivs2_for_redisplay(self, run_dir, adc_csv_file):
        """Method to prepare IVS2 object for regeneration of plot with modified
           options
        """
        self.master.ivs2.hdd_output_dir = run_dir
        self.master.ivs2.plot_title = None
        if os.path.exists(adc_csv_file):
            adc_pairs = self.master.get_adc_pairs_from_csv(adc_csv_file)
            self.master.ivs2.adc_pairs = adc_pairs
        else:
            self.master.ivs2.adc_pairs = None

    # -------------------------------------------------------------------------
    def update_to_selected_config(self, run_dir):
        """Method to read config file, if it exists, and update the config
        """
        cfg_file = os.path.join(run_dir, APP_NAME + ".cfg")
        if cfg_file == self.master.ivs2.cfg_filename:
            return
        if os.path.exists(cfg_file):
            self.master.get_old_result_config(cfg_file)
            self.master.update_plot_power_cb()
            self.master.update_axis_ranges()
            # Change the IVS2 object config file property to point to
            # this one
            self.master.ivs2.cfg_filename = cfg_file
            # Clear flag to suppress copying the .cfg file
            self.master.suppress_cfg_file_copy = False
        else:
            # Indicate that axis ranges are unknown
            self.master.v_range.set("<unknown>")
            self.master.i_range.set("<unknown>")
            # Set flag to suppress copying the .cfg file if there
            # wasn't already one in this directory
            self.master.suppress_cfg_file_copy = True

    # -------------------------------------------------------------------------
    def change_folder(self, event=None):
        """Method to handle the change folder event (click on treeview column
           heading)
        """
        options = {}
        options['initialdir'] = self.results_dir
        options['parent'] = self.master
        options['title'] = 'Choose Folder'
        if sys.platform == 'darwin':
            options['message'] = options['title']
        dir = tkFileDialog.askdirectory(**options)
        if len(dir):
            self.results_dir = dir
            self.delete_all()
            self.populate_tree()

    # -------------------------------------------------------------------------
    def delete_all(self):
        """Method to delete all items from the Treeview"""
        self.tree.delete(*self.tree.get_children())

    # -------------------------------------------------------------------------
    def expand_all(self, event=None):
        """Method to expand/open all Treeview date groupings (click on
        button)
        """
        for date in self.dates:
            self.tree.item(date, open=True)

    # -------------------------------------------------------------------------
    def collapse_all(self, event=None):
        """Method to collapse/close all Treeview date groupings (click on
        button)
        """
        for date in self.dates:
            self.tree.item(date, open=False)

    # -------------------------------------------------------------------------
    def get_copy_dest(self):
        """Method to get the copy destination from the user
        """
        # Open a tkFileDialog to get user to choose a destination
        options = {}
        options['parent'] = self.master
        options['title'] = 'Choose Copy Destination'
        if sys.platform == 'darwin':
            options['message'] = options['title']
        self.copy_dest = tkFileDialog.askdirectory(**options)
        if self.copy_dest is '':  # Cancel
            return RC_FAILURE

        # If leaf directory is named IV_Swinger2, assume the user meant
        # to choose its parent directory
        if os.path.basename(self.copy_dest) == APP_NAME:
            self.copy_dest = os.path.dirname(self.copy_dest)

        # Check that it is writeable
        if not os.access(self.copy_dest, os.W_OK | os.X_OK):
            err_str = "ERROR: " + self.copy_dest + " is not writeable"
            tkmsg.showinfo(message=err_str)
            return RC_FAILURE

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def copy_selected(self, event=None):
        """Method to copy the selected runs and/or overlays (to a USB drive or
        elsewhere)
        """
        # Get the selected run(s) from the Treeview
        selected_runs = self.get_selected_runs()

        # Get the selected overlay(s) from the Treeview
        selected_overlays = self.get_selected_overlays()

        # Display error dialog and return if nothing is selected
        if not len(selected_runs) and not len(selected_overlays):
            tkmsg.showinfo(message="ERROR: no runs or overlays are selected")
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
            individual_run = IV_Swinger.DateTimeStr.is_date_time_str(selection)
            is_date_group = re.compile('^(\d{6})$').search(selection)
            if individual_run:
                selected_runs.append(os.path.join(self.results_dir, selection))
            elif (include_whole_days and is_date_group and not
                  (IV_Swinger.DateTimeStr.is_date_time_str(selections[0]) or
                   IV_Swinger.DateTimeStr.is_date_time_str(selections[-1]))):
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
            # Add all of the overlays if the whole groups is selected,
            # but not if the last selection is an individual overlay
            # (DWIM)
            if (selection == 'overlays' and
                    not selections[-1].startswith('overlay_')):
                for child in self.tree.get_children(selection):
                    # Add all the overlays to the list
                    dts = IV_Swinger.DateTimeStr.extract_date_time_str(child)
                    selected_overlays.append(os.path.join(self.results_dir,
                                                          'overlays', dts))
            # Add individual overlay
            if selection.startswith('overlay_'):
                dts = IV_Swinger.DateTimeStr.extract_date_time_str(selection)
                selected_overlays.append(os.path.join(self.results_dir,
                                                      'overlays', dts))

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
            if os.path.exists(dest_dir):
                existing_dest_dirs.append(dest_dir)

        if len(existing_dest_dirs):
            if len(existing_dest_dirs) > 10:
                # If more than 10 found, just prompt with the count found
                msg_str = (str(len(existing_dest_dirs)) +
                           " folders to be copied exist in " +
                           os.path.join(self.copy_dest, APP_NAME) + "\n")
            else:
                # If 1-10 found, prompt with the list of names
                msg_str = "The following destination folder(s) exist(s):\n"
                for dest_dir in existing_dest_dirs:
                    msg_str += "  " + dest_dir + "\n"
            msg_str += "\nOverwrite all?"
            overwrite = tkmsg.askyesno("Overwrite all?", msg_str,
                                       default=tkmsg.NO)
        return overwrite

    # -------------------------------------------------------------------------
    def copy_dirs(self, src_dirs, overwrite):
        """Method to copy the specified directories to the destination,
        overwriting or not, based on input parameter. Returns number of
        runs copied.
        """
        num_copied = {'overlays': 0, 'runs': 0}
        for src_dir in src_dirs:
            dest_dir = self.get_dest_dir(src_dir)
            if os.path.exists(dest_dir):
                if overwrite:
                    try:
                        shutil.rmtree(dest_dir)
                    except (IOError, OSError, shutil.Error) as e:
                        err_str = ("ERROR: removing " + dest_dir +
                                   "({})".format(e))
                        tkmsg.showinfo(message=err_str)
                        continue
                else:
                    continue
            try:
                shutil.copytree(src_dir, dest_dir)
                if os.path.basename(os.path.dirname(src_dir)) == 'overlays':
                    num_copied['overlays'] += 1
                else:
                    num_copied['runs'] += 1
                self.master.ivs2.logger.log("Copied " + src_dir +
                                            " to " + dest_dir)
            except (IOError, OSError, shutil.Error) as e:
                err_str = ("ERROR: error copying " + src_dir +
                           " to " + dest_dir + "\n" +
                           "({})".format(e))
                tkmsg.showinfo(message=err_str)

        return num_copied

    # -------------------------------------------------------------------------
    def get_dest_dir(self, src_dir):
        """Method to derive the destination directory name from the source
        directory name
        """
        if os.path.basename(os.path.dirname(src_dir)) == 'overlays':
            dest_dir = os.path.join(self.copy_dest, APP_NAME,
                                    'overlays', os.path.basename(src_dir))
        else:
            dest_dir = os.path.join(self.copy_dest, APP_NAME,
                                    os.path.basename(src_dir))
        return dest_dir

    # -------------------------------------------------------------------------
    def display_copy_summary(self, num_copied):
        """Method to display a message dialog with a count of how many runs
        were copied
        """
        msg_str = 'Copied:\n'
        msg_str += "   " + str(num_copied['overlays']) + " overlays\n"
        msg_str += "   " + str(num_copied['runs']) + " runs\n"
        msg_str += "to " + os.path.join(self.copy_dest, APP_NAME) + "\n"
        tkmsg.showinfo(message=msg_str)

    # -------------------------------------------------------------------------
    def change_title(self, event=None):
        """Method to change the title of the selected run or of the current
           overlay
        """
        prompt_str = "Enter new title"
        if self.master.overlay_mode:
            run_str = str(len(self.overlaid_runs)) + " Runs"
            init_val = "IV Swinger Plot for " + run_str
        else:
            # Display error dialog and return if any overlays are selected
            selected_overlays = self.get_selected_overlays()
            if len(selected_overlays):
                tkmsg.showinfo(message=("ERROR: cannot change title on "
                                        "completed overlays"))
                return
            sel_runs = self.get_selected_runs(include_whole_days=False)
            if len(sel_runs) == 1:
                dts = IV_Swinger.DateTimeStr.extract_date_time_str(sel_runs[0])
                date_time = self.date_at_time_from_dts(dts)
                if (self.master.ivs2.plot_title is None):
                    init_val = "IV Swinger Plot for " + date_time
                else:
                    init_val = self.master.ivs2.plot_title
            elif len(sel_runs) > 1:
                err_str = ("ERROR: Title can only be changed on one run "
                           "at a time")
                tkmsg.showinfo(message=err_str)
                return
            else:
                err_str = ("ERROR: No run selected")
                tkmsg.showinfo(message=err_str)
                return
        new_title = tksd.askstring(title="Change title",
                                   prompt=prompt_str,
                                   initialvalue=init_val)
        if new_title:
            if self.master.overlay_mode:
                self.overlay_title = new_title
                self.plot_overlay_and_display()
            else:
                self.master.plot_title = new_title
                self.master.redisplay_img(reprocess_adc=False)

    # -------------------------------------------------------------------------
    def view_pdf(self, event=None):
        """Callback method to view the PDF when the View PDF button
           is pressed.
        """
        # If there is a PDF, it has the same name as the image being
        # displayed in the image pane, but with a .pdf suffix
        # replacing the .gif suffix.
        img = self.master.img_file
        if img is not None and os.path.exists(img):
            (file, ext) = os.path.splitext(img)
            pdf = file + ".pdf"
            if self.master.overlay_mode:
                # In overlay mode, the PDF is only generated when the Finished
                # button is pressed, so we have to generate it "on demand" when
                # the View PDF button is pressed.
                self.ivp.plot_graphs_to_pdf(self.ivp.ivsp_ivse,
                                            self.ivp.csv_proc)
            if os.path.exists(pdf):
                self.master.sys_view_file(pdf)
                return
        err_str = ("ERROR: No PDF to display")
        tkmsg.showinfo(message=err_str)

    # -------------------------------------------------------------------------
    def update_selected(self, event=None):
        """Callback method to update the selected runs when the Update button
           is pressed.
        """
        # Display error dialog and return if any overlays are selected
        selected_overlays = self.get_selected_overlays()
        if len(selected_overlays):
            tkmsg.showinfo(message="ERROR: overlays cannot be updated")
            return

        # Get the selected run(s) from the Treeview (sorted from
        # oldest to newest). Display error dialog and return if no
        # runs are selected
        selected_runs = sorted(self.get_selected_runs())
        if not len(selected_runs):
            tkmsg.showinfo(message="ERROR: no runs are selected")
            return

        # Hack: invisible progress bar (length=0). For some reason, this solves
        # the (Mac-only) problem of the images not getting displayed during the
        # update
        if sys.platform == 'darwin':
            pb = ProgressBar(master=self, length=0, maximum=len(selected_runs))

        # Loop through runs, regenerating/redisplaying
        for run_dir in selected_runs:
            selection = os.path.basename(run_dir)

            # Get names of CSV and GIF files
            (csv_data_point_file,
             adc_csv_file, _) = self.get_csv_and_gif_names(run_dir, selection)
            if csv_data_point_file is None and adc_csv_file is None:
                continue

            # Prepare IVS2 object for regeneration of plot with modified
            # options
            self.prep_ivs2_for_redisplay(run_dir, adc_csv_file)

            # Set x_pixels to current value
            self.master.ivs2.x_pixels = self.master.get_curr_x_pixels()

            # Get the title from the saved config
            self.master.plot_title = None
            cfg_file = os.path.join(run_dir, APP_NAME + ".cfg")
            if os.path.exists(cfg_file):
                self.master.get_old_title_config(cfg_file)
                self.master.plot_title = self.master.ivs2.plot_title

            # If Lock checkbutton is unchecked, unlock axes so scaling
            # is automatic - otherwise, all updates will use the
            # current lock values
            if self.master.axes_locked.get() == "Unlock":
                self.unlock_axes()

            # Redisplay the image with the current options. This
            # regenerates the image files, and while not necessary to
            # display the image, it serves the function of a progress
            # indicator.
            self.master.img_pane.splash_img_showing = False
            reprocess_adc = os.path.exists(adc_csv_file)
            self.master.redisplay_img(reprocess_adc=reprocess_adc)
            self.update_idletasks()

        # Destroy dummy progress bar
        if sys.platform == 'darwin':
            pb.destroy()

        # Display done message if multiple runs selected
        if len(selected_runs) > 1:
            tkmsg.showinfo(message="Batch update complete")

    # -------------------------------------------------------------------------
    def overlay_runs(self, event=None):
        """Method to overlay the selected runs
        """
        # Get the selected run(s) from the Treeview
        # Sort in oldest-to-newest order
        self.overlaid_runs = self.get_selected_runs(include_whole_days=False)
        self.sort_overlaid_runs()

        # Check for too many selected
        max_overlays = len(IV_Swinger.PLOT_COLORS)
        if len(self.overlaid_runs) > max_overlays:
            err_str = ("ERROR: Maximum of " + str(max_overlays) +
                       " overlays supported (" + str(len(self.overlaid_runs)) +
                       " requested)")
            tkmsg.showinfo(message=err_str)
            return RC_FAILURE

        # Check for none selected
        if not self.master.overlay_mode and not len(self.overlaid_runs):
            info_str = ("Select at least one run to begin an overlay")
            tkmsg.showinfo(message=info_str)
            return RC_FAILURE

        # Enter overlay mode (if not already in it)
        if not self.master.overlay_mode:
            self.add_overlay_widgets()
            self.master.overlay_mode = True
            self.make_overlay_dir()

        # Populate the overlay treeview
        self.populate_overlay_treeview(self.overlaid_runs)

        # If anything is selected, create the overlay and display the
        # result
        if len(self.overlaid_runs):
            rc = self.get_selected_csv_files(self.overlaid_runs)
            if rc == RC_SUCCESS:
                self.plot_overlay_and_display()
                self.add_new_overlay_to_tree()

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
        if not self.master.overlay_mode:
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
                    run_dts = IV_Swinger.DateTimeStr.extract_date_time_str(run)
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
        overlay_dir = self.master.overlay_dir
        overlay = IV_Swinger.DateTimeStr.extract_date_time_str(overlay_dir)
        self.overlay_iid = "overlay_" + overlay
        parent = 'overlays'

        # If the iid already exists in the tree, nothing to do
        if self.tree.exists(self.overlay_iid):
            return

        # Add overlays parent to Treeview if it doesn't already exist
        if not self.tree.exists(parent):
            self.tree.insert('', 0, parent, text="Overlays")

        # Translate to human readable date and time
        xlated = IV_Swinger.DateTimeStr.xlate_date_time_str(overlay)
        (xlated_date, xlated_time) = xlated

        # Add to tree at the beginning of the parent (since order is
        # newest first)
        text = ("Created on " + xlated_date + " at " +
                xlated_time)
        self.tree.insert(parent, 0, self.overlay_iid, text=text)

    # -------------------------------------------------------------------------
    def add_overlay_widgets(self):
        """Method to add the overlay mode widgets to the dialog
        """
        self.overlay_widget_box = ttk.Frame(self.body, borderwidth=5,
                                            relief='ridge')
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
        """Callback method for changes to the overlay label checkbuttons
        """
        self.plot_overlay_and_display()

    # -------------------------------------------------------------------------
    def create_overlay_treeview(self):
        """Method to create the overlay Treeview widget
        """
        self.overlay_widget_treeview = ttk.Treeview(self.overlay_widget_box,
                                                    columns=("label"),
                                                    displaycolumns=("label"),
                                                    selectmode='browse')
        # Set treeview height to accomodate the maximum number of
        # overlays
        max_overlays = len(IV_Swinger.PLOT_COLORS)
        self.overlay_widget_treeview.configure(height=max_overlays)

        # Set each column's width to half the wizard's main treeview
        # width so the two treeviews are the same width. Add column
        # headings.
        col0_text = "Date/Time"
        col1_text = "Name (2-click to change)"
        self.overlay_widget_treeview.column('#0', width=WIZARD_TREE_WIDTH/2)
        self.overlay_widget_treeview.heading('#0', text=col0_text,
                                             command=self.chron_sort_overlays)
        self.overlay_widget_treeview.column('#1', width=WIZARD_TREE_WIDTH/2)
        self.overlay_widget_treeview.heading('#1', text=col1_text,
                                             command=self.overlay_tv_col1_help)

        # Register callbacks for drag-and-drop reordering
        self.overlay_widget_treeview.bind("<ButtonPress-1>",
                                          self.grab_overlay_curve)

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
        """Callback method to sort the overlays in the treeview chronologically
           when the heading is clicked. Order reverses each time it is
           called.
        """
        self.sort_overlaid_runs(chron=True)
        self.populate_overlay_treeview(self.overlaid_runs)
        self.overlay_runs(event=None)

    # -------------------------------------------------------------------------
    def overlay_tv_col1_help(self, event=None):
        """Method to display a help dialog if the column 1 heading (Name) is
           clicked.
        """
        help_str = "Double-click items below to rename.\n"
        help_str += "Drag items to change order."
        tkmsg.showinfo(message=help_str)

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
            date_time = self.date_at_time_from_dts(dts)
            if dts in self.master.overlay_names:
                name = self.master.overlay_names[dts]
            else:
                name = date_time
            self.overlay_widget_treeview.insert('', 'end', dts,
                                                text=date_time,
                                                values=[name])
        self.overlays_reordered = False

    # -------------------------------------------------------------------------
    def date_at_time_from_dts(self, dts):
        """Method to convert a date_time_str to date@time, e.g. from
           170110_190017 to 01/10/17@19:00:17
        """
        (date, time) = IV_Swinger.DateTimeStr.xlate_date_time_str(dts)
        return(date + "@" + time)

    # -------------------------------------------------------------------------
    def grab_overlay_curve(self, event=None):
        """Callback method to select clicked curve in the treeview in
           preparation for dragging to reorder
        """
        tv = event.widget
        if tv.identify_row(event.y) not in tv.selection():
            tv.selection_set(tv.identify_row(event.y))

    # -------------------------------------------------------------------------
    def move_overlay_curve(self, event=None):
        """Callback method to drag the selected curve to a new position in the
           list
        """
        tv = event.widget
        moveto = tv.index(tv.identify_row(event.y))
        try:
            tv.move(tv.selection()[0], '', moveto)
            self.overlays_reordered = True
        except IndexError:
            # Spurious error - ignore
            pass

    # -------------------------------------------------------------------------
    def update_overlay_order(self, event=None):
        """Callback method to update the order of the overlay curves after a
           drag-and-drop
        """
        if self.overlays_reordered:
            self.reorder_selected_csv_files()
            self.plot_overlay_and_display()
        self.overlays_reordered = False

    # -------------------------------------------------------------------------
    def change_overlay_curve_name(self, event=None):
        """Callback method to prompt the user to enter a new name for an
           overlay curve
        """
        tv = event.widget
        dts = tv.identify_row(event.y)
        if IV_Swinger.DateTimeStr.is_date_time_str(dts):
            date_time = self.date_at_time_from_dts(dts)
        else:
            # Double-click was somewhere else
            return

        # Open dialog to add or change name
        prompt_str = "Enter name for " + date_time + " curve"
        if dts in self.master.overlay_names:
            init_val = self.master.overlay_names[dts]
        else:
            init_val = date_time
        new_name = tksd.askstring(title="Change name",
                                  prompt=prompt_str,
                                  initialvalue=init_val)
        if new_name:
            self.master.overlay_names[dts] = new_name
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
        """Callback method to display overlay help dialog when the Help button
           is pressed.
        """
        OverlayHelpDialog(self.master)

    # -------------------------------------------------------------------------
    def overlay_cancel(self, event=None):
        """Callback method to perform actions when Cancel button is pressed.
           Overlay mode is exited and the widgets are removed. The runs
           are left selected.
        """
        # Exit overlay mode and remove widgets
        self.master.overlay_mode = False
        self.overlay_title = None
        self.remove_overlay_widgets()

        # Remove overlay from tree
        self.tree.delete(self.overlay_iid)

        # Remove overlay directory
        if self.master.overlay_dir == os.getcwd():
            os.chdir("..")
        shutil.rmtree(self.master.overlay_dir)

    # -------------------------------------------------------------------------
    def overlay_finished(self, event=None):
        """Callback method to perform actions when Finished button is pressed.
           PDF is generated. Overlay mode is exited and the widgets are
           removed. The runs are de-selected and the overlay is selected
           and made visible, with the assumption that the user's next
           action will be to copy the overlay files.
        """
        # Generate the PDF
        self.ivp.plot_graphs_to_pdf(self.ivp.ivsp_ivse, self.ivp.csv_proc)

        # Exit overlay mode and remove widgets
        self.master.overlay_mode = False
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
            self.tree.see('overlays')
            self.tree.see(self.overlay_iid)
            self.tree.selection_add(self.overlay_iid)

    # -------------------------------------------------------------------------
    def rm_overlay_if_unfinished(self):
        """Method to remove the current overlay directory if it is
           "unfinished", i.e. if it doesn't contain a PDF (or doesn't
           exist at all). Returns True if it was removed (or didn't
           exist) and False otherwise.
        """
        if self.master.overlay_dir is not None:
            if not os.path.exists(self.master.overlay_dir):
                return True
            # Remove directory if it doesn't contain overlaid PDF
            overlay_pdf = ("overlaid_" +
                           os.path.basename(self.master.overlay_dir) +
                           ".pdf")
            if overlay_pdf not in os.listdir(self.master.overlay_dir):
                if self.master.overlay_dir == os.getcwd():
                    os.chdir("..")
                shutil.rmtree(self.master.overlay_dir)
                return True
            # Clean up the directory
            self.master.clean_up_files(self.master.overlay_dir,
                                       loop_mode=False)
        return False

    # -------------------------------------------------------------------------
    def get_selected_csv_files(self, selected_runs):
        """Method to get the full paths of the CSV files for the selected runs
        """
        self.selected_csv_files = []
        for csv_dir in selected_runs:
            dts = IV_Swinger.DateTimeStr.extract_date_time_str(csv_dir)
            csv_files_found = 0
            for file in os.listdir(csv_dir):
                if (file.endswith(dts + '.csv') and
                        not file.startswith('adc_pairs')):
                    csv_file_full_path = os.path.join(csv_dir, file)
                    self.selected_csv_files.append(csv_file_full_path)
                    csv_files_found += 1
            if not csv_files_found:
                err_str = "ERROR: no data point CSV file found in " + csv_dir
                tkmsg.showinfo(message=err_str)
                return RC_FAILURE
            elif csv_files_found > 1:
                err_str = ("ERROR: multiple data point CSV files found in " +
                           csv_dir)
                tkmsg.showinfo(message=err_str)
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
                csv_dts = IV_Swinger.DateTimeStr.extract_date_time_str(csv)
                if csv_dts == dts:
                    new_csv_list.append(csv)
                    break
        self.selected_csv_files = list(new_csv_list)

    # -------------------------------------------------------------------------
    def make_overlay_dir(self):
        """Method to create the directory for an overlay
        """
        # Generate the date/time string from the current time
        date_time_str = IV_Swinger.DateTimeStr.get_date_time_str()

        # Create overlay directory
        self.master.overlay_dir = os.path.join(self.results_dir, "overlays",
                                               date_time_str)
        if not os.path.exists(self.master.overlay_dir):
            os.makedirs(self.master.overlay_dir)

    # -------------------------------------------------------------------------
    def plot_overlay(self):
        """Method to generate the overlay plot
        """
        self.ivp = IV_Swinger2_plotter()
        self.get_overlay_curve_names()
        self.ivp.title = self.overlay_title
        self.ivp.logger = self.master.ivs2.logger
        self.ivp.csv_files = self.selected_csv_files
        self.ivp.plot_dir = self.master.overlay_dir
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
        if len(self.master.overlay_names):
            curves = self.overlay_widget_treeview.get_children()
            for dts in curves:
                if dts in self.master.overlay_names:
                    # Name is user-specified
                    name = self.master.overlay_names[dts]
                    self.ivp.curve_names.append(name)
                else:
                    # Default name: date@time
                    date_time = self.date_at_time_from_dts(dts)
                    self.ivp.curve_names.append(date_time)
        else:
            self.ivp.curve_names = None


# Progress bar class
#
class ProgressBar(tk.Toplevel):
    """Determinate progress bar class"""

    # Initializer
    def __init__(self, master=None, orient=HORIZONTAL, length=200,
                 maximum=None):
        tk.Toplevel.__init__(self, master=master)
        self.p = ttk.Progressbar(self, orient=orient, length=length,
                                 maximum=maximum, mode='determinate')
        self.p.pack()


# Menu bar class
#
class MenuBar(tk.Menu):
    """Menu bar class"""

    # Initializer
    def __init__(self, master=None):
        tk.Menu.__init__(self, master=master)
        self.win_sys = self.master.root.tk.call('tk', 'windowingsystem')
        self.menubar = tk.Menu(self.master)
        self.selected_port = tk.StringVar()
        self.selected_port.set(self.master.ivs2.usb_port)
        self.create_about_menu()
        self.create_file_menu()
        self.create_usb_port_menu()
        self.create_calibrate_menu()
        self.create_window_menu()
        self.create_help_menu()
        self.master.root['menu'] = self.menubar

    # -------------------------------------------------------------------------
    def create_about_menu(self):
        if self.win_sys == 'aqua':  # Mac
            self.about_menu = tk.Menu(self.menubar, name='apple')
            self.menubar.add_cascade(menu=self.about_menu)
            self.master.root.createcommand('tk::mac::ShowPreferences',
                                           self.master.show_preferences)
        else:
            self.about_menu = tk.Menu(self.menubar)
            self.menubar.add_cascade(menu=self.about_menu, label='About')
        self.about_menu.add_command(label="About IV Swinger 2",
                                    command=self.show_about_dialog)
        self.about_menu.add_separator()

    # -------------------------------------------------------------------------
    def create_file_menu(self):
        self.file_menu = tk.Menu(self.menubar)
        self.menubar.add_cascade(menu=self.file_menu, label='File')
        self.file_menu.add_command(label="View Log File",
                                   command=self.view_log_file)

    # -------------------------------------------------------------------------
    def create_usb_port_menu(self):
        self.usb_port_menu = tk.Menu(self.menubar)
        self.menubar.add_cascade(menu=self.usb_port_menu, label='USB Port')
        for serial_port_full_str in self.master.ivs2.serial_ports:
            serial_port = str(serial_port_full_str).split(' ')[0]
            self.usb_port_menu.add_radiobutton(label=serial_port_full_str,
                                               variable=self.selected_port,
                                               value=serial_port,
                                               command=self.select_serial)

    # -------------------------------------------------------------------------
    def create_calibrate_menu(self):
        self.calibrate_menu = tk.Menu(self.menubar)
        self.menubar.add_cascade(menu=self.calibrate_menu, label='Calibrate')
        self.calibrate_menu.add_command(label="Voltage Calibration",
                                        command=self.get_v_cal_value)
        self.calibrate_menu.add_command(label="Current Calibration",
                                        command=self.get_i_cal_value)
        self.calibrate_menu.add_command(label="Calibration Help",
                                        command=self.show_calibration_help)

    # -------------------------------------------------------------------------
    def disable_calibration(self):
        kwargs = {"state": "disabled"}
        self.calibrate_menu.entryconfig("Voltage Calibration", **kwargs)
        self.calibrate_menu.entryconfig("Current Calibration", **kwargs)

    # -------------------------------------------------------------------------
    def enable_calibration(self):
        kwargs = {"state": "normal"}
        self.calibrate_menu.entryconfig("Voltage Calibration", **kwargs)
        self.calibrate_menu.entryconfig("Current Calibration", **kwargs)

    # -------------------------------------------------------------------------
    def create_window_menu(self):
        if self.win_sys == 'aqua':  # Mac
            self.window_menu = tk.Menu(self.menubar, name='window')
            self.menubar.add_cascade(menu=self.window_menu, label='Window')
        else:
            pass

    # -------------------------------------------------------------------------
    def create_help_menu(self):
        # FIXME: not sure if special code is needed for Mac - other
        # looks better
        if self.win_sys == 'aqua':  # Mac
            self.help_menu = tk.Menu(self.menubar, name='help')
            self.master.root.createcommand('tk::mac::ShowHelp',
                                           self.show_help)
        else:
            self.help_menu = tk.Menu(self.menubar)
        self.menubar.add_cascade(menu=self.help_menu, label='Help')
        self.help_menu.add_command(label="Help topic 1",
                                   command=self.show_help)

    # -------------------------------------------------------------------------
    def show_about_dialog(self):
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
documentation, Fritzing file (hardware
description), and software can be found
at:

   https://github.com/csatt/IV_Swinger
"""
        tkmsg.showinfo(message=about_str)

    # -------------------------------------------------------------------------
    def view_log_file(self):
        (dir, file) = os.path.split(self.master.ivs2.logger.log_file_name)
        options = {}
        options['defaultextension'] = '.txt'
        options['initialdir'] = dir
        options['initialfile'] = file
        options['parent'] = self.master
        options['title'] = 'Choose log file'
        if sys.platform == 'darwin':
            options['message'] = options['title']
        log_file = tkFileDialog.askopenfilename(**options)
        self.master.sys_view_file(log_file)

    # -------------------------------------------------------------------------
    def select_serial(self):
        self.master.ivs2.usb_port = self.selected_port.get()
        self.master.ivs2.arduino_ready = False
        self.master.attempt_arduino_handshake()
        if self.master.ivs2.arduino_ready:
            self.master.ivs2.cfg_set('USB', 'port', self.master.ivs2.usb_port)
            self.master.save_config()

    # -------------------------------------------------------------------------
    def get_v_cal_value(self):
        curr_voc = self.master.ivs2.ivp.csv_proc.plt_voc_volts[0]
        prompt_str = "Enter measured Voc value:"
        new_voc = tksd.askfloat(title="Voltage Calibration",
                                prompt=prompt_str,
                                initialvalue=curr_voc)
        if new_voc:
            new_v_cal = self.master.ivs2.v_cal * (new_voc / curr_voc)
            self.master.ivs2.v_cal = new_v_cal
            self.master.ivs2.cfg_set('Calibration', 'voltage', new_v_cal)
            # Redisplay the image with the new settings (saves config)
            self.master.redisplay_img(reprocess_adc=True)

    # -------------------------------------------------------------------------
    def get_i_cal_value(self):
        curr_isc = self.master.ivs2.ivp.csv_proc.plt_isc_amps[0]
        prompt_str = "Enter measured Isc value:"
        new_isc = tksd.askfloat(title="Current Calibration",
                                prompt=prompt_str,
                                initialvalue=curr_isc)
        if new_isc:
            new_i_cal = self.master.ivs2.i_cal * (new_isc / curr_isc)
            self.master.ivs2.i_cal = new_i_cal
            self.master.ivs2.cfg_set('Calibration', 'current', new_i_cal)
            # Redisplay the image with the new settings (saves config)
            self.master.redisplay_img(reprocess_adc=True)

    # -------------------------------------------------------------------------
    def show_calibration_help(self):
        CalibrationHelpDialog(self.master)

    # -------------------------------------------------------------------------
    def show_help(self):
        help_str = "Help not yet implemented"
        tkmsg.showinfo(message=help_str)


# Generic dialog class (based on
# http://effbot.org/tkinterbook/tkinter-dialog-windows.htm)
#
class Dialog(tk.Toplevel):
    """Toplevel class used for dialogs. This is a so-called 'modal window'.
    This means that when it comes up, access to the main window is
    disabled until this window is closed. Focus is directed to this
    window when it opens, and is returned to the main window when it is
    closed. This class is intended to be extended by subclasses.  This
    class provides the modal behavior and the standard OK and/or Cancel
    buttons. Placeholder methods to create the body and perform the
    appropriate actions when the OK or Cancel button is pressed are
    provided for the subclass to override. A placeholder function to
    validate the input before applying it is also provided for optional
    override.
    """
    # Initializer
    def __init__(self, master=None, title=None, has_ok_button=True,
                 has_cancel_button=True, return_ok=False, ok_label="OK",
                 resizable=False):
        tk.Toplevel.__init__(self, master=master)
        self.win_sys = self.master.tk.call('tk', 'windowingsystem')
        self.has_ok_button = has_ok_button
        self.has_cancel_button = has_cancel_button
        self.return_ok = return_ok
        self.ok_label = ok_label
        self.resizable(width=resizable, height=resizable)
        self.master = master
        self.transient(self.master)  # tie this window to master
        if title is not None:
            self.title(title)
        self.grab_set()  # block change of focus to master
        self.focus_set()
        self.snapshot_values = {}
        self.curr_values = {}

        # Snapshot current values for revert
        self.snapshot()

        # Create body frame
        body = ttk.Frame(self)
        # Call body method to create body contents
        self.body(body)
        body.grid(column=0, row=0, sticky=(N, S, E, W))
        # Add button box with OK and Cancel buttons
        self.buttonbox(body)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.master.set_dialog_geometry(self)
        self.wait_window(self)

    # -------------------------------------------------------------------------
    def body(self, master):
        # Create dialog body. This method should be overridden.
        pass

    # -------------------------------------------------------------------------
    def buttonbox(self, master):
        # Add standard button box. Override if you don't want the
        # standard buttons.
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
        box.grid(column=0, row=1, sticky=(E))
        if self.win_sys == 'win32':  # Windows
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
        if not self.validate():
            return
        self.withdraw()
        self.update_idletasks()
        self.apply()
        self.close()

    # -------------------------------------------------------------------------
    def cancel(self, event=None):
        self.revert()
        self.close()

    # -------------------------------------------------------------------------
    def snapshot(self):
        pass  # override

    # -------------------------------------------------------------------------
    def validate(self):
        return True  # override

    # -------------------------------------------------------------------------
    def revert(self):
        pass  # override

    # -------------------------------------------------------------------------
    def apply(self):
        pass  # override

    # -------------------------------------------------------------------------
    def close(self, event=None):
        # put focus back to the master window
        self.master.focus_set()
        self.destroy()


# Calibration help dialog class
#
class CalibrationHelpDialog(Dialog):
    """Extension of the generic Dialog class used for the Calibration Help
    dialog
    """
    # Initializer
    def __init__(self, master=None):
        title = "Calibration Help"
        Dialog.__init__(self, master=master, title=title,
                        has_cancel_button=False, return_ok=True)

    # Create body, which is just a Text widget
    def body(self, master):
        help_text_1 = """
Voltage and current calibration are performed by "correcting" the open circuit
voltage (Voc) and short circuit current (Isc) values of a given IV curve with
values that are measured with a digital multimeter (DMM).
"""
        voltage_heading = """
Voltage calibration:"""
        help_text_2 = """
  1. Connect the DMM to the IV Swinger 2 binding posts with the PV module
     connected normally
  2. Set the DMM to measure DC voltage
  3. Note the DMM value immediately before and after swinging a curve
  4. Enter this value in the Voltage Calibration dialog and hit OK

  The curve will be regenerated with Voc calibrated to this value, and future
  curves will be generated using the new calibration.
"""
        current_heading = """
Current calibration (a bit trickier):"""
        help_text_3 = """
  1. Move the red DMM lead to the "A" DMM input and set it to measure DC
     current
  2. Disconnect the PV+ lead from the red (+) IV Swinger 2 binding post
  3. Connect the DMM in series between the PV+ lead and the red (+) IV Swinger
     2 binding post
  4. Shade the PV module as much as possible (to prevent arcing)
  5. Short the red (+) IV Swinger 2 binding post to the black (-) binding post
     using a banana plug shorting bar or short banana plug jumper cable
  6. Unshade the PV module
  7. Note the DMM value
  8. Shade the PV module
  9. Remove the shorting bar/jumper
 10. Unshade the PV module
 11. Swing an IV curve
 12. Enter the DMM value in the Current Calibration dialog and hit OK

  The curve will be regenerated with Isc calibrated to this value, and future
  curves will be generated using the new calibration. Steps 7-11 must be
  performed quickly and in steady sunlight so that the Isc is not changing
  between the DMM measurement and the IV swing. Repeat to confirm/adjust.
"""
        total_height = (len(help_text_1.split('\n')) +
                        len(voltage_heading.split('\n')) +
                        len(help_text_2.split('\n')) +
                        len(current_heading.split('\n')) +
                        len(help_text_3.split('\n')))
        if self.master.ivs2.x_pixels <= 750:
            font_size = 12
            total_height *= 0.85
        elif self.master.ivs2.x_pixels <= 1100:
            font_size = 13
            total_height *= 0.9
        else:
            font_size = 14
            total_height *= 0.95
        font = "Arial " + str(font_size)
        self.text = tk.Text(master, height=total_height, borderwidth=10)
        self.text.tag_configure('body_tag', font=font)
        self.text.tag_configure('heading_tag', font=font, underline=True)
        self.text.insert('end', help_text_1, ('body_tag'))
        self.text.insert('end', voltage_heading, ('heading_tag'))
        self.text.insert('end', help_text_2, ('body_tag'))
        self.text.insert('end', current_heading, ('heading_tag'))
        self.text.insert('end', help_text_3, ('body_tag'))
        self.text.grid()


# Preferences dialog class
#
class PreferencesDialog(Dialog):
    """Extension of the generic Dialog class used for the Preferences
    dialog
    """
    # Initializer
    def __init__(self, master=None):
        self.restore_looping = tk.StringVar()
        self.fancy_labels = tk.StringVar()
        self.interpolation_type = tk.StringVar()
        self.font_scale = tk.StringVar()
        self.line_scale = tk.StringVar()
        self.point_scale = tk.StringVar()
        self.correct_adc = tk.StringVar()
        self.spi_clk_str = tk.StringVar()
        self.max_iv_points_str = tk.StringVar()
        self.min_isc_adc_str = tk.StringVar()
        self.max_isc_poll_str = tk.StringVar()
        self.isc_stable_adc_str = tk.StringVar()
        self.max_discards_str = tk.StringVar()
        self.aspect_height_str = tk.StringVar()
        self.aspect_width_str = tk.StringVar()
        self.plot_props = PlottingProps(ivs2=master.ivs2)
        title = APP_NAME + " Preferences"
        Dialog.__init__(self, master=master, title=title)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Create body, which is a Notebook (tabbed frames)
        """
        self.nb = ttk.Notebook(master)
        self.plotting_tab = ttk.Frame(self.nb)
        self.looping_tab = ttk.Frame(self.nb)
        self.arduino_tab = ttk.Frame(self.nb)
        self.nb.add(self.plotting_tab, text='Plotting')
        self.nb.add(self.looping_tab, text='Looping')
        self.nb.add(self.arduino_tab, text='Arduino')
        self.populate_plotting_tab()
        self.populate_looping_tab()
        self.populate_arduino_tab()
        self.nb.grid()

    # -------------------------------------------------------------------------
    def populate_plotting_tab(self):
        """Add widgets to the Plotting tab"""
        section = "Plotting"
        self.font_scale.set(self.master.ivs2.cfg.getfloat(section,
                                                          'font scale'))
        self.line_scale.set(self.master.ivs2.cfg.getfloat(section,
                                                          'line scale'))
        self.point_scale.set(self.master.ivs2.cfg.getfloat(section,
                                                           'point scale'))
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
        if self.master.ivs2.cfg.getboolean(section, 'linear'):
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
        if self.master.ivs2.cfg.getboolean(section, 'fancy labels'):
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
        font_scale_slider.bind('<ButtonRelease-1>', self.immediate_apply)
        font_scale_entry = ttk.Entry(master=plotting_widget_box,
                                     width=8,
                                     textvariable=self.font_scale)
        font_scale_entry.bind('<Return>', self.immediate_apply)

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
        line_scale_slider.bind('<ButtonRelease-1>', self.immediate_apply)
        line_scale_entry = ttk.Entry(master=plotting_widget_box,
                                     width=8,
                                     textvariable=self.line_scale)
        line_scale_entry.bind('<Return>', self.immediate_apply)

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
        point_scale_slider.bind('<ButtonRelease-1>', self.immediate_apply)
        point_scale_entry = ttk.Entry(master=plotting_widget_box,
                                      width=8,
                                      textvariable=self.point_scale)
        point_scale_entry.bind('<Return>', self.immediate_apply)

        # Add radio buttons to choose whether ADC values should be
        # corrected or not
        correct_adc_label = ttk.Label(master=plotting_widget_box,
                                      text="ADC correction:")
        correct_adc_off_rb = ttk.Radiobutton(master=plotting_widget_box,
                                             text="Off",
                                             variable=self.correct_adc,
                                             command=self.immediate_apply,
                                             value="Off")
        correct_adc_on_rb = ttk.Radiobutton(master=plotting_widget_box,
                                            text="On",
                                            variable=self.correct_adc,
                                            command=self.immediate_apply,
                                            value="On")
        self.correct_adc.set("Off")
        if self.master.ivs2.cfg.getboolean(section, 'correct adc'):
            self.correct_adc.set("On")

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
        # Suppress displaying ADC correction widgets if the adc_pairs
        # property is not populated (unless we're still at the splash
        # screen)
        if (self.master.ivs2.adc_pairs is not None or
                self.master.img_pane.splash_img_showing):
            row = 5
            correct_adc_label.grid(column=0, row=row, sticky=W)
            correct_adc_off_rb.grid(column=1, row=row, sticky=W)
            correct_adc_on_rb.grid(column=2, row=row, sticky=W)
        row = 6
        plotting_help_box.grid(column=0, row=row, sticky=W, pady=pady,
                               columnspan=2)
        plotting_help.grid(column=0, row=0, sticky=W)
        plotting_restore_box.grid(column=2, row=row, sticky=W, columnspan=2)
        plotting_restore.grid(column=0, row=0, sticky=W)

    # -------------------------------------------------------------------------
    def restore_plotting_defaults(self, event=None):
        """Restore Plotting tab values to defaults"""
        self.fancy_labels.set(str(FANCY_LABELS_DEFAULT))
        self.interpolation_type.set(str(INTERPOLATION_TYPE_DEFAULT))
        self.font_scale.set(str(FONT_SCALE_DEFAULT))
        self.line_scale.set(str(LINE_SCALE_DEFAULT))
        self.point_scale.set(str(POINT_SCALE_DEFAULT))
        self.correct_adc.set(str(CORRECT_ADC_DEFAULT))
        self.immediate_apply()

    # -------------------------------------------------------------------------
    def show_plotting_help(self):
        """Display Plotting tab help"""
        PlottingHelpDialog(self.master)

    # -------------------------------------------------------------------------
    def populate_looping_tab(self):
        """Add widgets to the Looping tab"""
        # Add container box for widgets
        looping_widget_box = ttk.Frame(master=self.looping_tab, padding=20)

        # Add checkbutton to choose whether to restore looping settings
        # at startup
        restore_looping_cb_text = "Restore looping settings at startup?"
        restore_looping_cb = ttk.Checkbutton(master=looping_widget_box,
                                             text=restore_looping_cb_text,
                                             variable=self.restore_looping,
                                             onvalue="Enabled",
                                             offvalue="Disabled")
        if self.master.ivs2.cfg.getboolean('Looping', 'restore values'):
            restore_looping_cb.invoke()

        # Add Help button in its own container box
        looping_help_box = ttk.Frame(master=self.looping_tab, padding=10)
        looping_help = ttk.Button(looping_help_box,
                                  text="Help", width=8,
                                  command=self.show_looping_help)

        # Layout
        pady = 8
        looping_widget_box.grid(column=0, row=0, sticky=W, columnspan=2)
        restore_looping_cb.grid(column=0, row=0)
        looping_help_box.grid(column=0, row=1, sticky=W,
                              pady=pady, columnspan=2)
        looping_help.grid(column=0, row=0, sticky=W)

    # -------------------------------------------------------------------------
    def show_looping_help(self):
        """Display Looping tab help"""
        LoopingHelpDialog(self.master)

    # -------------------------------------------------------------------------
    def populate_arduino_tab(self):
        """Add widgets to the Arduino tab"""
        # Add container box for widgets
        arduino_widget_box = ttk.Frame(master=self.arduino_tab, padding=20)

        # Add label and combobox to select SPI clock frequency
        spi_clk_label = ttk.Label(master=arduino_widget_box,
                                  text="SPI clock freq:")
        spi_clk_combo = SpiClkCombo(master=arduino_widget_box,
                                    textvariable=self.spi_clk_str,
                                    ivs2=self.master.ivs2)

        # Add label and entry box to select maximum IV points
        max_iv_label = ttk.Label(master=arduino_widget_box,
                                 text="Max IV points:")
        max_iv_entry = ttk.Entry(master=arduino_widget_box,
                                 width=8,
                                 textvariable=self.max_iv_points_str)
        label_txt = ("(< " + str(MAX_IV_POINTS_DEFAULT + 1) + ")")
        max_iv_constraint_label = ttk.Label(master=arduino_widget_box,
                                            text=label_txt)
        max_iv_points = self.master.ivs2.cfg.getint('Arduino', 'max iv points')
        self.max_iv_points_str.set(max_iv_points)

        # Add label and entry box to select minimum Isc ADC
        min_isc_adc_label = ttk.Label(master=arduino_widget_box,
                                      text="Min Isc ADC:")
        min_isc_adc_entry = ttk.Entry(master=arduino_widget_box,
                                      width=8,
                                      textvariable=self.min_isc_adc_str)
        label_txt = ("(< " + str(ADC_MAX + 1) + ")")
        min_isc_adc_constraint_label = ttk.Label(master=arduino_widget_box,
                                                 text=label_txt)
        min_isc_adc = self.master.ivs2.cfg.getint('Arduino', 'min isc adc')
        self.min_isc_adc_str.set(min_isc_adc)

        # Add label and entry box to select maximum Isc polling loops
        max_isc_poll_label = ttk.Label(master=arduino_widget_box,
                                       text="Max Isc poll:")
        max_isc_poll_entry = ttk.Entry(master=arduino_widget_box,
                                       width=8,
                                       textvariable=self.max_isc_poll_str)
        label_txt = ("(< " + str(ARDUINO_MAX_INT + 1) + ")")
        max_isc_poll_constraint_label = ttk.Label(master=arduino_widget_box,
                                                  text=label_txt)
        max_isc_poll = self.master.ivs2.cfg.getint('Arduino', 'max isc poll')
        self.max_isc_poll_str.set(max_isc_poll)

        # Add label and entry box to select Isc stable ADC
        isc_stable_adc_label = ttk.Label(master=arduino_widget_box,
                                         text="Isc stable ADC:")
        isc_stable_adc_entry = ttk.Entry(master=arduino_widget_box,
                                         width=8,
                                         textvariable=self.isc_stable_adc_str)
        label_txt = ("(< " + str(ADC_MAX + 1) + ")")
        isc_stable_constraint_label = ttk.Label(master=arduino_widget_box,
                                                text=label_txt)
        isc_stable_adc = self.master.ivs2.cfg.getint('Arduino',
                                                     'isc stable adc')
        self.isc_stable_adc_str.set(isc_stable_adc)

        # Add label and entry box to select max discards
        max_discards_label = ttk.Label(master=arduino_widget_box,
                                       text="Max discards:")
        max_discards_entry = ttk.Entry(master=arduino_widget_box,
                                       width=8,
                                       textvariable=self.max_discards_str)
        label_txt = ("(< " + str(ARDUINO_MAX_INT + 1) + ")")
        max_discards_constraint_label = ttk.Label(master=arduino_widget_box,
                                                  text=label_txt)
        max_discards = self.master.ivs2.cfg.getint('Arduino', 'max discards')
        self.max_discards_str.set(max_discards)

        # Add label and entry box to select aspect height
        aspect_height_label = ttk.Label(master=arduino_widget_box,
                                        text="Aspect height:")
        aspect_height_entry = ttk.Entry(master=arduino_widget_box,
                                        width=8,
                                        textvariable=self.aspect_height_str)
        label_txt = ("(< " + str(MAX_ASPECT + 1) + ")")
        aspect_height_constraint_label = ttk.Label(master=arduino_widget_box,
                                                   text=label_txt)
        aspect_height = self.master.ivs2.cfg.getint('Arduino', 'aspect height')
        self.aspect_height_str.set(aspect_height)

        # Add label and entry box to select aspect width
        aspect_width_label = ttk.Label(master=arduino_widget_box,
                                       text="Aspect width:")
        aspect_width_entry = ttk.Entry(master=arduino_widget_box,
                                       width=8,
                                       textvariable=self.aspect_width_str)
        label_txt = ("(< " + str(MAX_ASPECT + 1) + ")")
        aspect_width_constraint_label = ttk.Label(master=arduino_widget_box,
                                                  text=label_txt)
        aspect_width = self.master.ivs2.cfg.getint('Arduino', 'aspect width')
        self.aspect_width_str.set(aspect_width)

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
        arduino_help_box.grid(column=0, row=row, sticky=W, pady=pady,
                              columnspan=2)
        arduino_help.grid(column=0, row=0, sticky=W)
        arduino_restore_box.grid(column=2, row=row, sticky=W, pady=pady,
                                 columnspan=2)
        arduino_restore.grid(column=0, row=0, sticky=W)

    # -------------------------------------------------------------------------
    def restore_arduino_defaults(self, event=None):
        """Restore Arduino tab values to defaults"""
        self.spi_clk_str.set(str(SPI_COMBO_VALS[SPI_CLK_DEFAULT]))
        self.max_iv_points_str.set(str(MAX_IV_POINTS_DEFAULT))
        self.min_isc_adc_str.set(str(MIN_ISC_ADC_DEFAULT))
        self.max_isc_poll_str.set(str(MAX_ISC_POLL_DEFAULT))
        self.isc_stable_adc_str.set(str(ISC_STABLE_DEFAULT))
        self.max_discards_str.set(str(MAX_DISCARDS_DEFAULT))
        self.aspect_height_str.set(str(ASPECT_HEIGHT_DEFAULT))
        self.aspect_width_str.set(str(ASPECT_WIDTH_DEFAULT))

    # -------------------------------------------------------------------------
    def show_arduino_help(self):
        """Display Arduino tab help"""
        ArduinoHelpDialog(self.master)

    # -------------------------------------------------------------------------
    def immediate_apply(self, event=None):
        """Apply configuration immediately"""
        try:
            event.widget.tk_focusNext().focus()  # move focus out
        except:
            pass
        self.update_idletasks()
        self.apply()

    # -------------------------------------------------------------------------
    def round_font_scale(self, event=None):
        """Emulate a resolution of 0.05 for font scale slider (no resolution
           option in ttk Scale class)
        """
        new_val = round(20.0*float(self.font_scale.get()))/20.0
        self.font_scale.set(str(new_val))

    # -------------------------------------------------------------------------
    def round_line_scale(self, event=None):
        """Emulate a resolution of 0.05 for line scale slider (no resolution
           option in ttk Scale class)
        """
        new_val = round(20.0*float(self.line_scale.get()))/20.0
        self.line_scale.set(str(new_val))

    # -------------------------------------------------------------------------
    def round_point_scale(self, event=None):
        """Emulate a resolution of 0.05 for point scale slider (no resolution
           option in ttk Scale class)
        """
        new_val = round(20.0*float(self.point_scale.get()))/20.0
        self.point_scale.set(str(new_val))

    # -------------------------------------------------------------------------
    def snapshot(self):
        """Override snapshot() method of parent to capture original
           configuration and property values
        """
        # Snapshot config
        self.master.get_snapshot_config()

        # Snapshot properties
        self.snapshot_values['linear'] = self.master.ivs2.linear
        self.snapshot_values['fancy_labels'] = self.master.ivs2.fancy_labels
        self.snapshot_values['font_scale'] = self.master.ivs2.font_scale
        self.snapshot_values['line_scale'] = self.master.ivs2.line_scale
        self.snapshot_values['point_scale'] = self.master.ivs2.point_scale
        self.snapshot_values['correct_adc'] = self.master.ivs2.correct_adc

    # -------------------------------------------------------------------------
    def validate(self):
        """Override validate() method of parent to check for legal values"""
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
            if max_iv_points > MAX_IV_POINTS_DEFAULT:
                err_str += ("\n  Max IV points must be no more than " +
                            str(MAX_IV_POINTS_DEFAULT))
            if min_isc_adc > ADC_MAX:
                err_str += ("\n  Min Isc ADC must be no more than " +
                            str(ADC_MAX))
            if max_isc_poll > ARDUINO_MAX_INT:
                err_str += ("\n  Max Isc poll must be no more than " +
                            str(ARDUINO_MAX_INT))
            if isc_stable_adc > ADC_MAX:
                err_str += ("\n  Isc stable ADC must be no more than " +
                            str(ADC_MAX))
            if max_discards > ARDUINO_MAX_INT:
                err_str += ("\n  Max discards must be no more than " +
                            str(ARDUINO_MAX_INT))
            if aspect_height > MAX_ASPECT:
                err_str += ("\n  Aspect height must be no more than " +
                            str(MAX_ASPECT))
            if aspect_width > MAX_ASPECT:
                err_str += ("\n  Aspect width must be no more than " +
                            str(MAX_ASPECT))
        if len(err_str) > len("ERROR:"):
            self.show_arduino_error_dialog(err_str)
            return False
        else:
            return True

    # -------------------------------------------------------------------------
    def show_arduino_error_dialog(self, err_str):
        tkmsg.showinfo(message=err_str)

    # -------------------------------------------------------------------------
    def revert(self):
        """Override revert() method of parent to apply original values to
           properties and the config
        """
        # Restore config
        self.master.save_snapshot_config()
        self.master.get_config()

        # Restore properties
        self.master.ivs2.linear = self.snapshot_values['linear']
        self.master.ivs2.fancy_labels = self.snapshot_values['fancy_labels']
        self.master.ivs2.font_scale = self.snapshot_values['font_scale']
        self.master.ivs2.line_scale = self.snapshot_values['line_scale']
        self.master.ivs2.point_scale = self.snapshot_values['point_scale']
        self.master.ivs2.correct_adc = self.snapshot_values['correct_adc']

        # Redisplay image if anything changed (saves config)
        if self.plot_props.prop_vals_changed():
            reprocess_adc = self.plot_props.correct_adc_prop_changed()
            self.master.redisplay_img(reprocess_adc=reprocess_adc)
            self.plot_props.update_prop_vals()

    # -------------------------------------------------------------------------
    def apply(self):
        """Override apply() method of parent to apply new values to properties
           and the config
        """
        if not self.validate():
            return

        # Apply config from each tab
        self.plotting_apply()
        self.looping_apply()
        self.arduino_apply()

    # -------------------------------------------------------------------------
    def plotting_apply(self):
        """Apply plotting config"""
        section = "Plotting"
        # Line type
        linear = (self.interpolation_type.get() == "Linear")
        self.master.ivs2.cfg_set(section, 'linear', linear)
        self.master.ivs2.linear = linear
        # Label type
        fancy_labels = (self.fancy_labels.get() == "Fancy")
        self.master.ivs2.cfg_set(section, 'fancy labels', fancy_labels)
        self.master.ivs2.fancy_labels = fancy_labels
        # Font scale
        font_scale = float(self.font_scale.get())
        self.master.ivs2.cfg_set(section, 'font scale', font_scale)
        self.master.ivs2.font_scale = font_scale
        # Line scale
        line_scale = float(self.line_scale.get())
        self.master.ivs2.cfg_set(section, 'line scale', line_scale)
        self.master.ivs2.line_scale = line_scale
        # Point scale
        point_scale = float(self.point_scale.get())
        self.master.ivs2.cfg_set(section, 'point scale', point_scale)
        self.master.ivs2.point_scale = point_scale
        # Correct ADC
        correct_adc = (self.correct_adc.get() == "On")
        self.master.ivs2.cfg_set(section, 'correct adc', correct_adc)
        self.master.ivs2.correct_adc = correct_adc

        # Redisplay image if anything changed (saves config)
        if self.plot_props.prop_vals_changed():
            reprocess_adc = self.plot_props.correct_adc_prop_changed()
            self.master.redisplay_img(reprocess_adc=reprocess_adc)
            self.plot_props.update_prop_vals()

    # -------------------------------------------------------------------------
    def looping_apply(self):
        """Apply looping config"""
        section = "Looping"
        # Restore values
        option = "restore values"
        restore_values = (self.restore_looping.get() == "Enabled")
        if (restore_values != self.master.ivs2.cfg.getboolean(section,
                                                              option)):
            self.master.ivs2.cfg_set(section, option, restore_values)
            # Save config
            self.master.save_config()

    # -------------------------------------------------------------------------
    def arduino_apply(self):
        """Apply Arduino config"""
        arduino_opt_changed = False
        section = "Arduino"
        option = "spi clock div"
        spi_clk_div = SPI_COMBO_VALS_INV[self.spi_clk_str.get()]
        if spi_clk_div != self.master.ivs2.cfg.getint(section, option):
            self.master.ivs2.cfg_set(section, option, spi_clk_div)
            arduino_opt_changed = True
        option = "max iv points"
        max_iv_points = int(self.max_iv_points_str.get())
        if max_iv_points != self.master.ivs2.cfg.getint(section, option):
            self.master.ivs2.cfg_set(section, option, max_iv_points)
            arduino_opt_changed = True
        option = "min isc adc"
        min_isc_adc = int(self.min_isc_adc_str.get())
        if min_isc_adc != self.master.ivs2.cfg.getint(section, option):
            self.master.ivs2.cfg_set(section, option, min_isc_adc)
            arduino_opt_changed = True
        option = "max isc poll"
        max_isc_poll = int(self.max_isc_poll_str.get())
        if max_isc_poll != self.master.ivs2.cfg.getint(section, option):
            self.master.ivs2.cfg_set(section, option, max_isc_poll)
            arduino_opt_changed = True
        option = "isc stable adc"
        isc_stable_adc = int(self.isc_stable_adc_str.get())
        if isc_stable_adc != self.master.ivs2.cfg.getint(section, option):
            self.master.ivs2.cfg_set(section, option, isc_stable_adc)
            arduino_opt_changed = True
        option = "max discards"
        max_discards = int(self.max_discards_str.get())
        if max_discards != self.master.ivs2.cfg.getint(section, option):
            self.master.ivs2.cfg_set(section, option, max_discards)
            arduino_opt_changed = True
        option = "aspect height"
        aspect_height = int(self.aspect_height_str.get())
        if aspect_height != self.master.ivs2.cfg.getint(section, option):
            self.master.ivs2.cfg_set(section, option, aspect_height)
            arduino_opt_changed = True
        option = "aspect width"
        aspect_width = int(self.aspect_width_str.get())
        if aspect_width != self.master.ivs2.cfg.getint(section, option):
            self.master.ivs2.cfg_set(section, option, aspect_width)
            arduino_opt_changed = True

        # Reestablish communication with Arduino if anything changed
        if arduino_opt_changed:
            self.master.reestablish_arduino_comm()
            # Save config
            self.master.save_config()


# Plotting properties class
#
class PlottingProps(object):
    """Plotting properties class. This class holds a copy of the state
    of all of the properties related to plotting and provides a
    method for comparing their current values with the current
    copy.
    """
    # Initializer
    def __init__(self, ivs2):
        self.ivs2 = ivs2
        self.prop_vals = {}
        self.update_prop_vals()

    # -------------------------------------------------------------------------
    def update_prop_vals(self):
        """Capture current values of properties"""
        # Capture current properties
        self.prop_vals['linear'] = self.ivs2.linear
        self.prop_vals['fancy_labels'] = self.ivs2.fancy_labels
        self.prop_vals['font_scale'] = self.ivs2.font_scale
        self.prop_vals['line_scale'] = self.ivs2.line_scale
        self.prop_vals['point_scale'] = self.ivs2.point_scale
        self.prop_vals['correct_adc'] = self.ivs2.correct_adc

    # -------------------------------------------------------------------------
    def prop_vals_changed(self):
        """Compare current values of properties with previously captured values
           to see if anything has changed
        """
        return ((self.prop_vals['linear'] != self.ivs2.linear) or
                (self.prop_vals['fancy_labels'] != self.ivs2.fancy_labels) or
                (self.prop_vals['font_scale'] != self.ivs2.font_scale) or
                (self.prop_vals['line_scale'] != self.ivs2.line_scale) or
                (self.prop_vals['point_scale'] != self.ivs2.point_scale) or
                (self.prop_vals['correct_adc'] != self.ivs2.correct_adc))

    # -------------------------------------------------------------------------
    def correct_adc_prop_changed(self):
        """Compare current value of correct_adc property with previously
           captured value to see if it has changed
        """
        return (self.prop_vals['correct_adc'] != self.ivs2.correct_adc)


# Plotting help dialog class
#
class PlottingHelpDialog(Dialog):
    """Extension of the generic Dialog class used for the Plotting Help
    dialog
    """
    # Initializer
    def __init__(self, master=None):
        title = "Plotting Help"
        Dialog.__init__(self, master=master, title=title,
                        has_cancel_button=False, return_ok=True)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Create body, which is just a Text widget"""
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
  maximum power. If "Off" is selected, these corrections are not
  performed. Note that the values written to the ADC CSV file are the
  uncorrected values, regardless of this setting. Also note that the
  calibration settings are used regardless of this setting.
"""
        total_height = (len(help_text_1.split('\n')))
        if self.master.ivs2.x_pixels <= 800:
            font_size = 12
            total_height *= 0.90
        elif self.master.ivs2.x_pixels <= 1024:
            font_size = 13
            total_height *= 0.95
        else:
            font_size = 14
            total_height *= 1.0
        font = "Arial " + str(font_size)
        self.text = tk.Text(master, height=total_height, borderwidth=10)
        self.text.tag_configure('body_tag', font=font)
        self.text.tag_configure('heading_tag', font=font, underline=True)
        self.text.insert('end', help_text_1, ('body_tag'))
        self.text.grid()


# SPI clock combobox class
#
class SpiClkCombo(ttk.Combobox):
    """Combobox used to select Arduino SPI clock frequency"""

    # Initializer
    def __init__(self, master=None, textvariable=None, ivs2=None):
        self.ivs2 = ivs2
        ttk.Combobox.__init__(self, master=master, textvariable=textvariable)
        spi_clk_div = self.ivs2.cfg.getint('Arduino', 'spi clock div')
        textvariable.set(SPI_COMBO_VALS[spi_clk_div])
        self['values'] = (SPI_COMBO_VALS[SPI_CLOCK_DIV2],
                          SPI_COMBO_VALS[SPI_CLOCK_DIV4],
                          SPI_COMBO_VALS[SPI_CLOCK_DIV8],
                          SPI_COMBO_VALS[SPI_CLOCK_DIV16],
                          SPI_COMBO_VALS[SPI_CLOCK_DIV32],
                          SPI_COMBO_VALS[SPI_CLOCK_DIV64],
                          SPI_COMBO_VALS[SPI_CLOCK_DIV128])
        self.state(['readonly'])
        self['width'] = 13


# Looping help dialog class
#
class LoopingHelpDialog(Dialog):
    """Extension of the generic Dialog class used for the Looping Help
    dialog
    """
    # Initializer
    def __init__(self, master=None):
        title = "Looping Help"
        Dialog.__init__(self, master=master, title=title,
                        has_cancel_button=False, return_ok=True)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Create body, which is just a Text widget"""
        help_text_1 = """
There is currently only one option on the Preferences Looping tab. The main
options controlling looping behavior are on the main IV Swinger 2 window to
the right of the "Swing!" button. The lone Preferences option is to choose
whether the settings on the main screen should be retained after the program is
closed and restored the next time it is opened.
"""
        total_height = (len(help_text_1.split('\n')))
        if self.master.ivs2.x_pixels <= 800:
            font_size = 12
            total_height *= 0.85
        elif self.master.ivs2.x_pixels <= 1024:
            font_size = 13
            total_height *= 0.9
        else:
            font_size = 14
            total_height *= 0.95
        font = "Arial " + str(font_size)
        self.text = tk.Text(master, height=total_height, borderwidth=10)
        self.text.tag_configure('body_tag', font=font)
        self.text.tag_configure('heading_tag', font=font, underline=True)
        self.text.insert('end', help_text_1, ('body_tag'))
        self.text.grid()


# Arduino help dialog class
#
class ArduinoHelpDialog(Dialog):
    """Extension of the generic Dialog class used for the Arduino Help
    dialog
    """
    # Initializer
    def __init__(self, master=None):
        title = "Arduino Help"
        Dialog.__init__(self, master=master, title=title,
                        has_cancel_button=False, return_ok=True)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Create body, which is just a Text widget"""
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
  Three consective measurements must vary less than this amount for Isc to be
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
"""
        total_height = (len(help_text_1.split('\n')))
        if self.master.ivs2.x_pixels <= 800:
            font_size = 12
            total_height *= 0.85
        elif self.master.ivs2.x_pixels <= 1024:
            font_size = 13
            total_height *= 0.9
        else:
            font_size = 14
            total_height *= 0.95
        font = "Arial " + str(font_size)
        self.text = tk.Text(master, height=total_height, borderwidth=10)
        self.text.tag_configure('body_tag', font=font)
        self.text.tag_configure('heading_tag', font=font, underline=True)
        self.text.insert('end', help_text_1, ('body_tag'))
        self.text.grid()


# Overlay help dialog class
#
class OverlayHelpDialog(Dialog):
    """Extension of the generic Dialog class used for the Overlay Help
    dialog
    """
    # Initializer
    def __init__(self, master=None):
        title = "Overlay Help"
        Dialog.__init__(self, master=master, title=title,
                        has_cancel_button=False, return_ok=True)

    # -------------------------------------------------------------------------
    def body(self, master):
        """Create body, which is just a Text widget"""
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
By default, the curves are named for the date and time they were captured,
e.g. "01/10/17@13:58:12".  This name can be changed by double-clicking it in
the "Overlay Runs" pane. The new name will remain associated with that run only
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
for labeling.
"""
        help_heading_5 = """
Finishing:"""
        help_text_5 = """
When the "Finished" button is pressed the overlay is finalized. The "Overlay
Runs" pane closes and the new overlay is added to the "Overlays" group in the
main Results Wizard tree view pane. The "Copy" button may then be used to copy
the overlay PDF (and GIF) to a USB drive or elsewhere. Note that once an
overlay is finalized, only the images are saved; it is not possible to modify
an overlay after it is finalized.
"""
        total_height = (len(help_text_intro.split('\n')) +
                        len(help_heading_1.split('\n')) +
                        len(help_text_1.split('\n')) +
                        len(help_heading_2.split('\n')) +
                        len(help_text_2.split('\n')) +
                        len(help_heading_3.split('\n')) +
                        len(help_text_3.split('\n')) +
                        len(help_heading_4.split('\n')) +
                        len(help_text_4.split('\n')) +
                        len(help_heading_5.split('\n')) +
                        len(help_text_5.split('\n')))
        if self.master.ivs2.x_pixels <= 800:
            font_size = 12
            total_height *= 0.85
        elif self.master.ivs2.x_pixels <= 1024:
            font_size = 13
            total_height *= 0.9
        else:
            font_size = 14
            total_height *= 0.95
        font = "Arial " + str(font_size)
        self.text = tk.Text(master, height=total_height, borderwidth=10)
        self.text.tag_configure('body_tag', font=font)
        self.text.tag_configure('heading_tag', font=font, underline=True)
        self.text.insert('end', help_text_intro, ('body_tag'))
        self.text.insert('end', help_heading_1, ('heading_tag'))
        self.text.insert('end', help_text_1, ('body_tag'))
        self.text.insert('end', help_heading_2, ('heading_tag'))
        self.text.insert('end', help_text_2, ('body_tag'))
        self.text.insert('end', help_heading_3, ('heading_tag'))
        self.text.insert('end', help_text_3, ('body_tag'))
        self.text.insert('end', help_heading_4, ('heading_tag'))
        self.text.insert('end', help_text_4, ('body_tag'))
        self.text.insert('end', help_heading_5, ('heading_tag'))
        self.text.insert('end', help_text_5, ('body_tag'))
        self.text.grid()


# Image pane class
#
class ImagePane(ttk.Label):
    """Label class used for the image pane"""
    # In Tkinter, the way to display an image is in a "Label" widget,
    # which makes it sound small. In our case it takes up the majority
    # of the GUI, so we'll call it a "pane" instead of a label. But it's
    # really a Label.

    # Initializer
    def __init__(self, master=None):
        ttk.Label.__init__(self, master=master)
        self.master = master
        self.display_splash_img()

    # -------------------------------------------------------------------------
    def display_splash_img(self):
        """Method to display the appropriately-sized splash image"""
        x_pixels = self.master.ivs2.x_pixels
        y_pixels = int(round(self.master.ivs2.x_pixels *
                             self.master.ivs2.plot_y_inches /
                             self.master.ivs2.plot_x_inches))
        splash_img = os.path.join(get_app_dir(), SPLASH_IMG)
        img = Image.open(splash_img).resize((x_pixels, y_pixels))
        self.current_img = ImageTk.PhotoImage(img)
        self['image'] = self.current_img
        self.image = self.current_img
        self.splash_img_showing = True


# Go/Stop button class
#
class GoStopButton(ttk.Button):
    """Button class used for the go button and stop button"""

    # Initializer
    def __init__(self, master=None, text=None):
        ttk.Button.__init__(self, master=master)
        self['text'] = "Not Ready"
        if text is not None:
            self['text'] = text
        self['style'] = "go_stop_button.TButton"


# Plot power checkbutton class
#
class PlotPower(ttk.Checkbutton):
    """Checkbutton used to include the power curve on the plot"""

    # Initializer
    def __init__(self, master=None, variable=None):
        ttk.Checkbutton.__init__(self, master=master, text='Plot Power',
                                 command=self.update_plot_power,
                                 variable=variable,
                                 onvalue="Plot", offvalue="DontPlot")
        self.plot_power = variable
        if self.master.ivs2.cfg.getboolean('Plotting', 'plot power'):
            self.invoke()

    # -------------------------------------------------------------------------
    def update_plot_power(self, event=None):
        # Update IVS2 property
        self.master.ivs2.plot_power = (self.plot_power.get() == "Plot")

        # Save values to config
        self.master.ivs2.cfg_set('Plotting', 'plot power',
                                 self.master.ivs2.plot_power)

        # Redisplay the image (with power plotted) - saves config
        self.master.redisplay_img(reprocess_adc=False)


# Lock axes checkbutton class
#
class LockAxes(ttk.Checkbutton):
    """Checkbutton used to lock axis ranges"""

    # Initializer
    def __init__(self, master=None, gui=None, variable=None, ivs2=None):
        ttk.Checkbutton.__init__(self, master=master, text='Lock',
                                 command=self.update_axis_lock,
                                 variable=variable,
                                 onvalue="Lock", offvalue="Unlock")
        self.gui = gui
        self.axes_locked = variable

    # -------------------------------------------------------------------------
    def update_axis_lock(self, event=None):
        axes_are_locked = (self.axes_locked.get() == "Lock")
        # Update IVS2 property
        self.gui.ivs2.plot_lock_axis_ranges = axes_are_locked
        # Update values in range boxes
        self.gui.update_axis_ranges()


# Loop mode checkbutton class
#
class LoopMode(ttk.Checkbutton):
    """Checkbutton used to enable loop mode"""

    # Initializer
    def __init__(self, master=None, gui=None, variable=None,
                 rate_limit=None, save_results=None, lock_axes=None):
        ttk.Checkbutton.__init__(self, master=master, text='Loop Mode',
                                 command=self.update_loop_mode,
                                 variable=variable,
                                 onvalue="On", offvalue="Off")
        self.gui = gui
        self.loop_mode = variable
        self.rate_limit = rate_limit
        self.save_results = save_results
        self.lock_axes = lock_axes
        self.axes_already_locked = False
        if (self.gui.ivs2.cfg.getboolean('Looping', 'restore values') and
                self.gui.ivs2.cfg.getboolean('Looping', 'loop mode')):
            self.invoke()

    # -------------------------------------------------------------------------
    def update_loop_mode(self, event=None):
        if self.loop_mode.get() == "On":
            self.gui.loop_mode.set("On")
            self.gui.loop_mode_active = True
            self.rate_limit.state(['!disabled'])
            self.save_results.state(['!disabled'])
            if self.lock_axes.instate(['selected']):
                self.axes_already_locked = True
            else:
                self.axes_already_locked = False
                self.lock_axes.invoke()  # Lock axes
                # But clear axis ranges so they lock on the first run of
                # the loop
                self.gui.ivs2.plot_max_x = None
                self.gui.ivs2.plot_max_y = None
            self.lock_axes.state(['disabled'])
        else:
            self.gui.loop_mode.set("Off")
            self.gui.loop_mode_active = False
            self.rate_limit.state(['disabled'])
            self.save_results.state(['disabled'])
            self.lock_axes.state(['!disabled'])
            if not self.axes_already_locked:
                self.lock_axes.invoke()  # Unlock axes

        # Save values to config
        self.gui.ivs2.cfg_set('Looping', 'loop mode',
                              self.gui.loop_mode_active)
        self.gui.save_config()


# Loop rate limit checkbutton class
#
class LoopRateLimit(ttk.Checkbutton):
    """Checkbutton used to rate limit loop mode"""

    # Initializer
    def __init__(self, master=None, gui=None, variable=None):
        ttk.Checkbutton.__init__(self, master=master, text='Rate Limit',
                                 command=self.update_loop_rate_limit,
                                 variable=variable,
                                 onvalue="On", offvalue="Off")
        self.gui = gui
        self.loop_rate_limit = variable
        self.value_label_obj = None
        self.state(['disabled'])

    # -------------------------------------------------------------------------
    def update_loop_rate_limit(self, event=None):
        if self.value_label_obj is not None:
            self.value_label_obj.destroy()
        if self.loop_rate_limit.get() == "On":
            curr_loop_delay = self.gui.loop_delay
            prompt_str = "Enter seconds to delay between loops:"
            new_loop_delay = tksd.askinteger(title="Loop delay",
                                             prompt=prompt_str,
                                             initialvalue=curr_loop_delay)
            if new_loop_delay:
                self.gui.loop_rate_limit = True
                self.gui.loop_delay = new_loop_delay
                self.update_value_str()
            else:
                self.gui.loop_rate_limit = False
                self.gui.loop_delay = 0
                self.state(['!selected'])
        else:
            self.gui.loop_rate_limit = False

        # Save values to config
        self.gui.ivs2.cfg_set('Looping', 'rate limit',
                              self.gui.loop_rate_limit)
        self.gui.ivs2.cfg_set('Looping', 'delay',
                              self.gui.loop_delay)
        self.gui.save_config()

    # -------------------------------------------------------------------------
    def update_value_str(self):
        value_str = "= " + str(self.gui.loop_delay) + "s"
        self.value_label_obj = ttk.Label(self.master, text=value_str)
        self.value_label_obj.pack(side=LEFT)


# Loop save results checkbutton class
#
class LoopSaveResults(ttk.Checkbutton):
    """Checkbutton used to enable/disable saving loop mode results"""

    # Initializer
    def __init__(self, master=None, gui=None, variable=None):
        ttk.Checkbutton.__init__(self, master=master, text='Save Results',
                                 command=self.update_loop_save_results,
                                 variable=variable,
                                 onvalue="On", offvalue="Off")
        self.gui = gui
        self.loop_save_results = variable
        self.value_label_obj = None
        self.state(['disabled'])

    # -------------------------------------------------------------------------
    def update_loop_save_results(self, event=None):
        if self.value_label_obj is not None:
            self.value_label_obj.destroy()
        if self.loop_save_results.get() == "On":
            self.gui.loop_save_results = True
            include_graphs = tkmsg.askyesno("Include graphs?",
                                            "Default is to save CSV files "
                                            "only. Do you want to save PDFs"
                                            " and GIFs too?",
                                            default=tkmsg.NO)
            self.gui.loop_save_graphs = include_graphs
            self.update_value_str()
        else:
            self.gui.loop_save_results = False
            self.configure(text='Save Results')

        # Save values to config
        self.gui.ivs2.cfg_set('Looping', 'save results',
                              self.gui.loop_save_results)
        self.gui.ivs2.cfg_set('Looping', 'save graphs',
                              self.gui.loop_save_graphs)
        self.gui.save_config()

    # -------------------------------------------------------------------------
    def update_value_str(self):
        if self.gui.loop_save_graphs:
            value_str = "(All)"
        else:
            value_str = "(CSV only)"
        self.value_label_obj = ttk.Label(self.master, text=value_str)
        self.value_label_obj.pack(side=LEFT)


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
        try:
            ivs.plot_graphs(self.args, csvp)
        except IOError as e:
            err_str = ("({})".format(e) +
                       "\n\n"
                       "PDF could not be written. If you have it open in a "
                       "viewer, close it BEFORE clicking OK.")
            tkmsg.showinfo(message=err_str)
            try:
                ivs.plot_graphs(self.args, csvp)
            except IOError as e:
                err_str = ("({})".format(e) +
                           "\n\n"
                           "PDF still could not be written. "
                           "It will not be updated.")
                tkmsg.showinfo(message=err_str)

    # -------------------------------------------------------------------------
    def plot_graphs_to_gif(self, ivs, csvp):
        """Method to plot the graphs to a GIF"""

        # Generating a GIF of a given resolution is trickier than it
        # should be. First of all, apparently pyplot can only generate
        # GIFs that have a 4:3 aspect ratio. If another aspect ratio is
        # used, there will be gray bars added to pad it out to the
        # requested ratio - but that obviously isn't appealing. So we'll
        # stick to 4:3.  The default pyplot image size is 8" x 6" at 100
        # DPI.  When a GIF is generated without overriding those
        # defaults, the resulting resolution is 1600x1200.  But the
        # resolution changes if different values are used for the width
        # and/or height and/or DPI.  Before calling the plot_graphs()
        # method, we have to adjust the scale parameters and the DPI
        # value based on the value of the x_pixels property. The
        # x_pixels property can be changed from a combobox in the GUI.
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
    def __init__(self):
        IV_Swinger.IV_Swinger.__init__(self)
        self.cfg = None
        self.cfg_snapshot = None
        self.lcd = None
        self.ivp = None
        self.prev_date_time_str = None
        # Property variables
        self._app_data_dir = None
        self._cfg_filename = None
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
        self._adc_pairs = []
        self._adc_pairs_corrected = []
        self._adc_ch0_offset = 0
        self._adc_ch1_offset = 0
        self._adc_range = 4096.0
        self._msg_timer_timeout = 50
        self._vdiv_r1 = 180000.0       # R1 = 180k nominal
        self._vdiv_r2 = 7500.0         # R2 = 7.5k nominal
        self._amm_op_amp_rf = 75000.0  # Rf = 75k
        self._amm_op_amp_rg = 1000.0   # Rg = 1k
        self._adc_vref = 5.0           # ADC voltage reference = 5V
        self._amm_shunt_max_volts = 0.050
        self._amm_shunt_max_amps = 10
        self._v_cal = 1.0
        self._i_cal = 1.0
        self._plot_title = None
        self._current_img = None
        self._x_pixels = 1085  # Default GIF width (1085x838)
        self._plot_lock_axis_ranges = False
        self._generate_pdf = True
        self._fancy_labels = True
        self._linear = True
        self._plot_power = False
        self._font_scale = FONT_SCALE_DEFAULT
        self._line_scale = LINE_SCALE_DEFAULT
        self._point_scale = POINT_SCALE_DEFAULT
        self._correct_adc = True

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
    def adc_ch0_offset(self):
        """Property to get the ADC channel 0 offset"""
        return self._adc_ch0_offset

    @adc_ch0_offset.setter
    def adc_ch0_offset(self, value):
        self._adc_ch0_offset = value

    # ---------------------------------
    @property
    def adc_ch1_offset(self):
        """Property to get the ADC channel 1 offset"""
        return self._adc_ch1_offset

    @adc_ch1_offset.setter
    def adc_ch1_offset(self, value):
        self._adc_ch1_offset = value

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
    def app_data_dir(self):
        """Application data directory where results, log files, and
           preferences are written. Default is platform-dependent.  The
           default can be overridden by setting the property after
           instantiation, but before calling the run() method.
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
    def cfg_filename(self):
        """Name of file (full path) that contains preferences and other
           configuration options
        """
        if self._cfg_filename is None:
            self._cfg_filename = os.path.join(self.app_data_dir,
                                              APP_NAME + ".cfg")
        return self._cfg_filename

    @cfg_filename.setter
    def cfg_filename(self, value):
        if value is not None and not os.path.isabs(value):
            raise ValueError("cfg_filename must be an absolute path")
        self._cfg_filename = value

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
    def ser(self):
        """Property to get the current serial port object"""
        return self._ser

    @ser.setter
    def ser(self, value):
        self._ser = value

    # ---------------------------------
    @property
    def sio(self):
        """Property to get the current TextIOWrapper buffered text
           stream object"""
        return self._sio

    @sio.setter
    def sio(self, value):
        self._sio = value

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
        last_measured_minus_offset = last_measured_adc - self.adc_ch0_offset
        voc_adc_minus_offset = self.voc_adc - self.adc_ch0_offset
        if last_measured_minus_offset > voc_adc_minus_offset:
            v_adj = (float(voc_adc_minus_offset) /
                     float(last_measured_minus_offset))
        return v_adj

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
            self.logger.print_and_log(section)
            for option in self.cfg.options(section):
                err_str = " " + option + "=" + self.cfg.get(section, option)
                self.logger.print_and_log(err_str)

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
        if self.ser is not None and self.ser.is_open:
            # First close port if it is already open
            self.ser.close()
        try:
            self.ser = serial.Serial(self.usb_port, self.usb_baud,
                                     timeout=self.serial_timeout)
        except (serial.SerialException) as e:
            self.logger.print_and_log("reset_arduino: ({})".format(e))
            return RC_SERIAL_EXCEPTION

        # Create buffered text stream
        self.sio = io.TextIOWrapper(io.BufferedRWPair(self.ser, self.ser),
                                    line_buffering=True)

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def wait_for_arduino_ready_and_ack(self):
        """Method to wait for the Arduino ready message, and send
           acknowledgement
        """

        # Return immediately if ready flag is already set
        if self.arduino_ready:
            return RC_SUCCESS

        # Otherwise wait for ready message from Arduino
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
        rc = self.send_config_msgs_to_arduino()
        if rc != RC_SUCCESS:
            return rc

        # Send ready message to Arduino
        rc = self.send_msg_to_arduino("Ready")
        if rc != RC_SUCCESS:
            return rc

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def send_config_msgs_to_arduino(self):
        """Method to send config messages to the Arduino, waiting for each
        reply"""
        config_dict = {"CLK_DIV": "spi clock div",
                       "MAX_IV_POINTS": "max iv points",
                       "MIN_ISC_ADC": "min isc adc",
                       "MAX_ISC_POLL": "max isc poll",
                       "ISC_STABLE_ADC": "isc stable adc",
                       "MAX_DISCARDS": "max discards",
                       "ASPECT_HEIGHT": "aspect height",
                       "ASPECT_WIDTH": "aspect width"}
        # self.cfg_dump()
        for config_type, config_str in config_dict.iteritems():
            config_value = self.cfg.getint('Arduino', config_str)
            rc = self.send_one_config_msg_to_arduino(config_type, config_value)
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

        if len(msg + "\n") > MAX_MSG_LEN_TO_ARDUINO:
            err_str = "ERROR: Message to Arduino is too long: " + msg
            self.logger.print_and_log(err_str)
            return RC_FAILURE

        try:
            self.sio.write(unicode(msg + "\n"))
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
                self.msg_from_arduino = self.sio.readline()
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
        adc_re = re.compile('CH0:(\d+)\s+CH1:(\d+)')
        for msg in received_msgs:
            match = adc_re.search(msg)
            if match:
                ch0_adc = int(match.group(1))
                ch1_adc = int(match.group(2))
                self.adc_pairs.append((ch0_adc, ch1_adc))

        return RC_SUCCESS

    # -------------------------------------------------------------------------
    def log_msg_from_arduino(self, msg):
        """Method to log a message from the Arduino"""
        self.logger.log("Arduino: " + msg.rstrip())

    # -------------------------------------------------------------------------
    def correct_adc_values(self):
        """Method to remove errors from the ADC values. This consists of the
        following corrections:
           - Adjust voltages to compensate for Voc shift
           - Enforce no voltage decreases
           - Enforce no current increases
           - Remove duplicates
        At some point, more sophisticated "noise reduction" may be
        substituted for the simplistic monotonicity enforcement.
        """
        self.logger.log("Correcting ADC values:")
        self.adc_pairs_corrected = []
        voc_pair_num = (len(self.adc_pairs) - 1)  # last one is Voc
        v_adj = self.v_adj
        self.logger.log("  v_adj = " + str(v_adj))
        num_v_decreases = 0
        num_i_increases = 0
        num_dups = 0
        for pair_num, adc_pair in enumerate(self.adc_pairs):
            if pair_num == voc_pair_num:
                v_adj = 1.0
            ch0_adc_corrected = (adc_pair[0] - self.adc_ch0_offset) * v_adj
            ch1_adc_corrected = adc_pair[1] - self.adc_ch1_offset
            if pair_num == 0:
                self.adc_pairs_corrected.append((ch0_adc_corrected,
                                                 ch1_adc_corrected))
                prev_adc0_corrected = ch0_adc_corrected
                prev_adc1_corrected = ch1_adc_corrected
                continue

            # Enforce no voltage decreases
            if ch0_adc_corrected < prev_adc0_corrected:
                ch0_adc_corrected = prev_adc0_corrected
                num_v_decreases += 1

            # Enforce no current increases
            if ch1_adc_corrected > prev_adc1_corrected:
                ch1_adc_corrected = prev_adc1_corrected
                num_i_increases += 1

            # Filter out dups
            if ((ch0_adc_corrected != prev_adc0_corrected) or
                    (ch1_adc_corrected != prev_adc1_corrected)):
                self.adc_pairs_corrected.append((ch0_adc_corrected,
                                                 ch1_adc_corrected))
            else:
                num_dups += 1

            prev_adc0_corrected = ch0_adc_corrected
            prev_adc1_corrected = ch1_adc_corrected

        self.logger.log("  Voltage decreases corrected: " +
                        str(num_v_decreases))
        self.logger.log("  Current increases corrected: " +
                        str(num_i_increases))
        self.logger.log("  Duplicates removed: " + str(num_dups))

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
                ohms = IV_Swinger.INFINITE_VAL
            self.data_points.append((amps, volts, ohms, watts))
            output_line = ("V=%.3f, I=%.3f, P=%.3f, R=%.3f" %
                           (volts, amps, watts, ohms))
            self.logger.log(output_line)

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
        self.adc_ch0_offset = self.adc_pairs[-1][1]
        self.adc_ch1_offset = self.adc_pairs[-1][1]
        for adc_pair in self.adc_pairs:
            if adc_pair[0] < self.adc_ch0_offset:
                self.adc_ch0_offset = adc_pair[0]
            if adc_pair[1] < self.adc_ch1_offset:
                self.adc_ch1_offset = adc_pair[1]

    # -------------------------------------------------------------------------
    def adc_sanity_check(self):
        """Method to do basic sanity checks on the ADC values
        """
        # Check for Voc = 0V
        if self.voc_adc - self.adc_ch0_offset == 0:
            self.logger.log("Voc is zero volts")
            return RC_ZERO_VOC

        # Check for Isc = 0A
        if self.isc_adc - self.adc_ch1_offset == 0:
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
        csv_data_pt_leaf_name = self.file_prefix + date_time_str + ".csv"

        # Get the full-path names of the HDD output files
        self.hdd_adc_pairs_csv_filename = os.path.join(dir,
                                                       adc_pairs_csv_leaf_name)
        self.hdd_csv_data_point_filename = os.path.join(dir,
                                                        csv_data_pt_leaf_name)

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
        self.cfg_set("Plotting", 'plot max x', self.plot_max_x)
        self.cfg_set("Plotting", 'plot max y', self.plot_max_y)
        self.cfg_set("Plotting", 'title', self.plot_title)

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

    # -------------------------------------------------------------------------
    def run(self):
        """Top-level method to run the IV Swinger 2"""

        # Configure logging
        self.configure_logging()

        # Find serial ports
        self.find_serial_ports()

        # Create and run the GUI. This blocks until the GUI is closed.
        GraphicalUserInterface(ivs2=self).start()

        # Terminate log file
        self.logger.terminate_log()


############
#   Main   #
############
def main():
    """Main function"""
    ivs2 = IV_Swinger2()
    # Override default property values
    ivs2.v_cal = 0.8561
    ivs2.i_cal = 1.1187
    ivs2.run()


# Boilerplate main() call
if __name__ == '__main__':
    main()
