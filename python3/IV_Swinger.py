#!/usr/bin/env python
"""IV Swinger control module"""
# pylint: disable=too-many-lines
#
###############################################################################
#
# IV_Swinger.py: IV Swinger control module
#
# Copyright (C) 2016-2023  Chris Satterlee
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
# NOTE: This module was originally written for IV Swinger 1, which is no
# longer supported. All code that was specific to IVS1 has been removed,
# leaving only the code that is used for IVS2 (mostly plotting code.)
# See Issue #213 in the csatt/IV_Swinger GitHub repository.
#
###############################################################################
#
#
import datetime as dt
from contextlib import suppress
import math
import platform
import re
import sys
import warnings
import numpy as np

import matplotlib.pyplot as plt
import matplotlib.font_manager
from matplotlib import __version__ as matplotlib_version
from matplotlib import use
use("pdf")
with suppress(ImportError):
    from icecream import ic

#################
#   Constants   #
#################

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

MAX_I_RATIO_DEFAULT = 1.3
MAX_V_RATIO_DEFAULT = 1.2
PLOT_DPI_DEFAULT = 100
PLOT_X_INCHES_DEFAULT = 11.0
PLOT_X_PIXELS_DEFAULT = PLOT_DPI_DEFAULT * PLOT_X_INCHES_DEFAULT
PLOT_Y_INCHES_DEFAULT = 8.5
PLOT_X_SCALE = 1.0
PLOT_Y_SCALE = 1.0
FONT_NAME_DEFAULT = "Arial Unicode MS"
TITLE_FONTSIZE_DEFAULT = 14
AXISLABEL_FONTSIZE_DEFAULT = 11
TICKLABEL_FONTSIZE_DEFAULT = 9
POINT_LABEL_FONTSIZE_DEFAULT = 11
LEGEND_FONTSIZE_DEFAULT = 9
FONT_SCALE_DEFAULT = 1.0
POINT_SCALE_DEFAULT = 1.0
LINE_SCALE_DEFAULT = 1.0

# Data point list
AMPS_INDEX = 0
VOLTS_INDEX = 1
OHMS_INDEX = 2
WATTS_INDEX = 3


#############
#   Debug   #
#############
with suppress(NameError):
    ic.configureOutput(includeContext=True)


########################
#   Global functions   #
########################
def write_csv_data_points_to_file(filename, data_points):
    """Global function to write each of the CSV data points to the output
       file.
    """
    file_contents = "Volts, Amps, Watts, Ohms\n"  # Headings
    for data_point in data_points:
        volts = data_point[VOLTS_INDEX]
        amps = data_point[AMPS_INDEX]
        watts = data_point[WATTS_INDEX]
        ohms = data_point[OHMS_INDEX]
        file_contents += f"{volts:.6f},{amps:.6f},{watts:.6f},{ohms:.6f}\n"
    filename.write_text(file_contents, encoding="utf-8")


def write_plt_data_to_file(open_filehandle, volts, amps,
                           watts, new_data_set=False):
    """Global function to write/append the current voltage and current
       readings to an output file which the caller has opened for
       appending and has passed the filehandle.  If new_data_set=True,
       then the other values are ignored and two blank lines are
       appended to the file.
    """
    output_line = f"{volts:.6f} {amps:.6f} {watts:.6f}\n"
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
    with filename.open("a", encoding="utf-8") as f:
        # Add new data set delimiter
        if new_data_set:
            write_plt_data_to_file(f, 0, 0, 0, new_data_set=True)

        prev_vals = ""
        for data_point in data_points:
            curr_vals = (f"{data_point[VOLTS_INDEX]:.6f} "
                         f"{data_point[AMPS_INDEX]:.6f} "
                         f"{data_point[WATTS_INDEX]:.6f}\n")
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


def read_measured_and_interp_points(df):
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
    for line in df.read_text(encoding="utf-8").splitlines():
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


def mantissa_and_exp(value, figs):
    """Global function to return the scientific notation mantissa and
       exponent of the provided value
    """
    man, exp = f"{value:.{figs}e}".split('e')
    return (float(man), int(exp))


def get_tick_step(max_val):
    """Global function to return the step value for the X and Y axis plot
       ticks given the maximum value of the axis. The only step values
       generated are 1, 2, and 5 (times the appropriate power of 10.)
    """
    max_steps = 15
    man, exp = mantissa_and_exp(max_val * 10.0/max_steps, 2)
    if man <= 2:
        step = float(f"2e{exp - 1}")
    elif man <= 5:
        step = float(f"5e{exp - 1}")
    else:
        step = float(f"1e{exp}")
    return step


def sigfigs(number, figs):
    """Global function to convert a numerical value to a string with the
       given number of significant figures
    """
    # The following one-liner is pretty good. Numerically, the value is
    # correctly rounded to the requested number of significant
    # figures. But if the rounding happens to the left of the decimal
    # point, it still includes the decimal point and a zero after it,
    # and that implies more precision than it should. And if the
    # rounding happens to the right of the decimal point, there can be
    # missing significant trailing zeros.
    initial_result_str = f"{float(f'{number:.{figs}g}')}"

    # Fix the issues mentioned above
    if "e" in initial_result_str or initial_result_str == "0.0":
        return initial_result_str
    integer_part, decimal_part = initial_result_str.split(".")
    if integer_part == "0":
        num_added_zeros = figs - len(decimal_part)
    else:
        if len(integer_part) >= figs:
            return integer_part
        num_added_zeros = figs - len(integer_part) - len(decimal_part)
    return initial_result_str + "0" * num_added_zeros


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

    @staticmethod
    def extract_date_time_str(input_str):
        """Method to parse the date/time string from a leaf file name or
           other string (or pathlib Path)
        """
        dt_file_re = re.compile(r"(\d{6}_\d{2}_\d{2}_\d{2})")
        match = dt_file_re.search(str(input_str))
        if match:
            return match.group(1)
        return "No match"

    @staticmethod
    def is_date_time_str(input_str):
        """Method to test if a given string (or pathlib Path) is a date/time
           string
        """
        dt_file_re = re.compile(r"^(\d{6}_\d{2}_\d{2}_\d{2})$")
        match = dt_file_re.search(str(input_str))
        if match:
            return True
        return False

    @staticmethod
    def xlate_date_time_str(date_time_str):
        """Method to translate a date_time_str from yymmdd_hh_mm_ss
           format to a more readable format
        """
        yymmdd, hh, mm, ss = date_time_str.split("_")
        date_str = f"{yymmdd[2:4]}/{yymmdd[4:6]}/{yymmdd[0:2]}"
        time_str = f"{hh}:{mm}:{ss}"
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
        with self.log_file_name.open("a", encoding="utf-8") as f:
            f.write(f"\n{date_time_str}: {print_str}")

    def print_and_log(self, print_str):
        """Print to the screen (if there is one) and also to a log file
        """
        # Print to screen
        print(print_str)

        # Print to log file with timestamp
        self.log(print_str)


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
                new_i_vals = np.linspace(given_point[AMPS_INDEX],
                                         next_point[AMPS_INDEX],
                                         num_interp_points + 1,
                                         endpoint=False).tolist()
                # Get a list of all the interpolated V values
                new_v_vals = np.linspace(given_point[VOLTS_INDEX],
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
            vi_points_list = [([point[VOLTS_INDEX], point[AMPS_INDEX]])
                              for point in self.given_points] or []

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
        p_0, p_1, p_2, p_3 = list(map(np.array, [four_points[0],
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
        t = np.linspace(t_1, t_2, num_interp_points)

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
        self._vdiv_r1 = None
        self._vdiv_r2 = None
        self._amm_op_amp_rf = None
        self._amm_op_amp_rg = None
        self._amm_shunt_max_volts = None
        self._amm_shunt_max_amps = None
        self._plot_colors = []
        self._use_spline_interpolation = True
        self._plot_power = False
        self._plot_ref = False
        self._max_i_ratio = MAX_I_RATIO_DEFAULT
        self._max_v_ratio = MAX_V_RATIO_DEFAULT
        self._plot_dpi = PLOT_DPI_DEFAULT
        self._plot_max_x = None
        self._plot_max_y = None
        self._plot_x_inches = PLOT_X_INCHES_DEFAULT
        self._plot_y_inches = PLOT_Y_INCHES_DEFAULT
        self._plot_x_scale = PLOT_X_SCALE
        self._plot_y_scale = PLOT_Y_SCALE
        self._plot_title = None
        self._names = None
        self._label_all_iscs = False
        self._label_all_vocs = False
        self._label_all_mpps = False
        self._mpp_watts_only = False
        self._fancy_labels = True
        self._font_name = FONT_NAME_DEFAULT
        self._title_fontsize = TITLE_FONTSIZE_DEFAULT
        self._axislabel_fontsize = AXISLABEL_FONTSIZE_DEFAULT
        self._ticklabel_fontsize = TICKLABEL_FONTSIZE_DEFAULT
        self._isclabel_fontsize = POINT_LABEL_FONTSIZE_DEFAULT
        self._voclabel_fontsize = POINT_LABEL_FONTSIZE_DEFAULT
        self._mpplabel_fontsize = POINT_LABEL_FONTSIZE_DEFAULT
        self._legend_fontsize = LEGEND_FONTSIZE_DEFAULT
        self._font_scale = FONT_SCALE_DEFAULT
        self._point_scale = POINT_SCALE_DEFAULT
        self._line_scale = LINE_SCALE_DEFAULT
        self._v_sat = None
        self._i_sat = None
        self._ax1 = None
        self._ax2 = None
        self._filehandle = None
        self._output_line = None
        self.mp_kwargs = None
        self.logger = None
        self.os_version = platform.platform()
        arch_word_size = 64 if sys.maxsize > 2 ** 32 else 32
        self.python_version = (
            f"{sys.version_info[0]}.{sys.version_info[1]}."
            f"{sys.version_info[2]} ({arch_word_size}-bit)")
        try:
            self.matplotlib_version = matplotlib_version
        except NameError:
            self.matplotlib_version = "N/A"
        self.numpy_version = np.__version__

    # Properties
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
    def amm_shunt_max_amps(self, value):
        self._amm_shunt_max_amps = value

    @property
    def amm_shunt_resistance(self):
        """Resistance of shunt resistor"""
        amm_shunt_resistance = (self._amm_shunt_max_volts /
                                self._amm_shunt_max_amps)
        return amm_shunt_resistance

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
    def max_i_ratio(self, value):
        self._max_i_ratio = value

    @property
    def max_v_ratio(self):
        """Ratio of V-axis range to Voc
        """
        return self._max_v_ratio

    @max_v_ratio.setter
    def max_v_ratio(self, value):
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
    def plot_x_inches(self, value):
        self._plot_x_inches = value

    @property
    def plot_y_inches(self):
        """Height of plot in inches
        """
        return self._plot_y_inches

    @plot_y_inches.setter
    def plot_y_inches(self, value):
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
    def title_fontsize(self, value):
        self._title_fontsize = value

    @property
    def axislabel_fontsize(self):
        """Property to set font size of axis labels"""
        return self._axislabel_fontsize

    @axislabel_fontsize.setter
    def axislabel_fontsize(self, value):
        self._axislabel_fontsize = value

    @property
    def ticklabel_fontsize(self):
        """Property to set font size of axis tick labels"""
        return self._ticklabel_fontsize

    @ticklabel_fontsize.setter
    def ticklabel_fontsize(self, value):
        self._ticklabel_fontsize = value

    @property
    def isclabel_fontsize(self):
        """Property to set font size of Isc label"""
        return self._isclabel_fontsize

    @isclabel_fontsize.setter
    def isclabel_fontsize(self, value):
        self._isclabel_fontsize = value

    @property
    def voclabel_fontsize(self):
        """Property to set font size of Voc label"""
        return self._voclabel_fontsize

    @voclabel_fontsize.setter
    def voclabel_fontsize(self, value):
        self._voclabel_fontsize = value

    @property
    def mpplabel_fontsize(self):
        """Property to set font size of MPP label"""
        return self._mpplabel_fontsize

    @mpplabel_fontsize.setter
    def mpplabel_fontsize(self, value):
        self._mpplabel_fontsize = value

    @property
    def legend_fontsize(self):
        """Property to set font size of legend"""
        return self._legend_fontsize

    @legend_fontsize.setter
    def legend_fontsize(self, value):
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
    def plot_with_plotter(self, data_point_filenames, img_filename,
                          isc_amps, voc_volts, mpp_amps, mpp_volts):
        """Method to generate the graph with pyplot (gnuplot is no longer
           supported)

           The following parameters are lists:

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
        self.check_plot_with_plotter_args(data_point_filenames,
                                          isc_amps, voc_volts, mpp_amps,
                                          mpp_volts)

        # Call the plot method
        self.plot_with_pyplot_with_retry(data_point_filenames,
                                         img_filename, isc_amps,
                                         voc_volts, mpp_amps, mpp_volts)

    # -------------------------------------------------------------------------
    def get_and_log_pyplot_font_names(self):
        """Method to get the list of font names (families) available for pyplot
           plots. The list is returned to the caller (as a string with
           newlines) and is also written to the log file.
        """
        fonts = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
        font_names_str = ", ".join(sorted(fonts))
        self.logger.log(f"Plotting fonts:\n{font_names_str}")
        return font_names_str

    # -------------------------------------------------------------------------
    def set_pyplot_font_name(self):
        """Method to set the font name (family) for pyplot plots"""
        plt.rc('font', family=self.font_name)

    # -------------------------------------------------------------------------
    def plot_with_pyplot(self, data_point_filenames, img_filename,
                         isc_amps, voc_volts, mpp_amps, mpp_volts):
        """Method to generate the graph with pyplot.

           The following parameters are lists:

              data_point_filenames
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
        self.set_figure_title(data_point_filenames)

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
        self.plot_points_and_curves(data_point_filenames, mpp_volts)

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
        self.print_to_img_file(img_filename)

        # Clear the figure in preparation for the next plot
        plt.clf()

    # -------------------------------------------------------------------------
    def plot_with_pyplot_with_retry(self, data_point_filenames,
                                    img_filename, isc_amps, voc_volts,
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
                self.plot_with_pyplot(data_point_filenames, img_filename,
                                      isc_amps, voc_volts, mpp_amps, mpp_volts)
        except RuntimeError as e:
            if str(e) == "TrueType font is missing table":
                plt.clf()
                self.logger.print_and_log(f"Couldn't create {img_filename} "
                                          f"with font {self.font_name}; using "
                                          f"default font")
                self.font_name = FONT_NAME_DEFAULT
                self.plot_with_pyplot(data_point_filenames, img_filename,
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
    def check_plot_with_plotter_args(self, data_point_filenames,
                                     isc_amps, voc_volts, mpp_amps,
                                     mpp_volts):
        """Method to check the args passed to the plot_with_pyplot method
           (gnuplot no longer supported)
        """
        # pylint: disable=too-many-arguments

        max_len = len(self.plot_colors)
        assert len(data_point_filenames) <= max_len, \
            f"Max of {max_len} curves supported"
        assert len(isc_amps) == len(data_point_filenames), \
            "isc_amps list must be same size as data_point_filenames list"
        assert len(voc_volts) == len(data_point_filenames), \
            "voc_volts list must be same size as data_point_filenames list"
        assert len(mpp_amps) == len(data_point_filenames), \
            "mpp_amps list must be same size as data_point_filenames list"
        assert len(mpp_volts) == len(data_point_filenames), \
            "mpp_volts list must be same size as data_point_filenames list"

    # -------------------------------------------------------------------------
    def set_figure_size(self):
        """Method to set the plotter figure size"""

        # Set the figure size to 11 x 8.5 (optionally scaled)
        scaled_x_inches = self.plot_x_inches * self.plot_x_scale
        scaled_y_inches = self.plot_y_inches * self.plot_y_scale
        plt.gcf().set_size_inches(scaled_x_inches, scaled_y_inches)

    # -------------------------------------------------------------------------
    def set_figure_title(self, data_point_filenames):
        """Method to set the plotter figure title"""
        if len(data_point_filenames) > 1 and not self.plot_ref:
            run_str = f"{len(data_point_filenames)} Runs"
        else:
            filename = (data_point_filenames[0] if not self.plot_ref else
                        data_point_filenames[1])
            run_str = f"{filename}"
            date_time_str = DateTimeStr.extract_date_time_str(run_str)
            if date_time_str == "No match":
                run_str += " Run"
            else:
                (date_str,
                 time_str) = DateTimeStr.xlate_date_time_str(date_time_str)
                run_str = f"{date_str}@{time_str}"
        if self.plot_title is None:
            title_str = f"IV Swinger Plot for {run_str}"
        else:
            title_str = self.plot_title
        fontsize = self.title_fontsize * self.font_scale
        plt.title(title_str, fontsize=fontsize, y=1.02)

    # -------------------------------------------------------------------------
    def set_x_label(self):
        """Method to set the plotter X axis label"""
        x_label = "Voltage (volts)"
        fontsize = self.axislabel_fontsize * self.font_scale
        plt.xlabel(x_label, fontsize=fontsize)

    # -------------------------------------------------------------------------
    def set_y_label(self):
        """Method to set the plotter Y axis label"""
        y_label = "Current (amps)"
        fontsize = self.axislabel_fontsize * self.font_scale
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
                if volts * self.max_v_ratio > max_x:
                    max_x = volts * self.max_v_ratio

        # Round max_x to 2 significant figures
        max_x = float(sigfigs(max_x, 2))

        if max_x > 0:
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
                # The isc_amps value is negative when we want to
                # suppress plotting the Isc point. But we still need its
                # magnitude to determine the max_y value, so we use
                # abs().
                if abs(amps) * self.max_i_ratio > max_y:
                    max_y = abs(amps) * self.max_i_ratio

        # Round max_y to 2 significant figures
        max_y = float(sigfigs(max_y, 2))

        if max_y > 0:
            plt.ylim(0, max_y)

        self.plot_max_y = max_y
        return max_y

    # -------------------------------------------------------------------------
    def set_x_ticks(self, max_x):
        """Method to set the plotter X-axis ticks"""
        step = get_tick_step(max_x)
        fontsize = self.ticklabel_fontsize * self.font_scale
        plt.xticks(np.arange(0, max_x, step), fontsize=fontsize)

    # -------------------------------------------------------------------------
    def set_y_ticks(self, max_y):
        """Method to set the plotter Y-axis ticks"""
        step = get_tick_step(max_y)
        fontsize = self.ticklabel_fontsize * self.font_scale
        plt.yticks(np.arange(0, max_y, step), fontsize=fontsize)

    # -------------------------------------------------------------------------
    def display_grid(self):
        """Method to display the plotter grid"""
        plt.grid(True)

    # -------------------------------------------------------------------------
    def set_annotate_options(self):
        """Method to set the plotter annotation options (for Isc, Voc,
           and MPP labels)
        """
        if self.fancy_labels:
            xytext_offset = 10
            bbox = {"boxstyle": 'round', "facecolor": 'yellow'}
            arrowprops = {"arrowstyle": '->'}
        else:
            xytext_offset = 0
            bbox = {"boxstyle": 'square, pad=0',
                    "facecolor": 'white', "edgecolor": 'white'}
            arrowprops = None

        return (xytext_offset, bbox, arrowprops)

    # -------------------------------------------------------------------------
    def plot_and_label_isc(self, isc_amps, xytext_offset, bbox, arrowprops):
        """Method to plot and label/annotate the Isc point(s)"""
        fontsize = self.isclabel_fontsize * self.font_scale
        prev_isc_str_width = 0
        for ii, isc_amp in enumerate(isc_amps):
            # Round isc_amp to 3 significant figures
            isc_str = f"Isc = {sigfigs(isc_amp, 3)} A"
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
            # Round mpp_volts to 3 significant figures
            mppv_str = f"{sigfigs(mpp_volts[ii], 3)}"
            # Round mpp_amp to 3 significant figures
            mppa_str = f"{sigfigs(mpp_amp, 3)}"
            # Create (V * A) string from those
            mpp_volts_x_amps_str = f" ({mppv_str} * {mppa_str})"
            if self.mpp_watts_only:
                mpp_volts_x_amps_str = ""
            mpp_watts = mpp_volts[ii] * mpp_amp
            # Round mpp_watts to 3 significant figures
            mppw_str = f"{sigfigs(mpp_watts, 3)}"
            mpp_str = f"MPP = {mppw_str} W{mpp_volts_x_amps_str}"
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
            # Round voc_volt to 3 significant figures
            voc_str = f"Voc = {sigfigs(voc_volt, 3)} V"
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
    def plot_points_and_curves(self, data_point_filenames, mpp_volts):
        """Method to read the data in each data point file and use
           pyplot to plot the measured and interpolated curves
        """
        for curve_num, df in enumerate(data_point_filenames):
            # Read points from the file
            (measured_volts,
             measured_amps,
             _,
             interp_volts,
             interp_amps,
             interp_watts) = read_measured_and_interp_points(df)

            # Put measured points label at top of legend
            if not curve_num and self.point_scale:
                self.get_measured_points_kwargs()
                self.add_measured_points_label()

            # Plot interpolated curve first, so it is "under" the
            # measured points
            self.plot_interp_points(curve_num, df,
                                    data_point_filenames,
                                    interp_volts, interp_amps)

            # Plot measured points and (optionally) power curve (except
            # for reference curve, which is curve_num = 0)
            if not self.plot_ref or curve_num:
                self.plot_measured_points(measured_volts, measured_amps)

                # Plot power curve (except for reference curve)
                if self.plot_power:
                    # Plot power curve
                    self.plot_power_curve(curve_num, interp_volts,
                                          interp_watts, mpp_volts)

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
    def plot_measured_points(self, measured_volts, measured_amps):
        """Method to plot the measured points"""
        if self.point_scale == 0.0:
            # Skip plotting points altogether if scale is zero
            return
        # Plot without label, which was added by
        # add_measured_points_label()
        plt.plot(measured_volts, measured_amps, **self.mp_kwargs)

    # -------------------------------------------------------------------------
    def plot_interp_points(self, curve_num, df, data_point_filenames,
                           interp_volts, interp_amps):
        """Method to plot the interpolated points"""
        # pylint: disable=too-many-arguments
        # pylint: disable=too-many-branches

        if self.line_scale == 0.0:
            # Skip plotting curve altogether if scale is zero
            return
        if self.names is None:
            if len(data_point_filenames) > 1:
                interp_label = df
                date_time_str = DateTimeStr.extract_date_time_str(df)
                if date_time_str != "No match":
                    (date_str,
                     time_str) = DateTimeStr.xlate_date_time_str(date_time_str)
                    interp_label = f"{date_str}@{time_str}"
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
        _, max_y_exp = mantissa_and_exp(self.plot_max_y, 3)
        label_chars = int(3 - max_y_exp)
        lr_margin_add = 0.06 * label_chars
        left_adj = (margin_width + lr_margin_add) / xsize
        right_adj = 1.0 - (margin_width + lr_margin_add) / xsize
        top_adj = 1.0 - margin_width / ysize
        bottom_adj = margin_width / ysize
        plt.subplots_adjust(left=left_adj, right=right_adj,
                            top=top_adj, bottom=bottom_adj)

    # -------------------------------------------------------------------------
    def print_to_img_file(self, img_filename):
        """Method to print the plot to the image file"""
        plt.savefig(img_filename, dpi=self.plot_dpi)

    # -------------------------------------------------------------------------
    @staticmethod
    def close_plots():
        """Static method to close all plots. This is required on Windows
           before exiting a Tkinter GUI that has used the plotter or
           else it throws some strange errors and hangs on exit.
        """
        plt.close("all")


############
#   Main   #
############
def main():
    """Main function"""
    print("IV Swinger 1 is no longer supported. See Issue #213.")


# Boilerplate main() call
if __name__ == "__main__":
    main()
