#!/usr/bin/env python
"""IV Swinger plotter module"""
#
###############################################################################
#
# IV_Swinger_plotter.py: IV Swinger plotter module
#
# Copyright (C) 2016, 2017, 2019  Chris Satterlee
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
# This file contains a Python module for plotting data points previously
# captured by the IV Swinger. It can be run standalone on a Raspberry Pi
# or on any other platform with Python and the required libraries (numpy
# and matplotlib). By default it produces the same pyplot-generated PDF
# file that is produced by the IV Swinger immediately after each
# run. One reason for its existence is to be able to take data points
# from old runs and generate "new improved" graphs. For example, now
# that Catmull-Rom spline interpolation has been added, old PDFs that
# were generated with linear interpolation can be regenerated with
# spline interpolation.  Furthermore, it's not always clear if an
# "improvement" will work for all cases, so the ability to regression
# test it against old data sets is very useful.
#
# Additional values added are:
#
#     - The ability add the power curve to the same graph
#     - The ability to overlay up to 8 IV curves on a single graph
#     - Multiple options to customize the appearance of the graph:
#         - Chart title
#         - Curve names in legend
#         - Size of the plot, font sizes, point sizes, line width
#         - Fancy labels on Isc, Voc, and MPP
#         - Use linear interpolation
#
#  usage: IV_Swinger_plotter.py [-h] [-p] [-o] [-t TITLE] [-s SCALE]
#                               [-ps PLOT_SCALE] [-pxs PLOT_X_SCALE]
#                               [-pys PLOT_Y_SCALE] [-fs FONT_SCALE]
#                               [-pps POINT_SCALE] [-ls LINE_SCALE]
#                               [-n NAME] [-li] [-lv] [-lm] [-mw] [-fl]
#                               [-l] [--interactive] [--recalc_isc]
#                               CSV file or dir [CSV file or dir ...]
#
#  positional arguments:
#    CSV file or dir
#
#  optional arguments:
#    -h, --help            show this help message and exit
#    -p, --plot_power      Plot power with IV curve
#    -o, --overlay         Plot all IV curves on a single graph:
#                          overlaid<.pdf|.gif|.png>
#    -t TITLE, --title TITLE
#                          Title for plot
#    -s SCALE, --scale SCALE
#                          Scale everything by specified amount (no
#                          scaling = 1.0)
#    -ps PLOT_SCALE, --plot_scale PLOT_SCALE
#                          Scale plot by specified amount (no scaling =
#                          1.0)
#    -pxs PLOT_X_SCALE, --plot_x_scale PLOT_X_SCALE
#                          Scale plot width by specified amount (no scaling =
#                          1.0)
#    -pys PLOT_Y_SCALE, --plot_y_scale PLOT_Y_SCALE
#                          Scale plot height by specified amount (no scaling =
#                          1.0)
#    -fs FONT_SCALE, --font_scale FONT_SCALE
#                          Scale fonts by specified amount (no scaling =
#                          1.0)
#    -pps POINT_SCALE, --point_scale POINT_SCALE
#                          Scale plot points by specified amount (no
#                          scaling = 1.0)
#    -ls LINE_SCALE, --line_scale LINE_SCALE
#                          Scale plot line by specified amount (no
#                          scaling = 1.0)
#    -n NAME, --name NAME  Curve name(s) - can be used multiple times
#                          with --overlay
#    -on, --overlay_name   Name (without extension) for overlay file
#    -g, --gif             Generate GIF(s) rather than PDF(s)
#    -pn, --png            Generate PNG(s) rather than PDF(s)
#    -li, --label_all_iscs
#                          Label all Isc points (with --overlay)
#    -lv, --label_all_vocs
#                          Label all Voc points (with --overlay)
#    -lm, --label_all_mpps
#                          Label all MPPs (with --overlay)
#    -mw, --mpp_watts_only
#                          Label MPP(s) with watts only
#    -fl, --fancy_labels   Label Isc, Voc and MPP with fancy labels
#    -l, --linear          Use linear interpolation
#    --use_gnuplot         Use gnuplot instead of pyplot. Not recommended since
#                          many of the other options are not supported with
#                          gnuplot
#    --interactive         View output in interactive mode
#    --recalc_isc          Recalculate Isc using the overridden
#                          extrapolate_isc method
#
# The input is one or more CSV files in the format generated by the IV
# Swinger. If a directory is specified it must contain CSV files only,
# and they must all be in the expected format. The resulting PDF (or GIF
# or PNG) files are written to the directory in which the program is
# run.
#
# The IV_Swinger module is imported by this module. Since the IV_Swinger
# module imports the Adafruit_ADS1x15, Adafruit_CharLCD,
# Adafruit_MCP230xx and RPi.GPIO modules, those must be installed too -
# but only if the program is run on a Raspberry Pi (or other ARM-based
# platform).
#
import argparse
import os

import IV_Swinger


########################
#   Global functions   #
########################
def set_ivs_properties(args, ivs_extended):
    """Global function to set the IV Swinger properties"""
    # Set headless_mode to False if --interactive option is chosen
    if args.interactive:
        ivs_extended.headless_mode = False

    # Choose interpolation type
    if args.linear:
        ivs_extended.use_spline_interpolation = False
    else:
        ivs_extended.use_spline_interpolation = True

    # Set other properties based on commmand line options
    ivs_extended.plot_power = args.plot_power
    ivs_extended.plot_x_scale = (args.scale * args.plot_scale *
                                 args.plot_x_scale)
    ivs_extended.plot_y_scale = (args.scale * args.plot_scale *
                                 args.plot_y_scale)
    ivs_extended.font_scale = args.scale * args.font_scale
    ivs_extended.point_scale = args.scale * args.point_scale
    ivs_extended.line_scale = args.scale * args.line_scale
    if args.max_x is not None:
        ivs_extended.plot_max_x = args.max_x
    if args.max_y is not None:
        ivs_extended.plot_max_y = args.max_y
    ivs_extended.plot_title = args.title
    ivs_extended.names = args.name
    ivs_extended.label_all_iscs = args.label_all_iscs
    ivs_extended.label_all_vocs = args.label_all_vocs
    ivs_extended.label_all_mpps = args.label_all_mpps
    ivs_extended.mpp_watts_only = args.mpp_watts_only
    ivs_extended.fancy_labels = args.fancy_labels


def check_names(ivs_extended, csv_files):
    """Global function to check that if curve names were specified, the
       correct number were specified
    """
    if ivs_extended.names is not None:
        assert len(ivs_extended.names) == len(csv_files), \
            ("ERROR: {} names specified for {} curves"
             .format(len(ivs_extended.names), len(csv_files)))


#################
#   Classes     #
#################
# The PrintAndOrLog class
class PrintAndOrLog(object):
    """Class to provide static methods to print and/or log messages,
       depending on whether a logger is being used
    """
    @staticmethod
    def print_or_log_msg(logger, msg_str):
        """Method to either print or log a message. The message is just logged
           if there is a logger. Otherwise it is printed.
        """
        if logger is None:
            print msg_str
        else:
            logger.log(msg_str)

    @staticmethod
    def print_and_log_msg(logger, msg_str):
        """Method to either print only or print and log a message. The message
           is printed and logged if there is a logger. Otherwise it is
           just printed.
        """
        if logger is None:
            print msg_str
        else:
            logger.print_and_log(msg_str)


class CommandLineProcessor(object):
    """Class to parse the command line args. The args property returns
       the populated args namespace from argparse. The csv_files property
       returns the list of CSV file names.
    """
    def __init__(self):
        self._args = None
        self._csv_files = []

    @property
    def args(self):
        """Property to get the command line args"""
        if self._args is None:
            # Parse command line args
            parser = argparse.ArgumentParser()
            parser.add_argument("-p", "--plot_power", action="store_true",
                                help="Plot power with IV curve")
            parser.add_argument("-o", "--overlay", action="store_true",
                                help=("Plot all IV curves on a single graph: "
                                      "overlaid<.pdf|.gif|.png>"))
            parser.add_argument("-t", "--title", type=str,
                                help=("Title for plot"))
            parser.add_argument("-s", "--scale", type=float, default=1.0,
                                help=("Scale everything by specified amount "
                                      "(no scaling = 1.0)"))
            parser.add_argument("-ps", "--plot_scale", type=float, default=1.0,
                                help=("Scale plot by specified amount "
                                      "(no scaling = 1.0)"))
            parser.add_argument("-pxs", "--plot_x_scale", type=float,
                                default=1.0,
                                help=("Scale plot width by specified amount "
                                      "(no scaling = 1.0)"))
            parser.add_argument("-pys", "--plot_y_scale", type=float,
                                default=1.0,
                                help=("Scale plot height by specified amount "
                                      "(no scaling = 1.0)"))
            parser.add_argument("-mx", "--max_x", type=float, default=None,
                                help=("Hardcode X axis range to specified "
                                      "voltage"))
            parser.add_argument("-my", "--max_y", type=float, default=None,
                                help=("Hardcode Y axis range to specified "
                                      "current"))
            parser.add_argument("-fs", "--font_scale", type=float, default=1.0,
                                help=("Scale fonts by specified amount "
                                      "(no scaling = 1.0)"))
            parser.add_argument("-pps", "--point_scale", type=float,
                                default=1.0,
                                help=("Scale plot points by specified "
                                      "amount (no scaling = 1.0)"))
            parser.add_argument("-ls", "--line_scale", type=float, default=1.0,
                                help=("Scale plot line by specified "
                                      "amount (no scaling = 1.0)"))
            parser.add_argument("-n", "--name", type=str, action="append",
                                help=("Curve name(s) - can be used multiple "
                                      "times with --overlay"))
            parser.add_argument("-on", "--overlay_name", type=str,
                                default="overlaid",
                                help=("Name (without extension) for overlay "
                                      "file"))
            parser.add_argument("-g", "--gif", action="store_true",
                                help="Generate GIF(s) instead of PDF(s)")
            parser.add_argument("-pn", "--png", action="store_true",
                                help="Generate PNG(s) instead of PDF(s)")
            parser.add_argument("-li", "--label_all_iscs", action="store_true",
                                help="Label all Isc points (with --overlay)")
            parser.add_argument("-lv", "--label_all_vocs", action="store_true",
                                help="Label all Voc points (with --overlay)")
            parser.add_argument("-lm", "--label_all_mpps", action="store_true",
                                help="Label all MPPs (with --overlay)")
            parser.add_argument("-mw", "--mpp_watts_only", action="store_true",
                                help="Label MPP(s) with watts only")
            parser.add_argument("-fl", "--fancy_labels", action="store_true",
                                help=("Label Isc, Voc and MPP with "
                                      "fancy labels"))
            parser.add_argument("-l", "--linear", action="store_true",
                                help="Use linear interpolation")
            parser.add_argument("--use_gnuplot", action="store_true",
                                help=("Use gnuplot instead of pyplot. Not "
                                      "recommended since many of the other "
                                      "options are not supported with "
                                      "gnuplot"))
            parser.add_argument("--interactive", action="store_true",
                                help=("View output in interactive mode"))
            parser.add_argument("--recalc_isc", action="store_true",
                                help=("Recalculate Isc using the overridden "
                                      "extrapolate_isc method"))
            parser.add_argument("csv_files_or_dirs", metavar="CSV file or dir",
                                type=str, nargs="+")

            self._args = parser.parse_args()

        return self._args

    @property
    def csv_files(self):
        """Property to get the CSV file names"""
        if not self._csv_files:
            for arg in self.args.csv_files_or_dirs:
                if os.path.isfile(arg):
                    self._csv_files.append(arg)
                elif os.path.isdir(arg):
                    for (dirpath, _, filenames) in os.walk(arg):
                        for filename in sorted(filenames):
                            full_path_filename = os.path.join(dirpath,
                                                              filename)
                            self._csv_files.append(full_path_filename)
                        break
                else:
                    print ("ERROR: {} is neither a file nor a directory"
                           .format(arg))
                    exit(-1)

        return self._csv_files


class CsvParser(object):
    """Class to parse an IV Swinger-created CSV file and translate it to
       (I, V, R, P) tuple data points.
    """
    # pylint: disable=too-few-public-methods
    def __init__(self, csv_filename, logger=None):
        self.csv_filename = csv_filename
        self.logger = logger
        self._data_points = []

    @property
    def data_points(self):
        """Opens the CSV file and parses the voltage, current, power,
           and resistance values from each line and builds a data_points
           list with each data point being a (I, V, R, P) tuple.
        """
        if self._data_points == []:
            try:
                with open(self.csv_filename, "r") as f:
                    for ii, line in enumerate(f.read().splitlines()):
                        if ii == 0:
                            expected_first_line = "Volts, Amps, Watts, Ohms"
                            if line != expected_first_line:
                                err_str = ("ERROR: first line of CSV is not {}"
                                           .format(expected_first_line))
                                PrintAndOrLog.print_and_log_msg(self.logger,
                                                                err_str)
                                exit(-1)
                        else:
                            vipr_list = map(float, line.split(","))
                            if len(vipr_list) != 4:
                                err_str = ("ERROR: CSV line {} is not in "
                                           "expected V,I,P,R "
                                           "format".format(ii + 1))
                                PrintAndOrLog.print_and_log_msg(self.logger,
                                                                err_str)
                                exit(-1)
                            # Swap V <-> I and P <-> R
                            ivrp_tuple = (vipr_list[1], vipr_list[0],
                                          vipr_list[3], vipr_list[2])
                            self._data_points.append(ivrp_tuple)
            except IOError:
                print "Cannot open {}".format(self.csv_filename)
                exit(-1)

        return self._data_points


class IV_Swinger_extended(IV_Swinger.IV_Swinger):
    """Class to extend the IV_Swinger class for plotting old data sets (from
       CSV files) with the current interpolation, overlaying multiple
       curves on one graph, and more.

    """
    def __init__(self):
        IV_Swinger.IV_Swinger.__init__(self)
        self._data_points = []
        self._plt_img_filename = ""
        self._logger = None

    @property
    def data_points(self):
        """Property to get the data points"""
        return self._data_points

    @data_points.setter
    def data_points(self, value):
        self._data_points = value

    @property
    def plt_img_filename(self):
        """Property to get the plot image file name"""
        return self._plt_img_filename

    @plt_img_filename.setter
    def plt_img_filename(self, value):
        self._plt_img_filename = value

    @property
    def logger(self):
        """Logger object"""
        return self._logger

    @logger.setter
    def logger(self, value):
        self._logger = value

    def extrapolate_isc(self, data_points, max_watt_point_number):
        """If the --recalc_isc option is used, this method overrides the
           extrapolate_isc method in the IV_Swinger module. This is only
           useful if the code below is modified to be different from the
           IV_Swinger module code.
        """
        i1 = data_points[1][IV_Swinger.AMPS_INDEX]  # NONE data point
        v1 = data_points[1][IV_Swinger.VOLTS_INDEX]
        i2 = data_points[2][IV_Swinger.AMPS_INDEX]  # HALF data point
        v2 = data_points[2][IV_Swinger.VOLTS_INDEX]
        if v2 != v1 and max_watt_point_number > 3:
            isc_amps = i1 - ((i2 - i1) / (v2 - v1)) * v1
            if isc_amps > 1.02 * i1:
                isc_amps = 1.02 * i1
        else:
            isc_amps = i1
        isc_volts = 0
        isc_ohms = 0
        isc_watts = 0

        return (isc_amps, isc_volts, isc_ohms, isc_watts)

    def plot_graphs(self, args, csv_proc):
        """Method to generate the graph or graphs with pyplot or gnuplot
        """

        self.use_gnuplot = False
        if args.use_gnuplot:
            self.use_gnuplot = True
        if args.gif:
            plt_img_file_suffix = ".gif"
        elif args.png:
            plt_img_file_suffix = ".png"
        else:
            plt_img_file_suffix = ".pdf"
        gp_command_filename = "gp_command"
        if args.overlay:
            # Plot with pyplot or gnuplot
            self.plt_img_filename = args.overlay_name + plt_img_file_suffix
            self.plot_with_plotter(gp_command_filename,
                                   csv_proc.plt_data_point_files,
                                   self.plt_img_filename,
                                   csv_proc.plt_isc_amps,
                                   csv_proc.plt_voc_volts,
                                   csv_proc.plt_mpp_amps,
                                   csv_proc.plt_mpp_volts)
            msg_str = "Generated: {}".format(self.plt_img_filename)
            PrintAndOrLog.print_or_log_msg(self.logger, msg_str)

        else:
            for ii, csv_filename in enumerate(csv_proc.csv_files):
                plt_data_point_filename = csv_proc.plt_data_point_files[ii]
                isc_amps = csv_proc.plt_isc_amps[ii]
                voc_volts = csv_proc.plt_voc_volts[ii]
                mpp_amps = csv_proc.plt_mpp_amps[ii]
                mpp_volts = csv_proc.plt_mpp_volts[ii]
                # Plot with pyplot
                fn_wo_suffix = os.path.splitext(os.path.basename
                                                (csv_filename))[0]
                self.plt_img_filename = fn_wo_suffix + plt_img_file_suffix
                self.plot_with_plotter(gp_command_filename,
                                       [plt_data_point_filename],
                                       self.plt_img_filename,
                                       [isc_amps],
                                       [voc_volts],
                                       [mpp_amps],
                                       [mpp_volts])
                msg_str = "Generated: {}".format(self.plt_img_filename)
                PrintAndOrLog.print_or_log_msg(self.logger, msg_str)


class CsvFileProcessor(object):
    """Class to process all CSV files. The command line args, the list
       of CSV files, and an extended IV Swinger object are provided by the
       user at object creation. The proc_all_csv_files method is called at
       initialization; it uses the interpolator to generate the plotter
       data point files and compute or extract the Isc, Voc, and MPP
       values. It populates the results into the following attributes,
       which are available externally via properties:

           self._plt_data_point_files
           self._plt_isc_amps
           self._plt_voc_volts
           self._plt_mpp_amps
           self._plt_mpp_volts
    """
    # pylint: disable=too-many-instance-attributes
    def __init__(self, args, csv_files, ivs_extended, logger=None):
        self.args = args
        self.csv_files = csv_files
        self.ivs_extended = ivs_extended
        self.logger = logger
        self._plt_data_point_files = []
        self._plt_isc_amps = []
        self._plt_voc_volts = []
        self._plt_mpp_amps = []
        self._plt_mpp_volts = []
        # Process all CSV files
        self.proc_all_csv_files()

    def proc_one_csv_file(self, csv_filename):
        """Method to process a single CSV file"""

        msg_str = "Processing: {}".format(csv_filename)
        PrintAndOrLog.print_or_log_msg(self.logger, msg_str)

        # Create a CSV parser object and get the data points
        csv_parser = CsvParser(csv_filename, self.logger)
        data_points = csv_parser.data_points

        # Pass the data points to the extended IV Swinger object
        ivse = self.ivs_extended
        ivse.data_points = data_points

        # Optionally recalculate Isc
        if self.args.recalc_isc:
            # Find the measured point number with the highest power
            max_watt_point_number = (
                ivse.get_max_watt_point_number(data_points))

            # Extrapolate Isc value and store in first element of
            # data_points list
            data_points[0] = ivse.extrapolate_isc(data_points,
                                                  max_watt_point_number)

        # Extract the Isc value
        isc_amps = data_points[0][IV_Swinger.AMPS_INDEX]
        if data_points[0][IV_Swinger.VOLTS_INDEX] > 0.0:
            # If the first data point does not have a voltage of zero,
            # we don't know the Isc. Negating isc_amps has the effect of
            # not plotting the Isc point since the Y range starts at 0.
            # But its magnitude is maintained so the set_y_range method
            # can determine the appropriate max_y value.
            isc_amps = 0.0 - isc_amps

        # Extract the Voc value
        voc_volts = data_points[-1][IV_Swinger.VOLTS_INDEX]

        # Create an Interpolator object and call the appropriate
        # interpolation methods
        interpolator = IV_Swinger.Interpolator(data_points)
        if ivse.use_spline_interpolation:
            interp_points = interpolator.spline_interpolated_curve
            interpolated_mpp = interpolator.spline_interpolated_mpp
        else:
            interp_points = interpolator.linear_interpolated_curve
            interpolated_mpp = interpolator.linear_interpolated_mpp

        # Extract the MPP values
        mpp_amps = interpolated_mpp[IV_Swinger.AMPS_INDEX]
        mpp_volts = interpolated_mpp[IV_Swinger.VOLTS_INDEX]

        # Write the original and interpolated data points to the plotter
        # data file
        fn_wo_suffix = os.path.splitext(os.path.basename(csv_filename))[0]
        plt_data_point_filename = ("plt_{}".format(fn_wo_suffix))
        if os.path.isfile(plt_data_point_filename):
            os.remove(plt_data_point_filename)
        IV_Swinger.write_plt_data_points_to_file(plt_data_point_filename,
                                                 data_points,
                                                 new_data_set=False)
        IV_Swinger.write_plt_data_points_to_file(plt_data_point_filename,
                                                 interp_points,
                                                 new_data_set=True)

        self.plt_data_point_files.append(plt_data_point_filename)
        self.plt_isc_amps.append(isc_amps)
        self.plt_voc_volts.append(voc_volts)
        self.plt_mpp_amps.append(mpp_amps)
        self.plt_mpp_volts.append(mpp_volts)

    def proc_all_csv_files(self):
        """Method to process all the CSV files"""
        for csv_filename in self.csv_files:
            self.proc_one_csv_file(csv_filename)

    @property
    def plt_data_point_files(self):
        """Property to get the data point file names"""
        return self._plt_data_point_files

    @property
    def plt_isc_amps(self):
        """Property to get the list of Isc amps"""
        return self._plt_isc_amps

    @property
    def plt_voc_volts(self):
        """Property to get the list of Voc volts"""
        return self._plt_voc_volts

    @property
    def plt_mpp_amps(self):
        """Property to get the list of MPP amps"""
        return self._plt_mpp_amps

    @property
    def plt_mpp_volts(self):
        """Property to get the list of MPP volts"""
        return self._plt_mpp_volts


class IV_Swinger_plotter(object):
    """Main IV Swinger plotter class"""

    def __init__(self):
        self._max_x = None
        self._max_y = None
        self.cl_proc = None

    @property
    def max_x(self):
        """Maximum X-axis value (i.e. range in volts)
        """
        return self._max_x

    @max_x.setter
    def max_x(self, value):
        self._max_x = value

    @property
    def max_y(self):
        """Maximum Y-axis value (i.e. range in amps)
        """
        return self._max_y

    @max_y.setter
    def max_y(self, value):
        self._max_y = value

    def run(self):
        """Main method to run the IV Swinger plotter"""
        # Get command line args
        self.cl_proc = CommandLineProcessor()
        args = self.cl_proc.args

        # Get CSV file name(s) and/or directory name(s)
        csv_files = self.cl_proc.csv_files

        # Create extended IV Swinger object
        ivs_extended = IV_Swinger_extended()
        set_ivs_properties(args, ivs_extended)

        # Check for correct number of --name options
        check_names(ivs_extended, csv_files)

        # Process all CSV files
        csv_proc = CsvFileProcessor(args, csv_files, ivs_extended)

        # Plot graphs
        ivs_extended.plot_graphs(args, csv_proc)


############
#   Main   #
############
def main():
    """Main function"""
    ivp = IV_Swinger_plotter()
    ivp.run()


# Boilerplate main() call
if __name__ == "__main__":
    main()
