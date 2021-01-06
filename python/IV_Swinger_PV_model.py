#!/usr/bin/env python
"""IV Swinger PV modeling module"""
# pylint: disable=too-many-lines
#
###############################################################################
#
# IV_Swinger_PV_model.py: IV Swinger PV modeling module
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
# This file contains Python code that models PV modules or cells. It is
# part of the IV Swinger project, but has no dependencies on other code
# from that project. Therefore it may be imported and used for other
# unrelated projects without importing the other IV Swinger modules.
#
# The main purpose of this module is to predict the IV curve of a PV
# module/cell given its datasheet values and the irradiance and cell
# temperature conditions under which it is operating. When compared to a
# measured IV curve, this "reference" IV curve can be used to evaluate
# the performance of the PV under test. This modeling is not a trivial
# task. There are many research papers devoted to the topic. I primarily
# studied the following papers:
#
#    Ibrahim, Haider & Anani, Nader. (2017). Variations of PV module
#    parameters with irradiance and temperature. Energy
#    Procedia. 134. 10.1016/j.egypro.2017.09.617.
#
#    De Soto, W. & Klein, S.A. & Beckman, W.A.. (2006). Improvement and
#    validation of a model for photovoltaic array performance. Solar
#    Energy. 80. 78-88. 10.1016/j.solener.2005.06.010.
#
# This code (like most of the research papers) uses the "single-diode"
# circuit model for PV cells. A 2-diode circuit model is slightly more
# accurate, but makes the mathematics too complex to be justified (and
# it is bad enough with the single-diode model). The following equation
# defines the relationship between current and voltage for the
# single-diode model.
#
#   I = IL - I0 * [e^((V + I*Rs)/(n*Ns*Vth)) - 1] - (V + I*Rs)/Rsh
#
# where:
#        I = output current
#        V = output voltage
#       IL = light current aka photocurrent
#       I0 = diode reverse saturation current
#       Rs = series resistance
#      Rsh = shunt (parallel) resistance
#        n = diode ideality factor
#       Ns = number of series-connected cells
#      Vth = thermal equivalent voltage = kT/q
#            where:
#               k = Boltzmann constant (1.381E-23 J/K)
#               T = cell temperature (K)
#               q = charge of an electron (1.602E-19 C)
#          = 25.7 mV at 25 degrees C (298.15 K)
#
# At a given cell temperature, the value (n*Ns*Vth) is constant, which
# we will name "A":
#
#   I = IL - I0 * [e ^ ((V + I*Rs)/A) - 1] - (V + I*Rs)/Rsh
#
# What makes this equation difficult to work with is the fact that the
# current (I) is on both sides of the equation AND it is in the exponent
# of e on the right side. This makes it both "implicit" and
# "transcendental". Algebra cannot be used to solve for I, given the
# other values. Instead, numerical methods (such as the Newton-Raphson
# method) must be used to iteratively search for the solution.
# Fortunately, the SciPy library provides the tool we need - namely a
# "root solver".
#
# The values of the following five parameters need to be determined in
# order to generate an IV curve:
#
#    IL, I0, A, Rs, Rsh
#
# Their values are dependent on the particular PV module/cell
# characteristics and also on the irradiance and cell temperature.
#
# The datasheet provides the following four values at standard test
# conditions (aka STC, which are 1000 W/m^2 irradiance and 25 degrees C
# cell temperature):
#
#      Voc = open-circuit voltage
#      Isc = short-circuit current
#      Vmp = voltage at maximum power point
#      Imp = current at maximum power point
#
# Determining the five parameter values requires simultaneously solving
# five equations. These five equations are based on information we know
# about certain points on the curve, namely:
#
#  Eq 1: I=0 where V=Voc
#  Eq 2: V=0 where I=Isc
#  Eq 3: I=Imp and V=Vmp at the MPP
#  Eq 4: Power is at its peak (i.e. dP/DV=0) at the MPP
#  Eq 5: The reciprocal of the slope at the Isc point is -Rsh
#
# The SciPy root solver is also used for solving these simultaneous
# equations. However, there are cases where this fails to converge. In
# some such cases using using only the first four equations with a fixed
# value for Rsh converges and produces a good result. And in some cases,
# equation #4 must be ignored altogether for the solver to converge.  In
# that case, the result is imperfect because there is a point on the
# modeled curve that has a higher power than the specified MPP. But the
# curve does pass through the specified MPP, and the modeled curve is
# usable for most purposes.
#
# To generate the IV curve at STC, the parameters are derived using the
# STC values from the datasheet. That is nice, but not very useful other
# than to validate the model since the STC IV curve is generally
# included in the datasheet anyway. What we really want is to generate
# the IV curve at non-STC values of irradiance and/or cell temperature.
#
# The effect of irradiance is modeled as a scaling of the light current
# (IL) in proportion to the STC irradiance. It assumes that irradiance
# does not affect I0, A or Rs. This is fairly accurate except at low
# irradiance.
#
# The effect of cell temperature is determined from the following
# datasheet values:
#
#   Isc temperature coefficient  (%/K or mA/K)
#   Voc temperature coefficient  (%/K or mV/K)
#   MPP temperature coefficient  (%/K or W/K)
#
# Note that the MPP temperature coefficient specifies a power delta, and
# does not split out its current and voltage components. We assume that
# the current component is equal to the Isc temperature coefficient, and
# the voltage component is derived based on that and the power
# coefficient.
#
# A two-step process is used to generate the IV curve at a given
# irradiance and cell temperature:
#
#    Step 1 (account for temperature only):
#            - Calculate temperature-adjusted Isc (@ 1000 W/m^2)
#            - Calculate temperature-adjusted Voc (@ 1000 W/m^2)
#            - Calculate temperature-adjusted Vmp (@ 1000 W/m^2)
#            - Calculate temperature-adjusted Imp (@ 1000 W/m^2)
#            - Use root solver to determine IL, I0, A, Rs and Rsh
#
#    Step 2 (adjust for irradiance):
#            - scale IL from step 1 by irradiance/STC_irradiance
#            - Use I0, A, Rs and Rsh from step 1
#            - Generate curve using root solver
#
# This module also supports a reverse computation, where the measured
# Voc and Isc are provided and the temperature and/or irradiance are
# derived.
#
import datetime as dt
import csv
import os
import warnings
import numpy as np
from scipy.optimize import root
from scipy import __version__ as scipy_version

#################
#   Constants   #
#################
# Default property values (can be overridden)
DEFAULT_I0_GUESSES = [1e-8, 1e-9, 1e-10, 3e-8]
DEFAULT_RS_GUESSES = [0.1, 0.2, 0.0, 0.6, 0.7, 0.9, 0.5]
DEFAULT_RSH_GUESSES = [1e15, 100]
DEFAULT_ERR_THRESH = 0.001

# Other constants
STC_IRRAD = 1000.0
NOC_IRRAD = 800.0
STC_T_C = 25.0
BOLTZMANN_K = 1.38066e-23  # Boltzmann constant (Joules/Kelvin)
TEMP_K_0_DEG_C = 273.15  # Kelvins at 0 degrees C
ELECTRON_CHG_Q = 1.60218e-19  # electron charge (coulombs)
IDEALITY_FACTOR_GUESS = 1.0
CELL_VOC_GUESS = 0.67
SPEC_FIELDS = ["PV Name", "Voc", "Isc", "Vmp", "Imp", "Cells",
               "Voc temp coeff", "Voc temp coeff units",
               "Isc temp coeff", "Isc temp coeff units",
               "MPP temp coeff", "MPP temp coeff units",
               "NOCT"]
SCIPY_VERSION = scipy_version  # for flake8


########################
#   Global functions   #
########################
def test_i_given_v_and_parms(amps, volts, il_i0_a_rs_rsh):
    """Function to test a current value (amps) to determine how close it is
       to satisfying the single-diode equation, given the voltage and
       the five parameter values: IL, I0, A, Rs and Rsh. If the provided
       amps value is perfect, the value returned will be zero.  This
       function is used for identifying points on the IV curve (other
       than Isc, MPP and Voc) once the five parameter values are known.
       It is intended to be passed to the SciPy root solver to find the
       current corresponding to a given voltage. The root solver
       repeatedly calls this function using progressively better guesses
       for the current until it has identified a value that produces a
       return value sufficiently close to zero.
    """
    il, i0, a, rs, rsh = il_i0_a_rs_rsh
    exp_term = (volts + amps*rs)/a if (volts + amps*rs)/a < 100 else 100
    return il - i0 * np.expm1(exp_term) - (volts + amps*rs)/rsh - amps


def test_voc(voc, il_i0_a_rsh):
    """Function to test a Voc value to determine how close it is to
       satisfying the single-diode equation, given the four parameter
       values: IL, I0, A and Rs. If the provided Voc value is perfect
       (given the parameter values), or if the parameter values are
       perfect (given the Voc value), the value returned will be zero.
       In this case, the single-diode equation is simplified by the fact
       that the current is zero at the Voc point. The Rs parameter is
       not relevant since it is multiplied by current in the full
       single-diode equation. This function is used as one of the five
       simultaneous equations (#1) used by the test_parms function to
       determine the parameter values. It is also used for identifying
       the Voc once the parameter values are known.  It is intended to
       be passed to the SciPy root solver. The root solver repeatedly
       calls this function using progressively better guesses for the
       inputs until it has identified values that produce a return value
       sufficiently close to zero.
    """
    il, i0, a, rsh = il_i0_a_rsh
    voc_exp_term = voc/a if voc/a < 100 else 100  # prevent overflow
    return il - i0 * np.expm1(voc_exp_term) - voc/rsh


def test_isc(isc, il_i0_a_rs_rsh):
    """Function to test an Isc value to determine how close it is to
       satisfying the single-diode equation, given the five parameter
       values: IL, I0, A, Rs and Rsh. If the provided Isc value is
       perfect (given the parameter values), or if the parameter values
       are perfect (given the Isc value), the value returned will be
       zero.  In this case, the single-diode equation is simplified by
       the fact that the voltage is zero at the Isc point. This function
       is used as one of the five simultaneous equations (#2) used by
       the test_parms function to determine the parameter values. It may
       also be used for identifying the Isc once the parameter values are
       known.  It is intended to be passed to the SciPy root solver. The
       root solver repeatedly calls this function using progressively
       better guesses for the inputs until it has identified values that
       produce a return value sufficiently close to zero.
    """
    il, i0, a, rs, rsh = il_i0_a_rs_rsh
    isc_exp_term = isc*rs/a if isc*rs/a < 100 else 100  # prevent overflow
    return il - i0 * np.expm1(isc_exp_term) - isc*rs/rsh - isc


def test_eq3(vmp_imp, il_i0_a_rs_rsh):
    """Function to test Vmp and Imp values to determine how close they are
       to satisfying the single-diode equation, given the five parameter
       values: IL, I0, A, Rs and Rsh. If the provided Vmp and Imp values
       are perfect (given the parameter values), or if the parameter
       values are perfect (given the Vmp and Imp values), the value
       returned will be zero. This function is used for Equation #3 in
       the test_parms function. Note, that a return value of zero proves
       only that the Vmp, Imp point is on the curve, not that it is the
       point on the curve with the maximum power - that is what Equation
       #4 is for.
    """
    vmp, imp = vmp_imp
    eq3_result = test_i_given_v_and_parms(imp, vmp, il_i0_a_rs_rsh)
    return eq3_result


def test_eq4(vmp_imp, i0_a_rs_rsh):
    """Function to test Vmp and Imp values to determine if they represent
       the point with the maximum power, given the four parameter
       values: I0, A, Rs and Rsh. If the provided Vmp and Imp values are
       perfect (given the parameter values), or if the parameter values
       are perfect (given the Vmp and Imp values), the values returned
       will be zero. This function is used for Equation #4 in the
       test_parms function.
    """
    vmp, imp = vmp_imp
    i0, a, rs, rsh = i0_a_rs_rsh
    mpp_exp_term = (vmp + imp*rs)/a if (vmp + imp*rs)/a < 100 else 100
    eq4_result = (imp - vmp * (i0 * rsh * np.exp(mpp_exp_term) + a) /
                  (rsh * (i0 * rs * np.exp(mpp_exp_term) + a) + (rs * a)))
    return eq4_result


def test_mpp(vmp_imp, il_i0_a_rs_rsh):
    """Function to test Vmp and Imp with both Equation #3 and Equation
       #4. If both return values are zero, the Vmp and Imp values
       represent the maximum power point of the curve defined by the
       five parameters.
    """
    eq3_result = test_eq3(vmp_imp, il_i0_a_rs_rsh)
    eq4_result = test_eq4(vmp_imp, il_i0_a_rs_rsh[1:])
    return [eq3_result, eq4_result]


def test_eq5(rsh, i0_a_rs_isc):
    """Function to test Rsh with the I0, A and Rs parameters as well as the
       Isc value to determine if they satisfy the fifth equation, which
       is based on the fact that the slope of the curve at the Isc point
       should be the negative reciprocal of Rsh.
    """
    i0, a, rs, isc = i0_a_rs_isc
    mpp_exp_term = (isc*rs)/a if (isc*rs)/a < 100 else 100
    eq5_result = (1/rsh - (i0 * rsh * np.exp(mpp_exp_term) + a) /
                  (rsh * (i0 * rs * np.exp(mpp_exp_term) + a) + (rs*a)))
    return eq5_result


def test_parms(il_i0_a_rs_rsh, voc_isc_vmp_imp_ignore_eq4):
    """Function to test all five parameter values (IL, I0, A, Rs, and Rsh),
       given the following known values from the curve:

          Voc = open-circuit voltage
          Isc = short-circuit current
          Vmp = voltage at maximum power point
          Imp = current at maximum power point

       Five equations are required because there are five unknowns to
       solve for:

          Eq 1: Single-diode equation with I=0 and V=Voc
          Eq 2: Single-diode equation with I=Isc and V=0
          Eq 3: Single-diode equation with I=Imp and V=Vmp
          Eq 4: dP/dV=0 with I=Imp and V=Vmp
          Eq 5: dI/dV = -1/Rsh with I=Isc and V=0

       The first three are very straightforward. The fourth and fifth
       require using implicit differentiation (see
       https://en.wikipedia.org/wiki/Implicit_function) to find the
       derivative of the single-diode equation, with I being the
       differentiation variable and V being the dependent variable. See
       the design document for more details on this math.

       This function is used for determining the five parameter values
       given known voltage and current values at the Voc, Isc, and
       maximum power points. The function is intended to be passed to
       the SciPy root solver, which repeatedly calls it using
       progressively better guesses for the five parameters until it has
       identified values that result in all five return values being
       sufficiently close to zero.

       In some cases, a good solution cannot be found that satisfies all
       five equations. This may be due to flawed datasheet values. The
       last entry in the voc_isc_vmp_imp_ignore_eq4 list is a flag that,
       when True, causes the 4th equation to be ignored. This is done by
       forcing its return value to zero. In this case the resulting
       curve will "hit" all three points (Isc, Voc, MPP). But the "MPP"
       won't necessarily be the point with the maximum power on that
       curve.

       The test_first_four_parms function is called to determine the
       results of the first four equations, and then the test_eq5
       function is called to determine the result of the fifth.
    """
    # The caller passes the test values for IL, I0, A, Rs, and Rsh in a
    # numpy array (a simple list works too though).
    il, i0, a, rs, rsh = il_i0_a_rs_rsh

    # Steer away from negative numbers
    if i0 < 0 or a < 0 or rs < 0 or rsh <= 0:
        return [999, 999, 999, 999, 999]

    # Equation #1 - #4: call test_first_four_parms function
    il_i0_a_rs = [il, i0, a, rs]
    rsh_voc_isc_vmp_imp_ignore_eq4 = [rsh] + voc_isc_vmp_imp_ignore_eq4
    (eq1_result,
     eq2_result,
     eq3_result,
     eq4_result) = test_first_four_parms(il_i0_a_rs,
                                         rsh_voc_isc_vmp_imp_ignore_eq4)

    # Equation #5 is the Isc slope equation. It equals zero if the slope
    # of the curve at the Isc point is equal to -1/Rsh, i.e.:
    #
    #   dI/dV = -1/Rsh  @ I=Isc, V=0
    #
    # dI/dV is the derivative of the single-diode equation, with I being
    # the differentiation variable and V being the dependent variable.
    # The test_eq5 function implements equation #5.
    #
    isc = voc_isc_vmp_imp_ignore_eq4[1]
    eq5_result = test_eq5(rsh, [i0, a, rs, isc])
    return [eq1_result, eq2_result, eq3_result, eq4_result, eq5_result]


def test_first_four_parms(il_i0_a_rs, rsh_voc_isc_vmp_imp_ignore_eq4):
    """Function to test the four parameter values (IL, I0, A, and Rs), given
       the Rsh value and the Voc, Isc, Vmp and Imp values from the
       curve.

       Only the first four equations are considered for this function.
       In some cases, the root solver is able to find a solution given a
       fixed value for Rsh (and relieved of having to satisfy equation
       #5) when it otherwise fails if it is asked to solve all five
       equations for all five parameters. Having a separate function for
       the first four equations/parameters makes it possible to invoke
       the root solver in this way as a fallback.

       See the test_parms docstring for more details.
    """
    # pylint: disable=too-many-locals

    # The caller passes the test values for IL, I0, A, and Rs in a
    # numpy array (a simple list works too though).
    il, i0, a, rs = il_i0_a_rs

    # Steer away from negative numbers
    if i0 < 0 or a < 0 or rs < 0:
        return [999, 999, 999, 999]

    # The the Rsh, Voc, Isc, Vmp and Imp values and the flag to ignore
    # equation 4 are passed in the args list.
    rsh, voc, isc, vmp, imp, ignore_eq4 = rsh_voc_isc_vmp_imp_ignore_eq4

    # Create some combo lists
    il_i0_a_rsh = [il, i0, a, rsh]
    il_i0_a_rs_rsh = [il, i0, a, rs, rsh]
    i0_a_rs_rsh = [i0, a, rs, rsh]
    vmp_imp = [vmp, imp]

    # Equation #1: Voc equation
    #
    # This equals zero if the curve hits the Voc point. It is just
    # the single-diode equation with V=Voc and I=0.
    #
    # The test_voc function implements equation #1.
    #
    eq1_result = test_voc(voc, il_i0_a_rsh)

    # Equation #2: Isc equation
    #
    # This equals zero if the curve hits the Isc point. It is just
    # the single-diode equation with I=Isc and V=0.
    #
    # The test_isc function implements equation #2.
    #
    eq2_result = test_isc(isc, il_i0_a_rs_rsh)

    # Equations #3 and #4: MPP equations
    #
    # Equation #3 equals zero if the curve hits the MPP. It is just the
    # single-diode equation with V=Vmp and I=Imp. It does not, by
    # itself guarantee that this point is in fact the point with the
    # maximum power.
    #
    # The test_eq3 function implements equation #3.
    #
    eq3_result = test_eq3(vmp_imp, il_i0_a_rs_rsh)

    # Equation #4 is the MPP power equation (dP/dV = 0). It equals zero
    # if the point at V=Vmp and I=Imp is the point with the highest
    # power. At the MPP, dP/dV = Imp + Vmp * dI/dV. dI/dV is the
    # derivative of the single-diode equation, with I being the
    # differentiation variable and V being the dependent variable.
    #
    # The test_eq4 function implements equation #4.
    #
    eq4_result = test_eq4(vmp_imp, i0_a_rs_rsh) if not ignore_eq4 else 0.0

    return [eq1_result, eq2_result, eq3_result, eq4_result]


def find_parms(voc_isc_vmp_imp, il_guess, i0_guesses, a_guess, rs_guesses,
               rsh_guesses, err_thresh):
    """Function to use the SciPy root solver to find the values of the IL,
       I0, A, Rs and Rsh parameters.

       The root solver's success depends heavily on being provided with
       "good" guesses for the values it is solving for. Suprisingly,
       guesses that are closest to the final solution value are not
       always the best.

       This function takes the following as inputs:

         - Voc, Isc, Vmp, Imp
         - A single guess for IL (usually equal to Isc)
         - A list of guesses for I0
         - A single guess for A
         - A list of guesses for Rs
         - A list of guesses for Rsh

       It then loops, calling the root solver with the different
       combinations of guesses. Since this can be time-consuming, it
       declares success and terminates if a solution is found that is
       "good enough". It is "good enough" if none of the equations has
       an absolute value greater than err_thresh. Performance is
       optimized if the guesses are ordered from most to least likely to
       succeed.

       The outermost loop first tries all the inner loops with
       ignore_eq4 set to False. The second-to-outermost loop first tries
       all the inner loops with use_eq5 set to True. Ideally, a solution
       is found before either of these loops repeats, meaning all five
       equations are satisfied within a margin of err_thresh. If not,
       then the the second-to-outermost loop sets use_eq5 to False,
       which causes the innermost loop to run the root solver only for
       the first four equations (and with the exact values for Rsh from
       the guesses list. If that too fails, then the outermost loop sets
       ignore_eq4 to True, which causes the root solver to be "fooled"
       into thinking that equation #4 is always satified. This results
       in an imperfect modeling, but usually better than nothing.
    """
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-nested-blocks
    voc, isc, vmp, imp = voc_isc_vmp_imp
    best_max_abs_err = 999999999
    for ignore_eq4 in [False, True]:
        for use_eq5 in [True, False]:
            for rsh_guess in rsh_guesses:
                for i0_guess in i0_guesses:
                    for rs_guess in rs_guesses:
                        with warnings.catch_warnings():
                            # Suppress printing annoying messages for cases
                            # that aren't working out
                            filter_str = "The iteration is not making "
                            filter_str += "good progress"
                            warnings.filterwarnings("ignore", filter_str,
                                                    RuntimeWarning)
                            filter_str = "The number of calls to function has "
                            filter_str += "reached maxfev"
                            warnings.filterwarnings("ignore", filter_str,
                                                    RuntimeWarning)
                            if use_eq5:
                                # Run SciPy root solver, using
                                # test_parms function with guesses for
                                # all five parameters and specified
                                # values for Voc, isc, vmp and imp
                                guesses = [il_guess, i0_guess, a_guess,
                                           rs_guess, rsh_guess]
                                sol = root(test_parms, guesses,
                                           args=[voc, isc, vmp, imp,
                                                 ignore_eq4])
                            else:
                                # Run SciPy root solver, using
                                # test_first_four_parms function with
                                # guesses for first four parameters and
                                # specified values for rsh, Voc, isc,
                                # vmp and imp
                                guesses = [il_guess, i0_guess, a_guess,
                                           rs_guess]
                                sol = root(test_first_four_parms, guesses,
                                           args=[rsh_guess, voc, isc, vmp, imp,
                                                 ignore_eq4])
                        solutions = sol.x
                        results = sol.fun

                        # Find worst error in results
                        worst_abs_err = 0
                        for res in results:
                            worst_abs_err = (abs(res)
                                             if abs(res) > worst_abs_err
                                             else worst_abs_err)

                        # If that's the best so far, update best_parms
                        # and best_results
                        if worst_abs_err < best_max_abs_err:
                            best_parms = (solutions if use_eq5
                                          else np.append(solutions, rsh_guess))
                            best_max_abs_err = worst_abs_err
                            best_results = results

                        # If it's less than err_thresh, we are
                        # done. Return the parameters and results
                        if worst_abs_err < err_thresh:
                            return [best_parms, best_results]

    # If no results met the err_thresh criterion, return the best
    # results seen
    return [best_parms, best_results]


def pv_spec_from_dict(pv_spec_dict):
    """Global function to extract the values from a pv_spec_dict and return
       them in the canonical order. All values are strings, so need to
       convert to ints/floats (and those that fail remain strings)
    """
    pv_spec = []
    for field in SPEC_FIELDS:
        try:
            value = int(pv_spec_dict[field])
        except ValueError:
            try:
                value = float(pv_spec_dict[field])
            except ValueError:
                value = pv_spec_dict[field]
        pv_spec.append(value)
    return pv_spec


def read_pv_specs(pv_spec_csv_file):
    """Global generator function to read a PV spec CSV file and yield each
       spec as a dict.
    """
    with open(pv_spec_csv_file) as csvfile:
        reader = csv.DictReader(csvfile)
        assert_str = "ERROR: first row of {} does not contain "
        assert_str += "the expected values: {}"
        assert sorted(reader.fieldnames) == sorted(SPEC_FIELDS), \
            assert_str.format(pv_spec_csv_file, SPEC_FIELDS)
        for pv_spec_dict in reader:
            pv_spec = pv_spec_from_dict(pv_spec_dict)
            check_pv_spec(pv_spec)
            yield pv_spec_dict


def add_pv_spec(pv_spec_csv_file, pv_spec):
    """Global function to add the spec values for a PV module or cell to the
       PV spec CSV file. If the file does not exist, it is created. If
       it does exist, the current entries are read and the file is
       overwritten with the same values, with the new entry added in the
       correct place (list sorted alphabetically by PV name). If the
       file already had an entry with the same PV name as the one being
       added, the old one is discarded and replaced by the new one.
    """
    check_pv_spec(pv_spec)
    # Create a dict from the spec values and the field names
    pv_spec_dict = dict(zip(SPEC_FIELDS, pv_spec))
    # Start the (unordered) list of specs with the new one
    pv_specs = [pv_spec_dict]
    if os.path.exists(pv_spec_csv_file):
        for old_pv_spec_dict in read_pv_specs(pv_spec_csv_file):
            # Add to list unless its name is the same as the one being
            # added
            if old_pv_spec_dict["PV Name"] != pv_spec_dict["PV Name"]:
                pv_specs.append(old_pv_spec_dict)

    with open(pv_spec_csv_file, "w+") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=SPEC_FIELDS)
        writer.writeheader()
        for new_pv_spec_dict in sorted(pv_specs, key=lambda k: k["PV Name"]):
            writer.writerow(new_pv_spec_dict)


def check_pv_spec(pv_spec):
    """Global function to check the fields in a PV spec list to make
       sure they are legal.
    """
    assert_lead = "ERROR: "
    # Voc, Isc, Vmp, Imp, and Isc temp coeff must all be positive
    # floating point or integer values
    for field in [SPEC_FIELDS.index("Voc"),
                  SPEC_FIELDS.index("Isc"),
                  SPEC_FIELDS.index("Vmp"),
                  SPEC_FIELDS.index("Imp"),
                  SPEC_FIELDS.index("Isc temp coeff")]:
        assert isinstance(pv_spec[field], (int, float)), \
            ("{} Invalid {} value ({}). Must be floating point or integer."
             .format(assert_lead, SPEC_FIELDS[field], pv_spec[field]))
        assert pv_spec[field] > 0, \
            ("{} Invalid {} value ({}). Must be positive."
             .format(assert_lead, SPEC_FIELDS[field], pv_spec[field]))

    # Cells and NOCT must be positive floating point or integer values
    # OR and empty string
    for field in [SPEC_FIELDS.index("Cells"),
                  SPEC_FIELDS.index("NOCT")]:
        if pv_spec[field] != "":
            assert_str = "{} Invalid {} value ({})."
            assert_str += " Must be floating point, integer or"
            assert_str += " empty string (if unknown)."
            assert isinstance(pv_spec[field], (int, float)), \
                (assert_str.format(assert_lead, SPEC_FIELDS[field],
                                   pv_spec[field]))
            assert pv_spec[field] > 0, \
                ("{} Invalid {} value ({}). Must be positive."
                 .format(assert_lead, SPEC_FIELDS[field], pv_spec[field]))

    # Voc and MPP temp coeff must be negative floating point or integer
    # values
    for field in [SPEC_FIELDS.index("Voc temp coeff"),
                  SPEC_FIELDS.index("MPP temp coeff")]:
        assert isinstance(pv_spec[field], (int, float)), \
            ("{} Invalid {} value ({}). Must be floating point or integer."
             .format(assert_lead, SPEC_FIELDS[field], pv_spec[field]))
        assert pv_spec[field] < 0, \
            ("{} Invalid {} value ({}). Must be negative."
             .format(assert_lead, SPEC_FIELDS[field], pv_spec[field]))

    # Voc temp coeff units must be "%" or "mV"
    field = SPEC_FIELDS.index("Voc temp coeff units")
    assert pv_spec[field] in ["%", "mV"], \
        ("{} Invalid {} value ({}). Must be % or mV."
         .format(assert_lead, SPEC_FIELDS[field], pv_spec[field]))

    # Isc temp coeff units must be "%" or "mA"
    field = SPEC_FIELDS.index("Isc temp coeff units")
    assert pv_spec[field] in ["%", "mA"], \
        ("{} Invalid {} value ({}). Must be % or mA."
         .format(assert_lead, SPEC_FIELDS[field], pv_spec[field]))

    # MPP temp coeff units must be "%"
    field = SPEC_FIELDS.index("MPP temp coeff units")
    assert pv_spec[field] in ["%"], \
        ("{} Invalid {} value ({}). Must be %."
         .format(assert_lead, SPEC_FIELDS[field], pv_spec[field]))


def create_pv_spec_file(pv_spec_csv_file):
    """Global function to create a starting PV spec CSV file populated with
       some example PV module specifications.
    """
    pv_specs = []
    pv_specs.append(["SunPower X21-345", 68.2, 6.39, 57.3, 6.02,
                     96, -167.4, "mV", 2.9, "mA", -0.29, "%", 41.5])
    pv_specs.append(["REC TwinPeak REC280TP", 39.2, 9.44, 31.9, 8.78,
                     60, -0.31, "%", 0.045, "%", -0.39, "%", 44.6])
    pv_specs.append(["Grape Solar GS-STAR-100W", 21.9, 6.13, 18.0, 5.56,
                     36, -0.32, "%", 0.04, "%", -0.45, "%", 45.0])
    pv_specs.append(["Jingko JKM370M-66HB", 43.7, 10.73, 36.93, 10.02,
                     66, -0.28, "%", 0.048, "%", -0.35, "%", 45.0])
    pv_specs.append(["Canadian Solar CS3W-415P", 47.8, 11.14, 39.3, 10.56,
                     72, -0.29, "%", 0.05, "%", -0.37, "%", 42.0])
    pv_specs.append(["Silfab SIL-380 NT", 48.0, 10.3, 39.3, 9.7,
                     72, -0.3, "%", 0.03, "%", -0.38, "%", 45.0])
    pv_specs.append(["Renogy RNG-160D-SS", 22.9, 8.37, 20.2, 7.92,
                     32, -0.31, "%", 0.05, "%", -0.42, "%", 47.0])
    pv_specs.append(["Q.PEAK DUO-G5 330", 40.66, 10.20, 33.98, 9.71,
                     60, -0.28, "%", 0.04, "%", -0.37, "%", 45.0])
    pv_specs.append(["SunPower SPR-A450-COM", 51.9, 11.0, 44.0, 10.2,
                     72, -136.0, "mV", 5.7, "mA", -0.29, "%", ""])
    pv_specs.append(["HQST HQST-150P", 22.7, 8.09, 19.1, 7.89,
                     32, -0.30, "%", 0.06, "%", -0.40, "%", 47.0])
    pv_specs.append(["JA Solar JAM60D09-325/BP", 41.05, 10.16, 33.75, 9.63,
                     60, -0.3, "%", 0.06, "%", -0.37, "%", 45.0])
    pv_specs.append(["Trina Solar TSM-DD05H.05(II) 320",
                     40.6, 10.0, 33.3, 9.6,
                     60, -0.29, "%", 0.05, "%", -0.37, "%", 44.0])
    pv_specs.append(["Longi LR6-72HPH-385M", 49.2, 10.03, 40.8, 9.43,
                     72, -0.286, "%", 0.057, "%", -0.37, "%", 45.0])
    pv_specs.append(["Risen Energy RSM72-6-385BMDG",
                     45.40, 8.24, 37.10, 7.75,
                     72, -0.29, "%", 0.05, "%", -0.39, "%", 45.0])
    pv_specs.append(["Risen Energy Poly 156mm cell 4.29W",
                     0.632, 8.668, 0.526, 8.156,
                     1, -0.32, "%", 0.06, "%", -0.44, "%", ""])
    pv_specs.append(["GCL-SI GCL-M3/72H-405", 49.23, 10.39, 40.96, 9.89,
                     72, -0.3, "%", 0.06, "%", -0.39, "%", 44.0])
    pv_specs.append(["Talesun Hipro M350", 47.4, 9.5, 39.3, 8.92,
                     72, -0.3, "%", 0.05, "%", -0.39, "%", 45.0])
    pv_specs.append(["LG LG350Q1C-A5", 42.7, 10.77, 36.1, 9.70,
                     60, -0.24, "%", 0.04, "%", -0.30, "%", 44.0])
    pv_specs.append(["Panasonic VBH340RA18N", 71.2, 6.02, 60.3, 5.64,
                     96, -170.0, "mV", 3.31, "mA", -0.258, "%", 44.0])
    pv_specs.append(["Hyundai HiS-S375RI", 48.0, 10.0, 39.7, 9.4,
                     72, -0.29, "%", 0.039, "%", -0.40, "%", 46.0])
    pv_specs.append(["ZZZ CANNOT BE MODELED", 30.6, 10.0, 33.3, 9.6,
                     60, -0.29, "%", 0.05, "%", -0.37, "%", 44.0])
    for pv_spec in pv_specs:
        add_pv_spec(pv_spec_csv_file, pv_spec)


#################
#   Classes     #
#################

class PV_model(object):
    """Class that models a PV cell or module, given its datasheet
       specifications. Methods are provided to generate the PV's
       single-diode model parameters at a given cell temperature and
       irradiance and to generate the IV curve at those conditions.
    """
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods

    def __init__(self):
        self.debug = False
        self.vi_points = []
        self.run_ms = 0
        # Property variables
        self._pv_name = None
        self._voc_stc = None
        self._isc_stc = None
        self._vmp_stc = None
        self._imp_stc = None
        self._num_cells = None
        self._voc_temp_coeff_pct_per_deg = None
        self._isc_temp_coeff_pct_per_deg = None
        self._mpp_temp_coeff_pct_per_deg = None
        self._noct = None
        self._i0_guesses = DEFAULT_I0_GUESSES
        self._rs_guesses = DEFAULT_RS_GUESSES
        self._rsh_guesses = DEFAULT_RSH_GUESSES
        self._err_thresh = DEFAULT_ERR_THRESH
        self._irradiance = STC_IRRAD
        self._cell_temp_c = STC_T_C
        self._il = None
        self._i0 = None
        self._a = None
        self._rs = None
        self._rsh = None
        self._vmp = None
        self._imp = None
        self._eq1_result = None
        self._eq2_result = None
        self._eq3_result = None
        self._eq4_result = None
        self._eq5_result = None

    # Properties
    # ---------------------------------
    @property
    def pv_name(self):
        """Name of PV module or cell
        """
        return self._pv_name

    @pv_name.setter
    def pv_name(self, value):
        self._pv_name = value

    # ---------------------------------
    @property
    def voc_stc(self):
        """Open-circuit voltage at standard test conditions (from datasheet)
        """
        return self._voc_stc

    @voc_stc.setter
    def voc_stc(self, value):
        self._voc_stc = value

    # ---------------------------------
    @property
    def isc_stc(self):
        """Short-circuit current at standard test conditions (from datasheet)
        """
        return self._isc_stc

    @isc_stc.setter
    def isc_stc(self, value):
        self._isc_stc = value

    # ---------------------------------
    @property
    def vmp_stc(self):
        """Maximum power point voltage at standard test conditions (from
           datasheet)
        """
        return self._vmp_stc

    @vmp_stc.setter
    def vmp_stc(self, value):
        self._vmp_stc = value

    # ---------------------------------
    @property
    def imp_stc(self):
        """Maximum power point current at standard test conditions (from
           datasheet)
        """
        return self._imp_stc

    @imp_stc.setter
    def imp_stc(self, value):
        self._imp_stc = value

    # ---------------------------------
    @property
    def num_cells(self):
        """Number of PV cells
        """
        return self._num_cells

    @num_cells.setter
    def num_cells(self, value):
        self._num_cells = value

    # ---------------------------------
    @property
    def voc_temp_coeff_pct_per_deg(self):
        """Voc temperature coefficient (%/K)
        """
        return self._voc_temp_coeff_pct_per_deg

    @voc_temp_coeff_pct_per_deg.setter
    def voc_temp_coeff_pct_per_deg(self, value):
        self._voc_temp_coeff_pct_per_deg = value

    # ---------------------------------
    @property
    def isc_temp_coeff_pct_per_deg(self):
        """Isc temperature coefficient (%/K)
        """
        return self._isc_temp_coeff_pct_per_deg

    @isc_temp_coeff_pct_per_deg.setter
    def isc_temp_coeff_pct_per_deg(self, value):
        self._isc_temp_coeff_pct_per_deg = value

    # ---------------------------------
    @property
    def mpp_temp_coeff_pct_per_deg(self):
        """MPP temperature coefficient (%/K)
        """
        return self._mpp_temp_coeff_pct_per_deg

    @mpp_temp_coeff_pct_per_deg.setter
    def mpp_temp_coeff_pct_per_deg(self, value):
        self._mpp_temp_coeff_pct_per_deg = value

    # ---------------------------------
    @property
    def noct(self):
        """Nominal operating cell temperature (degrees C)
        """
        return self._noct

    @noct.setter
    def noct(self, value):
        self._noct = value

    # ---------------------------------
    @property
    def i0_guesses(self):
        """List of guesses for the I0 parameter to try with the SciPy root
           solver
        """
        return self._i0_guesses

    @i0_guesses.setter
    def i0_guesses(self, value):
        self._i0_guesses = value

    # ---------------------------------
    @property
    def rs_guesses(self):
        """List of guesses for the Rs parameter to try with the SciPy root
           solver
        """
        return self._rs_guesses

    @rs_guesses.setter
    def rs_guesses(self, value):
        self._rs_guesses = value

    # ---------------------------------
    @property
    def rsh_guesses(self):
        """List of guesses for the Rsh parameter to try with the SciPy root
           solver
        """
        return self._rsh_guesses

    @rsh_guesses.setter
    def rsh_guesses(self, value):
        self._rsh_guesses = value

    # ---------------------------------
    @property
    def err_thresh(self):
        """Error threshold for the SciPy root solver results. A perfect solution
           returns 0. This threshold is the maximum absolute value that
           will be considered "good enough" for each of the results of
           the four equations in order to consider the solution a match.
        """
        return self._err_thresh

    @err_thresh.setter
    def err_thresh(self, value):
        self._err_thresh = value

    # ---------------------------------
    @property
    def irradiance(self):
        """Irradiance value in W/m^2 to model. Default is STC value of 1000.0
        """
        return self._irradiance

    @irradiance.setter
    def irradiance(self, value):
        self._irradiance = value

    # ---------------------------------
    @property
    def cell_temp_c(self):
        """Cell temperature (in degrees C) to model. Default is STC value of
           25.0
        """
        return self._cell_temp_c

    @cell_temp_c.setter
    def cell_temp_c(self, value):
        self._cell_temp_c = value

    # ---------------------------------
    @property
    def il(self):
        """Value of single-diode model IL parameter
        """
        return self._il

    @il.setter
    def il(self, value):
        self._il = value

    # ---------------------------------
    @property
    def i0(self):
        """Value of single-diode model I0 parameter
        """
        return self._i0

    @i0.setter
    def i0(self, value):
        self._i0 = value

    # ---------------------------------
    @property
    def a(self):
        """Value of single-diode model A parameter
        """
        return self._a

    @a.setter
    def a(self, value):
        self._a = value

    # ---------------------------------
    @property
    def rs(self):
        """Value of single-diode model Rs parameter
        """
        return self._rs

    @rs.setter
    def rs(self, value):
        self._rs = value

    # ---------------------------------
    @property
    def rsh(self):
        """Value of single-diode model Rsh parameter
        """
        return self._rsh

    @rsh.setter
    def rsh(self, value):
        self._rsh = value

    # ---------------------------------
    @property
    def vmp(self):
        """Value of the MPP voltage
        """
        return self._vmp

    @vmp.setter
    def vmp(self, value):
        self._vmp = value

    # ---------------------------------
    @property
    def imp(self):
        """Value of the MPP current
        """
        return self._imp

    @imp.setter
    def imp(self, value):
        self._imp = value

    # ---------------------------------
    @property
    def eq1_result(self):
        """Result of equation #1 (Step #1)"""
        return self._eq1_result

    @eq1_result.setter
    def eq1_result(self, value):
        self._eq1_result = value

    # ---------------------------------
    @property
    def eq2_result(self):
        """Result of equation #2 (Step #1)"""
        return self._eq2_result

    @eq2_result.setter
    def eq2_result(self, value):
        self._eq2_result = value

    # ---------------------------------
    @property
    def eq3_result(self):
        """Result of equation #3 (Step #1)"""
        return self._eq3_result

    @eq3_result.setter
    def eq3_result(self, value):
        self._eq3_result = value

    # ---------------------------------
    @property
    def eq4_result(self):
        """Result of equation #4 (Step #1)"""
        return self._eq4_result

    @eq4_result.setter
    def eq4_result(self, value):
        self._eq4_result = value

    # ---------------------------------
    @property
    def eq5_result(self):
        """Result of equation #5 (Step #1)"""
        return self._eq5_result

    @eq5_result.setter
    def eq5_result(self, value):
        self._eq5_result = value

    # Derived properties
    # ---------------------------------
    def voc_temp_coeff_mv_per_deg(self, value):
        """Voc temperature coefficient (mV/K) - Setter only
           Translated to %/K and sets that property.
        """
        # pylint: disable=method-hidden
        self._voc_temp_coeff_pct_per_deg = (value/10.0)/self.voc_stc
    voc_temp_coeff_mv_per_deg = property(None, voc_temp_coeff_mv_per_deg)

    # ---------------------------------
    def isc_temp_coeff_ma_per_deg(self, value):
        """Isc temperature coefficient (mA/K) - Setter only
           Translated to %/K and sets that property.
        """
        # pylint: disable=method-hidden
        self._isc_temp_coeff_pct_per_deg = (value/10.0)/self.isc_stc
    isc_temp_coeff_ma_per_deg = property(None, isc_temp_coeff_ma_per_deg)

    # ---------------------------------
    @property
    def a_guess(self):
        """Guess for A parameter for root solver"""
        num_cells = (self.num_cells if self.num_cells is not None else
                     round(self.voc_stc / CELL_VOC_GUESS))
        kt_over_q = BOLTZMANN_K * self.cell_temp_k / ELECTRON_CHG_Q
        return IDEALITY_FACTOR_GUESS * num_cells * kt_over_q

    # ---------------------------------
    @property
    def cell_temp_k(self):
        """Cell temperature (in K)
        """
        return self.cell_temp_c + TEMP_K_0_DEG_C

    # ---------------------------------
    @property
    def temp_diff_from_stc(self):
        """Difference between cell_temp_c and the standard test conditions
           temperature
        """
        return self.cell_temp_c - STC_T_C

    # ---------------------------------
    @property
    def isc_at_temp(self):
        """Calculated Isc value at cell_temp_c at STC irradiance"""
        isc_at_temp = (self.isc_stc * (1.0 + self.temp_diff_from_stc *
                                       self.isc_temp_coeff_pct_per_deg/100.0))
        return isc_at_temp

    # ---------------------------------
    @property
    def voc_at_temp(self):
        """Calculated Voc value at cell_temp_c at STC irradiance"""
        voc_at_temp = (self.voc_stc * (1.0 + self.temp_diff_from_stc *
                                       self.voc_temp_coeff_pct_per_deg/100.0))
        return voc_at_temp

    # ---------------------------------
    @property
    def imp_at_temp(self):
        """Calculated Imp value at cell_temp_c at STC irradiance. We assume
           that the Imp scales with the Isc temperature coefficient.
           This may not be exactly true, but it's close.
        """
        imp_at_temp = (self.imp_stc * (1.0 + self.temp_diff_from_stc *
                                       self.isc_temp_coeff_pct_per_deg/100.0))
        return imp_at_temp

    # ---------------------------------
    @property
    def vmp_at_temp(self):
        """Calculated Vmp value at cell_temp_c at STC irradiance. This is a
           two-step process. First we calculate the MPP power using the
           power temperature coefficient. Then we use the estimated Imp
           value to calculate the Vmp value that results in the
           calculated power.
        """
        pwr_at_temp = (self.imp_stc * self.vmp_stc *
                       (1.0 + self.temp_diff_from_stc *
                        self.mpp_temp_coeff_pct_per_deg/100.0))
        vmp_at_temp = pwr_at_temp / self.imp_at_temp
        return vmp_at_temp

    # ---------------------------------
    @property
    def voc(self):
        """Voc of IV curve for the PV module/cell at the specified temperature
           and irradiance.
        """
        if (self.il is None or self.i0 is None or
                self.a is None or self.rsh is None):
            return None
        voc_guess = self.voc_at_temp
        voc = root(test_voc, x0=[voc_guess], args=([self.il, self.i0, self.a,
                                                    self.rsh]))
        return voc.x[0]

    # ---------------------------------
    @property
    def isc(self):
        """Isc of IV curve for the PV module/cell at the specified temperature
           and irradiance.
        """
        if (self.il is None or self.i0 is None or
                self.a is None or self.rs is None or self.rsh is None):
            return None
        isc_guess = self.isc_at_temp
        isc = root(test_isc, x0=[isc_guess], args=([self.il, self.i0, self.a,
                                                    self.rs, self.rsh]))
        return isc.x[0]

    # ---------------------------------
    @property
    def ideality_factor(self):
        """Value of the ideality factor "n". This can only be calculated if the
           number of cells is specified.
        """
        return self.a / (self.num_cells * BOLTZMANN_K * self.cell_temp_k /
                         ELECTRON_CHG_Q)

    # ---------------------------------
    @property
    def parms_string(self):
        """String with the single-diode equations parameter values
        """
        return "IL: {}  I0: {}  A: {}  Rs: {}  Rsh: {}".format(self.il,
                                                               self.i0,
                                                               self.a,
                                                               self.rs,
                                                               self.rsh)

    # ---------------------------------
    @property
    def parms_string_w_newlines(self):
        """String with the single-diode equations parameter values
        """
        return "IL: {}\nI0: {}\nA: {}\nRs: {}\nRsh: {}".format(self.il,
                                                               self.i0,
                                                               self.a,
                                                               self.rs,
                                                               self.rsh)

    # ---------------------------------
    @property
    def title_string(self):
        """String with the PV name, irradiance and cell temperature.
        """
        sqd = u'\xb2'
        dgs = u'\N{DEGREE SIGN}'
        pv_name_unicode = self.pv_name.decode("utf-8")
        return (u"{} modeled @ {} W/m{}, {} {}C cell temp"
                .format(pv_name_unicode, self.irradiance, sqd,
                        self.cell_temp_c, dgs))

    # ---------------------------------
    @property
    def summary_string(self):
        """String with the PV name, irradiance, cell temperature and modeled
           Voc, Isc, Vmp, Imp and max power.
        """
        max_power = self.vmp * self.imp if self.vmp is not None else None
        str1 = "Voc: {} V  Isc: {} A   ".format(self.voc, self.isc)
        str2 = "MPP: {} V  {} A  {} W".format(self.vmp, self.imp, max_power)
        return u"{}\n{}\n{}".format(self.title_string, str1, str2)

    # Methods
    # -------------------------------------------------------------------------
    def get_spec_vals(self, pv_name, pv_spec_csv_file):
        """Method to get the spec values for a given PV from a CSV file and
           update the associated object properties.
        """
        for pv_spec_dict in read_pv_specs(pv_spec_csv_file):
            if pv_spec_dict["PV Name"] == pv_name:
                self.apply_pv_spec_dict(pv_spec_dict)
                return

        assert False, "{} does not have specs for {}".format(pv_spec_csv_file,
                                                             pv_name)

    # -------------------------------------------------------------------------
    def apply_pv_spec_dict(self, pv_spec_dict):
        """Method to update the associated object properties from the given
           pv_spec_dict
        """
        self.pv_name = pv_spec_dict["PV Name"]
        self.voc_stc = float(pv_spec_dict["Voc"])
        self.isc_stc = float(pv_spec_dict["Isc"])
        self.vmp_stc = float(pv_spec_dict["Vmp"])
        self.imp_stc = float(pv_spec_dict["Imp"])
        self.num_cells = (None if not pv_spec_dict["Cells"] else
                          float(pv_spec_dict["Cells"]))
        if pv_spec_dict["Voc temp coeff units"] == "%":
            val = float(pv_spec_dict["Voc temp coeff"])
            self.voc_temp_coeff_pct_per_deg = val
        else:
            val = float(pv_spec_dict["Voc temp coeff"])
            self.voc_temp_coeff_mv_per_deg = val
        if pv_spec_dict["Isc temp coeff units"] == "%":
            val = float(pv_spec_dict["Isc temp coeff"])
            self.isc_temp_coeff_pct_per_deg = val
        else:
            val = float(pv_spec_dict["Isc temp coeff"])
            self.isc_temp_coeff_ma_per_deg = val
        val = float(pv_spec_dict["MPP temp coeff"])
        self.mpp_temp_coeff_pct_per_deg = val
        self.noct = (None if not pv_spec_dict["NOCT"] else
                     float(pv_spec_dict["NOCT"]))

    # -------------------------------------------------------------------------
    def run(self):
        """Method to run the model once it is has been populated with
           the input values. Once this method has been run, the
           properties with the single-diode model parameters will
           contain their derived values and the properties for the Voc,
           Isc and MPP will also return the correct values.

           If the modeling fails to find a solution, an AssertionError
           exception is raised.

           If the "solution" required ignoring Equation #4 (see the
           find_parms() method), no exception is raised, but a True
           value is returned by the method.
        """
        # pylint: disable=too-many-locals
        start_time = dt.datetime.now()

        # Reset the vi_points, vmp, and imp properties since they won't
        # be valid if this method is being run with new property values.
        self.vi_points = []
        self.vmp = None
        self.imp = None

        # Step 1: Use the temperature-adjusted Voc, Isc, and MPP to
        # find the single-diode equation parameters of the curve at the
        # specified temperature, but still at STC irradiance.
        voc_isc_vmp_imp = [self.voc_at_temp, self.isc_at_temp,
                           self.vmp_at_temp, self.imp_at_temp]
        il_guess = self.isc_at_temp
        parms, results = find_parms(voc_isc_vmp_imp, il_guess,
                                    self.i0_guesses,
                                    self.a_guess,
                                    self.rs_guesses,
                                    self.rsh_guesses,
                                    self.err_thresh)
        il, i0, a, rs, rsh = parms
        eq1_res, eq2_res, eq3_res, eq4_res = results[0:4]
        eq5_res = test_eq5(rsh, [i0, a, rs, self.isc_at_temp])
        eq4_ignored = False
        if eq4_res == 0.0:
            eq4_res = test_eq4([self.vmp_at_temp, self.imp_at_temp],
                               [i0, a, rs, rsh])
            eq4_ignored = eq4_res != 0.0
        if self.debug:
            print "Best solution (Step 1):"
            print "  IL: {}".format(il)
            print "  I0: {}".format(i0)
            print "   A: {}".format(a)
            print "  Rs: {}".format(rs)
            print " Rsh: {}".format(rsh)
            print "\nResults:"
            print "  Eq1: {}".format(eq1_res)
            print "  Eq2: {}".format(eq2_res)
            print "  Eq3: {}".format(eq3_res)
            print "  Eq4: {}{}".format(eq4_res, " (Ignored)"
                                       if eq4_ignored else "")
            print "  Eq5: {}".format(eq5_res)
        self.eq1_result = eq1_res
        self.eq2_result = eq2_res
        self.eq3_result = eq3_res
        self.eq4_result = eq4_res
        self.eq5_result = eq5_res
        abs_results = [abs(res) for res in results]
        if max(abs_results) > self.err_thresh:
            if self.debug:
                print "  *** FAILED *** ({} is > {})".format(max(abs_results),
                                                             self.err_thresh)
            assert_str = u"ERROR: PV modeling for {} failed to find "
            assert_str += "a solution"
            pv_name_unicode = self.pv_name.decode("utf-8")
            assert False, assert_str.format(pv_name_unicode)

        # Step 2: Adjust for irradiance. For this model, this is
        # nothing more than scaling the IL parameter.
        il *= (self.irradiance / STC_IRRAD)

        # If the root-solving was successful (which it was if we have
        # gotten this far), set the property values of the five
        # parameters to the modeled values.
        self.il = il
        self.i0 = i0
        self.a = a
        self.rs = rs
        self.rsh = rsh

        # Update the Vmp and Imp properties
        self.update_mpp()

        # Record the run time
        elapsed_time = dt.datetime.now() - start_time
        self.run_ms = int(round(elapsed_time.total_seconds() * 1000))

        # For callers who care, the return value indicates if Eq4 was
        # ignored
        return eq4_ignored

    # -------------------------------------------------------------------------
    def update_mpp(self):
        """Method to update the Vmp and Imp of the IV curve for the PV
           module/cell at the specified temperature and irradiance.
        """
        if (self.il is None or self.i0 is None or
                self.a is None or self.rs is None or self.rsh is None):
            self.vmp = None
            self.imp = None
        else:
            vmp_guess = self.vmp_at_temp
            imp_guess = self.imp_at_temp * (self.irradiance / STC_IRRAD)
            mpp = root(test_mpp, x0=[vmp_guess, imp_guess],
                       args=([self.il, self.i0, self.a,
                              self.rs, self.rsh]))
            self.vmp = mpp.x[0]
            self.imp = mpp.x[1]

    # -------------------------------------------------------------------------
    def gen_vi_points(self, num_points):
        """Method to generate a list of V,I points for the modeled curve. This
           generator can be run only after a successful execution of the
           run() method. Each point is yielded as an (v,i) tuple,
        """
        mpp_added = False
        if self.voc is None:
            warnings.warn("No Voc. Has model been run successfully?",
                          UserWarning)
            return
        voc = self.voc
        # Number of loops is two less than num_points because MPP and
        # Voc are added
        num_loops = num_points - 2
        for ii in range(num_loops):
            # Voltage increments are proportional to the square root of
            # the point number. This results in large voltage increments
            # at Isc end of the curve and very small voltage increments
            # at the Voc end. This gives better resolution around the
            # MPP and also on the steep tail end of the curve where
            # small voltage increments map to large current increments.
            volts = voc * (ii**0.5) / float((num_loops)**0.5)
            # Since that probably won't include the actual MPP, we
            # insert it before inserting the first point with a voltage
            # higher than Vmp.
            if volts > self.vmp and not mpp_added:
                yield self.vmp, self.imp
                mpp_added = True
            # Run root solver to determine the current for this voltage
            x0 = [self.il]
            parms = [self.il, self.i0, self.a, self.rs, self.rsh]
            sol = root(test_i_given_v_and_parms, x0, args=(volts, parms))
            if sol.success:
                amps = sol.x[0]
                if amps > 0.0:
                    yield volts, amps
            else:
                warnings.warn("FAIL: v = {}".format(volts), UserWarning)
        # Add the Voc
        yield voc, 0.0

    # -------------------------------------------------------------------------
    def add_vi_points(self, num_points):
        """Method to add the specfied number of V,I points for the
           modeled curve to the vi_points property.
        """
        self.vi_points = self.gen_vi_points(num_points)

    # -------------------------------------------------------------------------
    def print_vi_points(self, num_points):
        """Method to print the list of V,I points. If the vi_points property
           is populated with the specified number of points, it will be
           used.  Otherwise, it will be created.
        """
        if len(self.vi_points) != num_points:
            self.add_vi_points(num_points)
        for point in self.vi_points:
            volts, amps = point
            print "{}, {}".format(volts, amps)

    # -------------------------------------------------------------------------
    def estimate_irrad(self, measured_isc):
        """Method to estimate irradiance, given the measured Isc value. The
           irradiance property is updated with the estimate. This method
           requires the cell_temp_c property to be valid (or at least a
           valid guess).
        """
        temp_diff_from_stc = self.cell_temp_c - STC_T_C
        self.irradiance = (STC_IRRAD * (measured_isc /
                                        (self.isc_stc *
                                         (1.0 + temp_diff_from_stc *
                                          self.isc_temp_coeff_pct_per_deg /
                                          100.0))))

    # -------------------------------------------------------------------------
    def estimate_temp_from_irrad(self, measured_isc):
        """Method to estimate cell temperature from the irradiance, given a
           measured Isc.
        """
        irrad = self.irradiance if self.irradiance > 0 else 0.001
        self.cell_temp_c = (((1 / ((irrad * self.isc_stc) /
                                   (STC_IRRAD * measured_isc))) - 1.0) /
                            (self.isc_temp_coeff_pct_per_deg/100.0)) + STC_T_C

    # -------------------------------------------------------------------------
    def estimate_temp(self, measured_voc, measured_isc):
        """Method to estimate temperature, given the measured Voc and Isc. The
           cell_temp_c property is updated with the estimate. This
           method requires the irradiance property to be valid (or at
           least a valid guess).
        """
        # First, estimate temperature from Isc
        self.estimate_temp_from_irrad(measured_isc)
        # Run the model with the the temperature and irradiance estimates
        self.run()
        # Calculate temperature error based on measured and modeled Voc
        temp_err = (((measured_voc / self.voc) - 1.0) /
                    (self.voc_temp_coeff_pct_per_deg/100.0))
        # Adjust temperature estimate accordingly
        self.cell_temp_c += temp_err

    # -------------------------------------------------------------------------
    def estimate_irrad_and_temp(self, measured_voc, measured_isc,
                                temp_err_thresh):
        """Method to estimate the irradiance and temperature, given measured
           values for Voc and Isc. This uses an iterative algorithm. The
           first step for each iteration is to estimate the irradiance.
           This is based on the estimated temperature and the measured
           Isc. Initially, the estimated temperature is 45 degrees C,
           which is a typical NOCT. The model is then run with the
           estimated temperature and irradiance. The resulting Voc is
           then compared with the measured Voc to determine the error in
           the estimated temperature. The estimated temperature is
           adjusted accordingly, and the next iteration uses that
           value. The iterations continue while the error in the
           estimated temperature is greater than the specified
           threshold.
        """
        self.cell_temp_c = 45.0  # Initial temperature estimate
        temp_err = 999999
        while abs(temp_err) > temp_err_thresh:
            # Estimate irradiance based on temperature and measured Isc
            self.estimate_irrad(measured_isc)
            # Estimate temperature based on irradiance and measured Voc
            temp_guess = self.cell_temp_c
            self.estimate_temp(measured_voc, measured_isc)
            temp_err = self.cell_temp_c - temp_guess

        # One last refinement of the estimated irradiance, using the
        # final estimated temperature
        self.estimate_irrad(measured_isc)


############
#   Main   #
############
def main():
    """Main function"""
    pv = PV_model()

    # Example: SunPower X21-345 at NOCI and NOCT
    pv.pv_name = "SunPower X21-345"
    pv.voc_stc = 68.2
    pv.isc_stc = 6.39
    pv.vmp_stc = 57.3
    pv.imp_stc = 6.02
    pv.num_cells = 96
    pv.voc_temp_coeff_mv_per_deg = -167.4  # mV per degree C
    pv.isc_temp_coeff_ma_per_deg = 2.9     # mA per degree C
    pv.mpp_temp_coeff_pct_per_deg = -0.29  # % per degree C
    pv.irradiance = NOC_IRRAD
    pv.cell_temp_c = 41.5  # NOCT from datasheet
    pv.debug = False

    # Run model. Voc, Isc, Vmp, Imp and Pmp should be close to datasheet
    # NOC values
    pv.run()
    pv.print_vi_points(100)
    print pv.parms_string
    print "Ideality factor: {}".format(pv.ideality_factor)
    print pv.summary_string
    print "PV model time: {} ms".format(pv.run_ms)

    # Now try reverse: estimate irradiance and temp from datasheet NOC
    # Voc and Isc values. They should be close to NOC irradiance and
    # temp.
    pv.estimate_irrad_and_temp(64.9, 5.16, 0.1)
    print "est_irrad = {}  est_temp = {}".format(pv.irradiance,
                                                 pv.cell_temp_c)


# Boilerplate main() call
if __name__ == '__main__':
    main()
