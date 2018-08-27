# LagBox WIP #

## Usage ##

LagBox can be used with different modes. While stepper mode and auto mode are used for latency measurements, the other modes serve debugging and testing purposes. You can set several parameters of the program via the command line.

##### Command Line Parameters #####
#
#
| Command | Function |
|---------|----------|
| -m      | Mode (0 = stepper mode, 1 = stepper latency test mode, 2 = stepper reset mode, 3 = auto mode, 4 = pressure sensor test mode) |
| -tmin   | minimum delay time in microseconds for auto mode |
| -tmax   | maximum delay time in microseconds for auto mode |
| -n      | number of test iterations |
| -b      | button code from input event (find out with evtest) |
| -d      | device type (1 = gamepad, 2 = mouse, 3 = keyboard) |
| -steps  | number of steps to test in stepper latency test mode |
| -delay  | delay between tests in stepper mode and stepper latency test mode |
| -dir    | direction to drive in stepper reset mode (1 (default) = up, -1 = down) |
| -event  | manually set the input event (find out with evtest) |
| -name   | manually set the device name that will appear in the log file |

##### Auto Mode #####

The most mature and reliable testing mode of the LagBox, known from our CHI paper. A button of a USB-connected input device is electrically triggered and the time until the input event arrives in the Linux kernel of the LagBox is measured.
This approach requires a bit of a setup as you have to connect (solder or clamp) wires to the two sides of the button you want to test. Connect those wires to the optocoupler that is controlled by the LagBox and connect the device to the LagBox via USB.
To specify the input device and -button, it is recommended to set them manually via the command line parameters -d and -b. If this does not work for some reason you might want to try the -event parameter to pass the input event of the device you want to test to the program.
The test results will be saved in '\.\./log/' as a .csv file with semicolons as separators.
If you want to use a simple GUI you can pipe the std output of auto mode into the python program latency_gui.py.

##### Stepper Mode #####

This mode is still work in progress will documented as soon as it works reliably.

## Code ##

##### inputLatencyMeasureTool.c #####

Contains the main functionality for all modes of the LagBox as well as some utility functions. Will be split up into multiple files at some point in the future.

##### fileLog.c #####

Handles building up and saving the log file for sensor data.

##### joystickControl.c #####

Handles the detection of input devices as well as setting up a connection to the kernel.

##### stepper.c #####

Small API for the DRV8834 stepper motor controller that drives the stepper motor used in stepper mode.

