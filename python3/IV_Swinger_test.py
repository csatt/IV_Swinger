#!/usr/bin/env python
"""IV Swinger test module"""
#
###############################################################################
#
# IV_Swinger_test.py: IV Swinger test module
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
# The IV Swinger is an open source hardware and software project
#
# Permission to use the hardware design is granted under the terms of
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
# This file contains an example of Python code that imports the
# IV_Swinger module and defines an IV_Swinger_test class that is derived
# from the IV_Swinger class. The derived class overrides some of the
# property values and overrides one of the class methods (shut_down).
#
# The purpose of including this module in the GitHub distribution is to
# provide an example of how these things are done. But this is actually
# a useful module for testing changes to the IV_Swinger
# module. Overriding the shut_down method prevents exceptions from
# shutting down the Raspberry Pi. (Alternately, setting shutdown_on_exit
# to False can be used)
import IV_Swinger
import time

class IV_Swinger_test(IV_Swinger.IV_Swinger):
    """IV_Swinger derived class for testing"""
    def __init__(self):
        IV_Swinger.IV_Swinger.__init__(self)
        # Override default property values
        self.vdiv_r1 = 178900.0  # tweaked based on DMM measurement
        self.vdiv_r2 = 8200.0    # tweaked based on DMM measurement
        self.vdiv_r3 = 5595.0    # tweaked based on DMM measurement
        self.amm_op_amp_rf = 82100.0  # tweaked based on DMM measurement
        self.amm_op_amp_rg = 1499.0   # tweaked based on DMM measurement
        #self.shutdown_on_exit = False
        self.use_spline_interpolation = False
        self.loads_to_skip = 1

    def shut_down(self, lock_held=True):
        print "Trying to shut down"
        try:
            if not lock_held:
                self.lock.acquire()
            msg_text = "Shutting down\nnow!!"
            lcd_msg = IV_Swinger.ScrollingMessage(msg_text,
                                                  self.lcd,
                                                  beep=False,
                                                  lock=None)
            lcd_msg.start()
        finally:
            time.sleep(2)
            #os.system("shutdown -h now")
            print "TESTING - NOT REALLY SHUTTING DOWN"
            time.sleep(5)
            lcd_msg.stop()
            self.reset_lcd()


############
#   Main   #
############
def main():
    """Main function"""
    ivs = IV_Swinger_test()
    ivs.run()

# Boilerplate main() call
if __name__ == '__main__':
    main()
