#!/usr/bin/env python
"""IV Swinger2 PV modeling module"""
#
###############################################################################
#
# IV_Swinger2_PV_model.py: IV Swinger 2 PV modeling module
#
# Copyright (C) 2020, 2021  Chris Satterlee
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
# This module adds IV Swinger 2 specific features to the
# IV_Swinger_PV_model.py module.
#
import os
from pathlib import Path
import IV_Swinger_PV_model
import IV_Swinger

#################
#   Constants   #
#################
PV_MODEL_CURVE_NUM_POINTS = 100
NOC_IRRAD = IV_Swinger_PV_model.NOC_IRRAD


#################
#   Classes     #
#################
class IV_Swinger2_PV_model(IV_Swinger_PV_model.PV_model):
    """Class that extends the IV_Swinger_PV_model for use with the IV
       Swinger 2 application code.
    """
    # pylint: disable=too-many-instance-attributes
    def __init__(self):
        super().__init__()
        self.data_points = []
        # Property variables
        self._csv_filename = None

    # Properties
    # ---------------------------------
    @property
    def csv_filename(self):
        """File name of CSV file to write data points.
        """
        return self._csv_filename

    @csv_filename.setter
    def csv_filename(self, value):
        self._csv_filename = value

    # Derived properties

    # Methods
    def get_data_points(self, num_points):
        """Method to populate the data_points attribute with (amps, volts,
           ohms, watts) tuples. This is the canonical format for data
           points in the IV Swinger code.
        """
        self.data_points = []
        for vi_point in self.gen_vi_points(num_points):
            volts, amps = vi_point
            ohms = volts / amps if amps != 0.0 else IV_Swinger.INFINITE_VAL
            watts = volts * amps
            self.data_points.append((amps, volts, ohms, watts))

    def gen_data_points_csv(self):
        """Method to generate the standard data points CSV file for the modeled
           IV curve.
        """
        IV_Swinger.write_csv_data_points_to_file(self.csv_filename,
                                                 self.data_points)


############
#   Main   #
############
def main():
    """Main function"""
    def plot_and_view_modeled_curve(pv):
        """Local function to plot the modeled curve and view the PDF. The PV
           model must be run and its get_data_points() method called
           before calling this function. Files are created in the same
           directory as the model's CSV file containing the modeled data
           points.
        """
        # Create plotter object and run it to create PDF
        ivp = IV_Swinger2.IV_Swinger2_plotter()
        ivp.title = pv.title_string
        ivp.csv_files = [pv.csv_filename]
        ivp.curve_names = [pv.parms_string_w_newlines]
        ivp.plot_dir = os.path.dirname(pv.csv_filename)
        ivp.linear = False
        ivp.point_scale = 0.0  # Change to 1.0 to see the points
        ivp.generate_gif = False
        ivp.run()

        # View the PDF and clean up
        basename, _ = os.path.splitext(os.path.basename(pv.csv_filename))
        IV_Swinger2.sys_view_file(f"{basename}.pdf")
        Path(f"plt_{basename}").unlink()

    # Create the PV spec CSV file in the current directory
    pv_spec_file = os.path.join(f"{Path.cwd()}",
                                "IV_Swinger2_PV_model_pv_spec.csv")
    IV_Swinger_PV_model.create_pv_spec_file(pv_spec_file)

    # Create a PV model object
    pv = IV_Swinger2_PV_model()

    # Populate the spec values in the model from an entry in the CSV
    # file
    pv_name = "SunPower X21-345"
    pv.get_spec_vals(pv_name, pv_spec_file)

    # Set the irradiance and temperature to model. For this example, use
    # NOC values so we can compare the model to the spec
    pv.irradiance = NOC_IRRAD
    pv.cell_temp_c = pv.noct

    # Run the model. Generate a curve with 100 points. Write those
    # points to a CSV file. Plot the curve and view the PDF.
    pv.run()
    pv.get_data_points(PV_MODEL_CURVE_NUM_POINTS)
    pv.csv_filename = os.path.join(f"{Path.cwd()}",
                                   "IV_Swinger2_PV_model.csv")
    pv.gen_data_points_csv()
    plot_and_view_modeled_curve(pv)


# Boilerplate main() call
if __name__ == '__main__':
    # pylint: disable=cyclic-import
    import IV_Swinger2
    main()
