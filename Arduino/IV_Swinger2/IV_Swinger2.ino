/*
 *-----------------------------------------------------------------------------
 *
 * IV_Swinger2.ino: IV Swinger 2 Arduino sketch
 *
 * Copyright (C) 2017,2018  Chris Satterlee
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 *-----------------------------------------------------------------------------
 *
 * IV Swinger and IV Swinger 2 are open source hardware and software
 * projects
 *
 * Permission to use the hardware designs is granted under the terms of
 * the TAPR Open Hardware License Version 1.0 (May 25, 2007) -
 * http://www.tapr.org/OHL
 *
 * Permission to use the software is granted under the terms of the GNU
 * GPL v3 as noted above.
 *
 * Current versions of the licensing files, documentation, Fritzing file
 * (hardware description), and software can be found at:
 *
 *    https://github.com/csatt/IV_Swinger
 *
 *-----------------------------------------------------------------------------
 *
 * This file contains the Arduino sketch for the IV Swinger 2. It
 * performs the following functions:
 *
 *     - Participates in handshakes with the host computer (via USB)
 *     - Receives configuration options from the host
 *     - Communicates debug messages to the host
 *     - Controls the relay that switches the capacitor between the
 *       bleed circuit and the PV circuit
 *     - Reads and records values from the two ADC channels
 *     - Waits for current to stabilize at the beginning
 *     - Compensates for the fact that time passes between the current
 *       and voltage measurements
 *     - Selectively discards values so that the Arduino memory isn't
 *       exhausted before the IV curve is complete
 *     - Determines when the IV curve is complete
 *     - Sends results to the host
 *
 * Performance is important. The rate that the curve is "swung" is a
 * function of the capacitor value and the PV module; there is no way to
 * slow it down (other than using a larger capacitance).  The faster the
 * software can take measurements, the closer together the points will
 * be, which improves the "resolution" of the IV curve.  Because i = C *
 * dv/dt, the speed of the sweep is not constant from the Isc end of the
 * curve to the Voc end. It is faster (i.e. dt is smaller) when current
 * (i) is higher and when the voltage change (dv) between points is
 * lower. At the beginning of the curve, i is high, but dv is also high,
 * so the sweep speed is moderate. And at the end of the curve, both i
 * and dv are low, so the sweep speed is also moderate. But just past
 * the knee, i is still high but dv is low, so the sweep rate is the
 * highest. If the software performance is poor, this part of the curve
 * will have poor resolution.
 *
 * The downside of taking measurements quickly is that too many
 * measurements are taken during the parts of the curve where the sweep
 * rate is low. The Arduino has very limited memory, so if all these
 * points are recorded, memory will be exhausted before the curve is
 * complete. The software must selectively discard points to prevent
 * this from happening. The trick is to determine which points to
 * discard. It is not useful to have points that are very close to each
 * other, so the discard criterion is based on the distance between
 * points. This calculation has to be very fast because it is performed
 * after every measurement, and that reduces the rate that measurements
 * can be taken. Any use of floating point math, or even 32-bit (long)
 * math slows things down drastically, so only 16-bit integer math is
 * used. Instead of Pythagorean distance, so-called Manhattan distance
 * is used, which only requires subtraction and addition. The criterion
 * distance could be a constant, but that would not produce good results
 * for all IV curves. Instead, it is scaled based on the measured values
 * for Voc and Isc. The Voc values are read before the relay is
 * activated and the Isc values are determined just after the relay is
 * activated. The minimum distance criterion calculation requires some
 * computation time between the first two measured points, but that is
 * not normally a resolution-sensitive part of the curve. Nevertheless,
 * this code is also restricted to simple 16-bit integer math in order
 * to make it as quick as possible.
 *
 * A single point on the curve requires reading both channels of the
 * ADC. There is no way to read both values at the same time; each read
 * requires a separate SPI transaction, so some time passes between the
 * two reads, and the values do not represent the exact same point in
 * time. The simplest way to deal with this would be to ignore it; if
 * the points are close enough together, the effect is relatively
 * minor. But it isn't difficult to compensate for, so we do.  One way
 * to compensate would be to do three reads for each pair
 * (i.e. CH0/CH1/CH0 or CH1/CH0/CH1) and average the first and third.
 * But that would slow things down by 50%.  Instead, we just do one read
 * of each channel on each iteration, but interpolate between the CH1
 * values of each iteration. The catch is that there is computation
 * between iterations (which takes time), so it's not a simple average;
 * it's a weighted average based on measured times.
 *
 */
#define VERSION "1.3.5"        // Version of this Arduino sketch

// Uncomment one or more of the following to enable the associated
// feature. Note, however, that enabling these features uses more of the
// Arduino's SRAM, so we have to reduce the maximum number of IV points
// accordingly to prevent running out of memory.
//#define DS18B20_SUPPORTED
//#define ADS1115_PYRANOMETER_SUPPORTED
//#define CAPTURE_UNFILTERED  // Debug only

#include <SPI.h>
#include <EEPROM.h>

#ifdef DS18B20_SUPPORTED
#include <OneWire.h>
#include <DallasTemperature.h>
#define DS18B20_SRAM 44
#else
#define DS18B20_SRAM 0
#endif

#ifdef ADS1115_PYRANOMETER_SUPPORTED
#include <Wire.h>
#include <Adafruit_ADS1015.h>
#define ADS1115_SRAM 224
#else
#define ADS1115_SRAM 0
#endif

#ifdef CAPTURE_UNFILTERED
#define MAX_UNFILTERED_POINTS 125
#define UNFILTERED_SRAM ((MAX_UNFILTERED_POINTS*4)+12)
#else
#define UNFILTERED_SRAM 0
#endif

#define MAX_UINT (1<<16)-1     // Max unsigned integer
#define MAX_INT (1<<15)-1      // Max integer
#define MAX_ULONG (1<<32)-1    // Max unsigned long integer
#define MAX_LONG (1<<31)-1     // Max long integer
#define MAX_MSG_LEN 35         // Maximum length of a host message
#define MSG_TIMER_TIMEOUT 1000 // Number of times to poll for host message
#define CLK_DIV SPI_CLOCK_DIV8 // SPI clock divider ratio
#define SERIAL_BAUD 57600      // Serial port baud rate
#define ADC_MAX 4096.0         // Max count of ADC (2^^num_bits)
#define ADC_CS_PIN 10          // Arduino pin used for ADC chip select
#define RELAY_PIN 2            // Arduino pin used to activate relay
#define ONE_WIRE_BUS 3         // Arduino pin used for one-wire bus (DS18B20)
#define SECOND_RELAY_PIN 4     // Arduino pin used to activate second relay
#define CS_INACTIVE HIGH       // Chip select is active low
#define CS_ACTIVE LOW          // Chip select is active low
#define VOLTAGE_CH 0           // ADC channel used for voltage measurement
#define CURRENT_CH 1           // ADC channel used for current measurement
#define VOC_POLLING_LOOPS 400  // Number of loops measuring Voc
#define FULL_MAX_IV_POINTS 275 // Max number of I/V pairs to capture
#define IV_POINT_REDUCTION ((DS18B20_SRAM+ADS1115_SRAM+UNFILTERED_SRAM)/4)
#define MAX_IV_POINTS (FULL_MAX_IV_POINTS - IV_POINT_REDUCTION)
#define MAX_IV_MEAS 1000000    // Max number of I/V measurements (inc discards)
#define CH1_1ST_WEIGHT 5       // Amount to weigh 1st CH1 value in avg calc
#define CH1_2ND_WEIGHT 3       // Amount to weigh 2nd CH1 value in avg calc
#define MIN_ISC_ADC 100        // Minimum ADC count for Isc
#define MAX_ISC_POLL 5000      // Max loops to wait for Isc to stabilize
#define ISC_STABLE_ADC 5       // Stable Isc changes less than this
#define MAX_DISCARDS 300       // Maximum consecutive discarded points
#define MIN_VOC_ADC 10         // Minimum value for Voc ADC value
#define ASPECT_HEIGHT 2        // Height of graph's aspect ratio (max 8)
#define ASPECT_WIDTH 3         // Width of graph's aspect ratio (max 8)
#define TOTAL_WEIGHT (CH1_1ST_WEIGHT + CH1_2ND_WEIGHT)
#define AVG_WEIGHT (int) ((TOTAL_WEIGHT + 1) / 2)
#define EEPROM_VALID_VALUE 123456.7890    // Must match IV_Swinger2.py
#define EEPROM_RELAY_ACTIVE_HIGH_ADDR 44  // Must match IV_Swinger2.py

// Compile-time assertion macros (from Stack Overflow)
#define COMPILER_ASSERT(predicate) _impl_CASSERT_LINE(predicate,__LINE__)
#define _impl_PASTE(a,b) a##b
#define _impl_CASSERT_LINE(predicate, line) \
    typedef char _impl_PASTE(assertion_failed_on_line_,line)[2*!!(predicate)-1];

// Compile-time assertions
COMPILER_ASSERT(MAX_IV_POINTS >= 10);
COMPILER_ASSERT(MAX_IV_MEAS <= (unsigned long) MAX_ULONG);
COMPILER_ASSERT(TOTAL_WEIGHT <= 16);
COMPILER_ASSERT(ASPECT_HEIGHT <= 8);
COMPILER_ASSERT(ASPECT_WIDTH <= 8);

// Global variables
char relay_active;
char relay_inactive;
int clk_div = CLK_DIV;
int max_iv_points = MAX_IV_POINTS;
int min_isc_adc = MIN_ISC_ADC;
int max_isc_poll = MAX_ISC_POLL;
int isc_stable_adc = ISC_STABLE_ADC;
int max_discards = MAX_DISCARDS;
int aspect_height = ASPECT_HEIGHT;
int aspect_width = ASPECT_WIDTH;
const static char ready_str[] PROGMEM = "Ready";
const static char config_str[] PROGMEM = "Config";
const static char go_str[] PROGMEM = "Go";
const static char clk_div_str[] PROGMEM = "CLK_DIV";
const static char max_iv_points_str[] PROGMEM = "MAX_IV_POINTS";
const static char min_isc_adc_str[] PROGMEM = "MIN_ISC_ADC";
const static char max_isc_poll_str[] PROGMEM = "MAX_ISC_POLL";
const static char isc_stable_adc_str[] PROGMEM = "ISC_STABLE_ADC";
const static char max_discards_str[] PROGMEM = "MAX_DISCARDS";
const static char aspect_height_str[] PROGMEM = "ASPECT_HEIGHT";
const static char aspect_width_str[] PROGMEM = "ASPECT_WIDTH";
const static char write_eeprom_str[] PROGMEM = "WRITE_EEPROM";
const static char dump_eeprom_str[] PROGMEM = "DUMP_EEPROM";
const static char relay_state_str[] PROGMEM = "RELAY_STATE";
const static char second_relay_state_str[] PROGMEM = "SECOND_RELAY_STATE";

#ifdef DS18B20_SUPPORTED
// Global setup for DS18B20 temperature sensor
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);
int num_ds18b20s;
#endif
#ifdef ADS1115_PYRANOMETER_SUPPORTED
// Global setup for ADS1115-based pyranometer
Adafruit_ADS1115 ads1115;
#endif

void setup()
{
  bool host_ready = false;
  char incoming_msg[MAX_MSG_LEN];

  // Get relay type from EEPROM (active-low or active-high)
  relay_active = get_relay_active_val();
  relay_inactive = (relay_active == LOW) ? HIGH : LOW;

  // Initialization
  pinMode(ADC_CS_PIN, OUTPUT);
  digitalWrite(ADC_CS_PIN, CS_INACTIVE);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, relay_inactive);
  pinMode(SECOND_RELAY_PIN, OUTPUT);
  digitalWrite(SECOND_RELAY_PIN, relay_inactive);
  Serial.begin(SERIAL_BAUD);
  SPI.begin();
  SPI.setClockDivider(clk_div);
#ifdef DS18B20_SUPPORTED
  // DS18B20 temperature sensor init
  sensors.begin();
  num_ds18b20s = sensors.getDS18Count();
  if (num_ds18b20s) {
    sensors.setResolution(10);
  }
#endif
#ifdef ADS1115_PYRANOMETER_SUPPORTED
  adsGain_t ads1115_gain;
  ads1115.begin();
  ads1115.setGain(GAIN_EIGHT);
#endif

  // Print version number
  Serial.print(F("IV Swinger2 sketch version "));
  Serial.println(F(VERSION));

  // Tell host that we're ready, and wait for config messages and
  // acknowledgement
  host_ready = false;
  while (!host_ready) {
    Serial.println(F("Ready"));
    if (get_host_msg(incoming_msg)) {
      if (strstr_P(incoming_msg, ready_str)) {
        host_ready = true;
      }
      else if (strstr_P(incoming_msg, config_str)) {
        process_config_msg(incoming_msg);
        Serial.println(F("Config processed"));
      }
    }
  }
#ifdef DS18B20_SUPPORTED
  Serial.println(F("DS18B20 temperature sensor is SUPPORTED"));
#else
  Serial.println(F("DS18B20 temperature sensor is NOT supported"));
#endif
#ifdef ADS1115_PYRANOMETER_SUPPORTED
  Serial.println(F("ADS1115-based pyranometer is SUPPORTED"));
#else
  Serial.println(F("ADS1115-based pyranometer is NOT supported"));
#endif
#ifdef CAPTURE_UNFILTERED
  Serial.println(F("Debug capture of unfiltered IV points is SUPPORTED"));
#else
  Serial.println(F("Debug capture of unfiltered IV points is NOT supported"));
#endif
  // Print value of MAX_IV_POINTS / max_iv_points
  Serial.print(F("MAX_IV_POINTS: "));
  Serial.print(MAX_IV_POINTS);
  Serial.print(F("   max_iv_points: "));
  Serial.println(max_iv_points);
#ifdef DS18B20_SUPPORTED
  // Print temp sensor info 
  for (int ii = 0; ii < num_ds18b20s; ii++) {
    DeviceAddress rom_code;
    sensors.getAddress(rom_code, ii);
    Serial.print(F("ROM code of DS18B20 temp sensor #"));
    Serial.print(ii+1);
    Serial.print(F(" is 0x"));
    for (int jj = 7; jj >= 0; jj--) {
      if (rom_code[jj] < 16) Serial.print('0');
      Serial.print(rom_code[jj], HEX);
    }
    Serial.println("");
  }
#endif
}

void loop()
{
  // Arduino: ints are 16 bits
  bool go_msg_received;
  bool update_prev_ch1 = false;
  bool poll_timeout = false;
  bool skip_isc_poll = false;
  bool count_updated = false;
  bool voc_adc_found = false;
  char incoming_msg[MAX_MSG_LEN];
  int ii;
  int index = 0;
  int max_count = 0;
  int adc_ch0_delta, adc_ch1_delta, adc_ch1_prev_delta;
  int manhattan_distance, min_manhattan_distance;
  int pt_num = 1;   // counts points actually recorded
  int isc_poll_loops = 0;
  int num_discarded_pts = 0;
  int i_scale, v_scale;
  int adc_ch0_vals[MAX_IV_POINTS], adc_ch1_vals[MAX_IV_POINTS];
  int isc_adc, voc_adc;
  int adc_noise_floor, min_adc_noise_floor, max_adc_noise_floor;
  int done_ch1_adc;
  int adc_ch0_val_prev_prev, adc_ch0_val_prev, adc_ch0_val;
  int adc_ch1_val_prev_prev, adc_ch1_val_prev, adc_ch1_val;
  unsigned long num_meas = 1; // counts IV measurements taken
  long start_usecs, elapsed_usecs;
  float usecs_per_iv_pair;
#ifdef CAPTURE_UNFILTERED
  bool capture_unfiltered = false;
  int unfiltered_index = 0;
  int unfiltered_adc_ch0_vals[MAX_UNFILTERED_POINTS];
  int unfiltered_adc_ch1_vals[MAX_UNFILTERED_POINTS];
#endif

  // Wait for go (or config) message from host
  Serial.println(F("Waiting for go message or config message"));
  go_msg_received = false;
  while (!go_msg_received) {
    if (get_host_msg(incoming_msg)) {
      if (strstr_P(incoming_msg, go_str)) {
        go_msg_received = true;
      }
      else if (strstr_P(incoming_msg, config_str)) {
        process_config_msg(incoming_msg);
        Serial.println(F("Config processed"));
      }
    }
  }

  // Get Voc ADC value and CH1 ADC noise floor
  voc_adc = 0;
  adc_noise_floor = ADC_MAX;
  min_adc_noise_floor = ADC_MAX;
  max_adc_noise_floor = 0;
  memset(adc_ch0_vals, 0, sizeof(adc_ch0_vals));
  memset(adc_ch1_vals, 0, sizeof(adc_ch1_vals));
  for (ii = 0; ii < VOC_POLLING_LOOPS; ii++) {
    adc_ch0_val = read_adc(VOLTAGE_CH);  // Read CH0 (voltage)
    adc_ch1_val = read_adc(CURRENT_CH);  // Read CH1 (current)
    // Update frequency count for this CH0 value. We temporarily use the
    // adc_ch0_vals array for the values and the adc_ch1_vals array for
    // the counts
    for (index = 0, count_updated = false;
         (index < sizeof(adc_ch0_vals)) && !count_updated;
         index++) {
      if (adc_ch1_vals[index] == 0) { // first empty slot
        adc_ch0_vals[index] = adc_ch0_val;
        adc_ch1_vals[index] = 1; // count
        count_updated = true;
      } else if (adc_ch0_vals[index] == adc_ch0_val) {
        adc_ch1_vals[index]++; // count
        count_updated = true;
      }
    }
    // The ADC noise floor is the value read from the ADC when it
    // "should" be zero.  At this point, we know that the actual current
    // is zero because the circuit is open, so whatever value is read on
    // CH1 is the noise floor value.  IVS2 implementations that are
    // targeted for low power PV cells need a very high gain
    // amplification of the voltage across the shunt resistor, which
    // results in a very high noise floor that has been observed to
    // cycle up and down.  Here we identify the top and bottom values of
    // that cycling.
    if (adc_ch1_val < min_adc_noise_floor) {
      min_adc_noise_floor = adc_ch1_val;
    }
    if (adc_ch1_val > max_adc_noise_floor) {
      max_adc_noise_floor = adc_ch1_val;
    }
  }

  // The Voc ADC value is the most common value seen during polling
  for (index = 0, voc_adc_found = false, max_count = 0;
       (index < sizeof(adc_ch0_vals)) && !voc_adc_found;
       index++) {
    if (adc_ch1_vals[index] == 0) {
      // When we see a slot with a zero count, we're done
      voc_adc_found = true;
    } else if (adc_ch1_vals[index] > max_count) {
      voc_adc = adc_ch0_vals[index];
      max_count = adc_ch1_vals[index];
    }
  }
  
  if (max_adc_noise_floor - min_adc_noise_floor > 10) {
    // If the noise floor is cycling by more than 10 ADC units, we
    // attempt to catch it at a point that is near the bottom
    for (ii = 0; ii < VOC_POLLING_LOOPS; ii++) {
      adc_ch0_val = read_adc(VOLTAGE_CH);  // Read CH0 (voltage)
      adc_ch1_val = read_adc(CURRENT_CH);  // Read CH1 (current)
#ifdef CAPTURE_UNFILTERED
      if (unfiltered_index < MAX_UNFILTERED_POINTS) {
        unfiltered_adc_ch1_vals[unfiltered_index] = adc_ch1_val;
        unfiltered_adc_ch0_vals[unfiltered_index++] = adc_ch0_val;
      }
#endif
      if (adc_ch1_val <= min_adc_noise_floor + 5) {
        break;
      }
    }
  }
  adc_noise_floor = min_adc_noise_floor;
  // Increase minimum Isc ADC value by noise floor
  min_isc_adc += adc_noise_floor;

  // Determine the CH1 ADC value that indicates the curve has reached
  // its tail.  This value is twice the noise floor value, or 20;
  // whichever is greater.
  done_ch1_adc = adc_noise_floor << 1;
  if (done_ch1_adc < 20) {
    done_ch1_adc = 20;
  }

  // Activate relay
  digitalWrite(RELAY_PIN, relay_active);

  // Wait until three consecutive measurements:
  //   - have current greater than min_isc_adc
  //   - have increasing or equal voltage
  //   - have decreasing or equal voltage
  //   - have a current difference less than or equal to isc_stable_adc
  adc_ch0_val_prev_prev = ADC_MAX;
  adc_ch0_val_prev = ADC_MAX;
  adc_ch1_val_prev_prev = 0;
  adc_ch1_val_prev = 0;
  if (voc_adc < MIN_VOC_ADC) {
    // If the Voc ADC value is lower than MIN_VOC_ADC we assume that it
    // is actually zero (not connected) and we force it to zero and skip
    // the Isc polling
    skip_isc_poll = true;
    voc_adc = 0;
  } else {
    skip_isc_poll = false;
    poll_timeout = true;
  }
  for (ii = 0; ii < max_isc_poll; ii++) {
    if (skip_isc_poll)
      break;
    adc_ch1_val = read_adc(CURRENT_CH);  // Read CH1 (current)
    adc_ch0_val = read_adc(VOLTAGE_CH);  // Read CH0 (voltage)
#ifdef CAPTURE_UNFILTERED
    if (((adc_ch1_val > min_isc_adc) || capture_unfiltered) &&
        (unfiltered_index < MAX_UNFILTERED_POINTS)) {
      unfiltered_adc_ch1_vals[unfiltered_index] = adc_ch1_val;
      unfiltered_adc_ch0_vals[unfiltered_index++] = adc_ch0_val;
      capture_unfiltered = true;
    }
#endif
    isc_poll_loops = ii + 1;
    // Nested ifs should be faster than &&
    if (adc_ch1_val > min_isc_adc) {
      // Current is greater than min_isc_adc
      if (adc_ch0_val >= adc_ch0_val_prev) {
        if (adc_ch0_val_prev >= adc_ch0_val_prev_prev) {
          // Voltage is increasing or equal
          if ((adc_ch1_val <= adc_ch1_val_prev) ||
              (adc_ch1_val_prev <= adc_ch1_val_prev_prev)) {
            // Current is decreasing or equal
            if (abs(adc_ch1_val_prev - adc_ch1_val) <= isc_stable_adc) {
              if (abs(adc_ch1_val_prev_prev -
                      adc_ch1_val_prev) <= isc_stable_adc) {
                // Current differences are less than or equal to
                // isc_stable_adc
                poll_timeout = false;
                break;
              }
            }
          }
        }
        // Shift all values
        adc_ch0_val_prev_prev = adc_ch0_val_prev;
        adc_ch1_val_prev_prev = adc_ch1_val_prev;
        adc_ch0_val_prev = adc_ch0_val;
        adc_ch1_val_prev = adc_ch1_val;
      } else {
        // If voltage decreases, discard the previous point but keep the
        // one before that
        adc_ch0_val_prev = adc_ch0_val;
        adc_ch1_val_prev = adc_ch1_val;
      }
    }
  }
  if (poll_timeout)
    Serial.println(F("Polling for stable Isc timed out"));

  // Isc is approximately the value of the first of the three points
  // above
  isc_adc = adc_ch1_val_prev_prev;

  // First IV pair (point number 0) is last point from polling
  adc_ch0_vals[0] = adc_ch0_val;
  adc_ch1_vals[0] = adc_ch1_val;

  // Get v_scale and i_scale
  compute_v_and_i_scale(isc_adc, voc_adc, &v_scale, &i_scale);

  // Calculate the minimum scaled adc delta value. This is the Manhattan
  // distance between the Isc point and the Voc point divided by the
  // maximum number of points (minus 2 for safety). This guarantees that
  // we won't run out of memory before the complete curve is
  // captured. However, it will usually result in a number of captured
  // points that is a fair amount lower than max_iv_points. The
  // max_iv_points value is how many points there -would- be if -all-
  // points were the minimum distance apart. But some points will be
  // farther apart than the minimum distance. One reason is simply
  // because, unless max_iv_points is set to a very small number, there
  // are portions of the curve where the limiting factor is the rate
  // that the measurements can be taken; even without discarding
  // measurements, the points are farther apart than the minimum. The
  // other reason is that it is unlikely that a measurement comes at
  // exactly the mimimum distance from the previously recorded
  // measurement, so the first one that does satisfy the requirement may
  // have overshot the minimum by nearly a factor of 2:1 in the worst
  // case.
  min_manhattan_distance = (unsigned int) ((isc_adc * i_scale) +
                            (voc_adc * v_scale)) / (max_iv_points - 2);

  // Proceed to read remaining points on IV curve. Compensate for the
  // fact that time passes between I and V measurements by using a
  // weighted average for I. Discard points that are not a minimum
  // "Manhattan distance" apart (scaled sum of V and I ADC values).
  adc_ch1_val_prev = adc_ch1_vals[0];
  start_usecs = micros();
  while (num_meas < MAX_IV_MEAS) {
    num_meas++;
    //----------------------------------------------------
    // Read both channels back-to-back. Channel 1 is first since it was
    // first in the reads for point 0 above.
    adc_ch1_val = read_adc(CURRENT_CH);  // Read CH1 (current)
    adc_ch0_val = read_adc(VOLTAGE_CH);  // Read CH0 (voltage)
#ifdef CAPTURE_UNFILTERED
    //------------------------- Unfiltered ----------------------
    if (unfiltered_index < MAX_UNFILTERED_POINTS) {
      unfiltered_adc_ch1_vals[unfiltered_index] = adc_ch1_val;
      unfiltered_adc_ch0_vals[unfiltered_index++] = adc_ch0_val;
    }
#endif
    //--------------------- CH1: current -----------------
    if (update_prev_ch1) {
      // Adjust previous CH1 value to weighted average with this value.
      // 16-bit integer math!! Max ADC value is 4095, so no overflow as
      // long as sum of CH1_1ST_WEIGHT and CH1_2ND_WEIGHT is 16 or less.
      adc_ch1_vals[pt_num-1] = (adc_ch1_val_prev * CH1_1ST_WEIGHT +
                                adc_ch1_val * CH1_2ND_WEIGHT +
                                AVG_WEIGHT) / TOTAL_WEIGHT;
    }
    //--------------------- CH0: voltage -----------------
    adc_ch0_vals[pt_num] = adc_ch0_val;
    //------------------------ Deltas  -------------------
    adc_ch0_delta = adc_ch0_val - adc_ch0_vals[pt_num-1];
    adc_ch0_val_prev = adc_ch0_val;
    adc_ch1_delta = adc_ch1_vals[pt_num-1] - adc_ch1_val;
    adc_ch1_prev_delta = adc_ch1_val_prev - adc_ch1_val;
    adc_ch1_val_prev = adc_ch1_val;
    //---------------------- Done check  -----------------
    // Check if we've reached the tail of the curve.
    if (adc_ch1_val < done_ch1_adc) {
      // Current is very close to zero so we're PROBABLY done
      if (adc_ch1_prev_delta < 3) {
        // But only if the current delta is very small
        break;
      }
    }
    // We're also done if Isc polling timed out
    if (poll_timeout) {
      break;
    }
    //--------------- Voltage decrease check -------------
    // At this point we know that all preceding points are in order of
    // increasing voltage.  However, it is possible that one or more of
    // them are erroneously high due to relay "bounce". This is detected
    // when the voltage of this point is lower than the voltage of the
    // previous point. If that is the case, we search backwards through
    // the previous points until we find one that has a lower voltage
    // and replace its successor with the current point and rewind the
    // pt_num counter. While it is probably not possible for the bounce
    // to span more than two or three points, this covers the general
    // case of it spanning N points (and starting at any point).
    if (adc_ch0_val < adc_ch0_vals[pt_num-1]) {
      while (pt_num > 1) {
        if (adc_ch0_val < adc_ch0_vals[pt_num-2]) {
          pt_num--;
        } else {
          break;
        }
      } 
      adc_ch0_vals[pt_num-1] = adc_ch0_val;
      adc_ch1_vals[pt_num-1] = adc_ch1_val;
      update_prev_ch1 = true; // Adjust this CH1 value on next measurement
      continue;
    }
    //------------------- Discard decision ---------------
    // "Manhattan distance" is sum of scaled deltas
    manhattan_distance = (adc_ch0_delta * v_scale) + (adc_ch1_delta * i_scale);
    // Keep measurement if Manhattan distance is big enough; otherwise
    // discard.  However, if we've discarded max_discards consecutive
    // measurements, then keep it anyway.
    if ((manhattan_distance >= min_manhattan_distance) ||
        (num_discarded_pts >= max_discards)) {
      // Keep this one
      pt_num++;
      update_prev_ch1 = true; // Adjust this CH1 value on next measurement
      num_discarded_pts = 0;  // Reset discard counter
      if (pt_num >= max_iv_points) {
        // We're done
        break;
      }
    } else {
      // Don't record this one
      update_prev_ch1 = false; // And don't adjust prev CH1 val next time
      num_discarded_pts++;
    }
  }
  if (update_prev_ch1) {
    // Last one didn't get adjusted (or even saved), so save it now
    adc_ch1_vals[pt_num-1] = adc_ch1_val;
  }
  elapsed_usecs = micros() - start_usecs;
  digitalWrite(RELAY_PIN, relay_inactive);

  // Report results on serial port
  //
#ifdef ADS1115_PYRANOMETER_SUPPORTED
  // Irradiance
    int16_t ads1115_val;
    ads1115_val = ads1115.readADC_Differential_0_1();
    if (ads1115_val != -1) {  // Value of -1 indicates no ADS1115 is present
      Serial.print(F("ADS1115 (pyranometer) raw value: "));
      Serial.println(ads1115_val);
    }
#endif
#ifdef DS18B20_SUPPORTED
  // Temperature
  if (num_ds18b20s) {
    sensors.requestTemperatures();
    for (int ii = 0; ii < num_ds18b20s; ii++) {
      Serial.print(F("Temperature at sensor #"));
      Serial.print(ii+1);
      Serial.print(F(" is "));
      Serial.print(sensors.getTempCByIndex(ii));
      Serial.println(F(" degrees Celsius"));
    }
  }
#endif
  // CH1 ADC noise floor
  Serial.print(F("CH1 ADC noise floor:"));
  Serial.println(adc_noise_floor);
  // Isc point
  Serial.print(F("Isc CH0:0"));
  Serial.print(F(" CH1:"));
  Serial.println(isc_adc);
  // Middle points
  for (ii = 0; ii < pt_num; ii++) {
    Serial.print(ii);
    Serial.print(F(" CH0:"));
    Serial.print(adc_ch0_vals[ii]);
    Serial.print(F(" CH1:"));
    Serial.println(adc_ch1_vals[ii]);
  }
  // Voc point
  Serial.print(F("Voc CH0:"));
  Serial.print(voc_adc);
  Serial.print(F(" CH1:"));
  Serial.println(adc_noise_floor);
#ifdef CAPTURE_UNFILTERED
  for (ii = 0; ii < unfiltered_index; ii++) {
    Serial.print(ii);
    Serial.print(F(" Unfiltered CH0:"));
    Serial.print(unfiltered_adc_ch0_vals[ii]);
    Serial.print(F(" Unfiltered CH1:"));
    Serial.println(unfiltered_adc_ch1_vals[ii]);
  }
#endif
  Serial.print(F("Isc poll loops: "));
  Serial.println(isc_poll_loops);
  Serial.print(F("Number of measurements: "));
  Serial.println(num_meas);
  Serial.print(F("Number of recorded points: "));
  Serial.println(pt_num);
  Serial.print(F("i_scale: "));
  Serial.println(i_scale);
  Serial.print(F("v_scale: "));
  Serial.println(v_scale);
  Serial.print(F("min_manhattan_distance: "));
  Serial.println(min_manhattan_distance);
  Serial.print(F("Elapsed usecs: "));
  Serial.println(elapsed_usecs);
  usecs_per_iv_pair = (float) elapsed_usecs / num_meas;
  Serial.print(F("Time (usecs) per i/v reading: "));
  Serial.println(usecs_per_iv_pair);
  Serial.println(F("Output complete"));

}

bool get_host_msg(char * msg) {
  bool msg_received = false;
  char c;
  int char_num = 0;
  int msg_timer;
  msg_timer = MSG_TIMER_TIMEOUT;
  while (msg_timer && !msg_received) {
    if (Serial.available()) {
      c = Serial.read();
      if (c == '\n') {
        // Substitute NULL for newline
        msg[char_num++] = '\0';
        msg_received = true;
        Serial.print(F("Received host message: "));
        Serial.println(msg);
        break;
      } else {
        msg[char_num++] = c;
      }
      msg_timer = MSG_TIMER_TIMEOUT;
    } else {
      msg_timer--;
    }
    delay(1);
  }
  return (msg_received);
}

void process_config_msg(char * msg) {
  char *substr;
  char *config_type;
  char *config_val;
  char *config_val2;
  int ii = 0;
  int eeprom_addr;
  float eeprom_value;
  substr = strtok(msg, " ");  // "Config:"
  while (substr != NULL) {
    substr = strtok(NULL, " ");
    if (ii == 0) {
      config_type = substr;
    } else if (ii == 1) {
      config_val = substr;
    } else if (ii == 2) {
      config_val2 = substr;
    } else if (substr != NULL) {
      Serial.println(F("ERROR: Too many fields in config message"));
      break;
    }
    ii++;
  }
  if (strcmp_P(config_type, clk_div_str) == 0) {
    clk_div = atoi(config_val);
    SPI.setClockDivider(clk_div);
  } else if (strcmp_P(config_type, max_iv_points_str) == 0) {
    max_iv_points = atoi(config_val);
    if (max_iv_points > MAX_IV_POINTS) {
      max_iv_points = MAX_IV_POINTS;
    }
  } else if (strcmp_P(config_type, min_isc_adc_str) == 0) {
    min_isc_adc = atoi(config_val);
  } else if (strcmp_P(config_type, max_isc_poll_str) == 0) {
    max_isc_poll = atoi(config_val);
  } else if (strcmp_P(config_type, isc_stable_adc_str) == 0) {
    isc_stable_adc = atoi(config_val);
  } else if (strcmp_P(config_type, max_discards_str) == 0) {
    max_discards = atoi(config_val);
  } else if (strcmp_P(config_type, aspect_height_str) == 0) {
    aspect_height = atoi(config_val);
  } else if (strcmp_P(config_type, aspect_width_str) == 0) {
    aspect_width = atoi(config_val);
  } else if (strcmp_P(config_type, write_eeprom_str) == 0) {
    eeprom_addr = atoi(config_val);
    eeprom_value = atof(config_val2);
    EEPROM.put(eeprom_addr, eeprom_value);
    if (eeprom_addr == EEPROM_RELAY_ACTIVE_HIGH_ADDR) {
      relay_active = (eeprom_value == LOW) ? LOW : HIGH;
      relay_inactive = (relay_active == LOW) ? HIGH : LOW;
      digitalWrite(RELAY_PIN, relay_inactive);
      digitalWrite(SECOND_RELAY_PIN, relay_inactive);
    }
  } else if (strcmp_P(config_type, dump_eeprom_str) == 0) {
    dump_eeprom();
  } else if (strcmp_P(config_type, relay_state_str) == 0) {
    set_relay_state((bool)atoi(config_val));
  } else if (strcmp_P(config_type, second_relay_state_str) == 0) {
    set_second_relay_state((bool)atoi(config_val));
  } else {
    Serial.print(F("ERROR: Unknown config type: "));
    Serial.println(config_type);
  }
}

void dump_eeprom() {
  int eeprom_addr, eeprom_valid_count;
  float eeprom_value;

  // Dump valid EEPROM entries
  EEPROM.get(0, eeprom_value);
  // Only dump if address 0 has "magic" value
  if (eeprom_value == EEPROM_VALID_VALUE) {
    // Second location has count of valid entries
    EEPROM.get(sizeof(float), eeprom_value);
    eeprom_valid_count = (int)eeprom_value;
    for (eeprom_addr = 0;
         eeprom_addr < ((eeprom_valid_count + 2) * sizeof(float));
         eeprom_addr += sizeof(float)) {
      EEPROM.get(eeprom_addr, eeprom_value);
      Serial.print(F("EEPROM addr: "));
      Serial.print(eeprom_addr, DEC);
      Serial.print(F("  value: "));
      Serial.println(eeprom_value, 4);
    }
  }
}

char get_relay_active_val() {
  // The IV Swinger 2 hardware design calls for an active-low triggered
  // relay module.  Support has been added now for the alternate use of
  // an active-high triggered relay module. The host software writes
  // EEPROM address 44 with either the value 0 or 1 indicating
  // active-low or active-high repectively. At the beginning of setup()
  // this function is called to determine which type the relay is.  It
  // is possible that EEPROM has not been written yet, or that it was
  // written by an older version of the host software and does not have
  // a valid value at address 44.  In either of these cases, the default
  // value of LOW is returned.
  int eeprom_valid_count;
  float eeprom_value;

  // Check that address 0 has "magic" value
  EEPROM.get(0, eeprom_value);
  if (eeprom_value == EEPROM_VALID_VALUE) {
    // Second location has count of valid entries
    EEPROM.get(sizeof(float), eeprom_value);
    eeprom_valid_count = (int)eeprom_value;
    // Check that EEPROM contains an entry for the relay active value
    if ((eeprom_valid_count + 1) * sizeof(float) >=
        EEPROM_RELAY_ACTIVE_HIGH_ADDR) {
      EEPROM.get(EEPROM_RELAY_ACTIVE_HIGH_ADDR, eeprom_value);
      if (eeprom_value == 0) {
        return (LOW);
      } else {
        return (HIGH);
      }
    } else {
      // If EEPROM is not programmed with the relay active value, we
      // have to assume it is active-low
      return (LOW);
    }
  } else {
    // If EEPROM is not programmed (at all), we have to assume the relay
    // is active-low
    return (LOW);
  }
}

void set_relay_state(bool active) {
  if (active) {
    digitalWrite(RELAY_PIN, relay_active);
  } else { 
    digitalWrite(RELAY_PIN, relay_inactive);
  }
}

void set_second_relay_state(bool active) {
  if (active) {
    digitalWrite(SECOND_RELAY_PIN, relay_active);
  } else { 
    digitalWrite(SECOND_RELAY_PIN, relay_inactive);
  }
}

int read_adc(int ch) {
  // This code assumes MCP3202.  MCP3302 would be slightly different.
  int ms_byte, ls_byte, cmd_bytes;
  cmd_bytes = (ch == 0) ?
    B10100000 :                          // SGL/~DIFF=1, CH=0, MSBF=1
    B11100000;                           // SGL/~DIFF=1, CH=1, MSBF=1
  digitalWrite(ADC_CS_PIN, CS_ACTIVE);   // Assert active-low chip select
  SPI.transfer (B00000001);              // START=1
  ms_byte = SPI.transfer(cmd_bytes);     // Send command, get result
  ms_byte &= B00001111;                  // Bits 11:8 (mask others)
  ls_byte = SPI.transfer(0x00);          // Bits 7:0
  digitalWrite(ADC_CS_PIN, CS_INACTIVE); // Deassert active-low chip select
  return ((ms_byte << 8) | ls_byte);     // {ms_byte, lsb}
}

void compute_v_and_i_scale(int isc_adc, int voc_adc,
                           int * v_scale, int * i_scale) {

  // Find integer scaling values for V and I, with the sum of the values
  // being 16 or less.  These values are used for calculating the
  // "Manhattan distance" between points when making the discard
  // decision. The idea is that the criterion for the minimum distance
  // between points on a horizontal part of the curve should be equal to
  // the criterion for the minimum distance between points on a vertical
  // part of the curve. The distance is literally the spacing on the
  // graph. The distance between points on a diagonal part of the curve
  // is overcounted somewhat, but that results in slightly closer points
  // near the knee(s) of the curve, and that is good. The two factors
  // that determine the distance are:
  //
  //       - The maximum ADC value of the axis
  //       - The aspect ratio of the graph
  //
  // The maximum value on the X-axis (voltage) is the Voc ADC value.
  // The maximum value on the Y-axis (current) is the Isc ADC value.
  // Since the graphs are rendered in a rectangular aspect ratio, the
  // scale of the axes differs. The initial scaling values could be:
  //
  //     initial_v_scale = aspect_width / voc_adc;
  //     initial_i_scale = aspect_height / isc_adc;
  //
  // That would require large values for aspect_width and aspect_height
  // to use integer math. Instead, proportional (but much larger) values
  // can be computed with:
  //
  //     initial_v_scale = aspect_width * isc_adc;
  //     initial_i_scale = aspect_height * voc_adc;
  //
  // An algorithm is then performed to reduce the values proportionally
  // such that the sum of the values is 16 or less.
  //
  // This function is only run once, but speed is important, so 16-bit
  // integer math is used exclusively (no floats or longs).
  //

  bool i_scale_gt_v_scale;
  int initial_v_scale, initial_i_scale;
  int lg, sm, round_up_mask;
  int lg_scale, sm_scale;
  char bit_num, shift_amt = 0;
  initial_v_scale = aspect_width * isc_adc;
  initial_i_scale = aspect_height * voc_adc;
  i_scale_gt_v_scale = initial_i_scale > initial_v_scale;
  lg = i_scale_gt_v_scale ? initial_i_scale : initial_v_scale;
  sm = i_scale_gt_v_scale ? initial_v_scale : initial_i_scale;

  // Find leftmost bit that is set in the larger initial value. The
  // right shift amount is three less than this bit number (to result in
  // a 4-bit value, i.e. 15 or less). Also look at the highest bit that
  // will be shifted off, to see if we should round up by adding one to
  // the resulting shifted amount.  If we get all the way down to bit 4
  // and it isn't set, the initial values will be used as-is.
  for (bit_num = 15; bit_num >= 4; bit_num--) {
    if (lg & (1 << bit_num)) {
      shift_amt = bit_num - 3;
      round_up_mask = (1 << (bit_num - 4));
      break;
    }
  }
  // Shift, and increment shifted amount if rounding up is needed
  lg_scale = (lg & round_up_mask) ? (lg >> shift_amt) + 1 : (lg >> shift_amt);
  sm_scale = (sm & round_up_mask) ? (sm >> shift_amt) + 1 : (sm >> shift_amt);
  // If the sum of these values is greater than 16, divide them both by
  // two (no rounding up here)
  if (lg_scale + sm_scale > 16) {
    lg_scale >>= 1;
    sm_scale >>= 1;
  }
  // Make sure sm_scale is at least 1 (necessary?)
  if (sm_scale == 0) {
    sm_scale = 1;
    if (lg_scale == 16)
      lg_scale = 15;
  }
  // Return values at pointer locations
  *v_scale = i_scale_gt_v_scale ? sm_scale : lg_scale;
  *i_scale = i_scale_gt_v_scale ? lg_scale : sm_scale;
}
