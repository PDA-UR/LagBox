/*
	Input Latency Measurement v2.0
	Software for input device measurement based on the Raspberry Pi

	Copyright (C) 2015 Simon Fuernstein
	Copyright (C) 2015 Oliver Pieper
	Copyright (C) 2016 Mark Engerißer
	Copyright (C) 2018 Andreas Schmid

	This program is free software: you can redistribute it and/or modify
	it under the terms of the GNU General Public License as published by
	the Free Software Foundation, either version 3 of the License, or
	(at your option) any later version.

	This program is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU General Public License for more details.

	You should have received a copy of the GNU General Public License
	along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

// Standard includes
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <time.h>
#include <sys/time.h>
#include <sys/sysinfo.h>
#include <stdint.h>
#include <stdarg.h>
#include <pthread.h>
#include <math.h>

// Project includes
#include "inputLatencyMeasureTool.h"
#include "joystickControl.h"
#include "wiringPi/wiringPi.h"
#include "stepper.h"
#include "fileLog.h"

enum INPUT_DEVICES inputDevice;

struct MenuIdRelName inputDeviceNames[3] = {
	{GAMEPAD, "Gamepad"},
	{MOUSE, "Mouse"},
	{KEYBOARD, "Keyboard"}
};

const int NUM_DEVICE_TYPES = 3;
const char* DEVICE_TYPES[3] = {
	"Gamepad",
	"Mouse",
	"Keyboard"
};

int g_iChannelCircId = -1;
int g_iButtonCode = 0; // ID of GP button which will be tested

int g_testIterations = MAX_ITERATIONS_AUTO_MODE;
int g_testDelay = AUTO_MODE_DELAY; // in microeconds

int g_iSPIFileDescriptor;

int *delayList;

int selectedDevice = 0;

int sm_steps = 1;
int sm_totalStepsUp = 0;
int sm_totalStepsDown = 0;

int sm_RPM = 960;

long long getCurTime_microseconds(int clk_id)
{
	struct timeval gettime_now;
	gettimeofday(&gettime_now, NULL);

	return (long long) gettime_now.tv_sec * 1000000l + (long long) gettime_now.tv_usec;
}

double timevalToSeconds(struct timeval *tv)
{
	return tv->tv_sec + (double)tv->tv_usec / 1000000l;
}

long long timevalToMicroSeconds(struct timeval *tv)
{
	return (long long) tv->tv_sec * 1000000l + (long long)tv->tv_usec;
}


/*
Sets up the wiringPi spi functions based on http://shaunsbennett.com/piblog/?p=266
*/
void setupSPI(int spiChannel)
{
	if ((g_iSPIFileDescriptor = wiringPiSPISetup(spiChannel, 1000000)) < 0)
	{
		fprintf(stderr, "Can't open the SPI bus: %s\n", strerror(errno));
		exit(EXIT_FAILURE);
	}
}

/*
 * Method:    Function for reading analog values from the adc via spi based on http://shaunsbennett.com/piblog/?p=266
 * Returns:   int Returns value between 0 and 1023 or -1 if unavailable analog channel was selected
 * Parameter: int channelConfig can be CHAN_CONFIG_SINGLE for single-ended or CHAN_CONFIG_DIFF for differential input
 * Parameter: int analogChannel can be a value between 0 and 7
 */
int readADC(int channelConfig, int analogChannel)
{
	if (analogChannel < 0 || analogChannel > 7)
		return -1;
	unsigned char buffer[3] = { 1 }; // start bit
	buffer[1] = (channelConfig + analogChannel) << 4;
	wiringPiSPIDataRW(SPI_CHANNEL, buffer, 3);
	return ((buffer[1] & 3) << 8) + buffer[2]; // get last 10 bits
}


void autoMode(struct AutoModeData *results, unsigned int iterations)
{
	long long dUSBEventTimestamp;
	long long dStartTime;
	long long diff;

	debug("starting auto mode\n");

	for (int i = 0; i < iterations; i++)
	{
		debug("iteration %d \n", i);
		digitalWrite(PIN_AUTO_MODE, LOW);
		

		while (1)
		{
			if(isButtonReleased(NULL)) break;
			usleep(10);
		}
		
		debug("pin clear\n");

        // maybe this helps to automatically start the measurement?
        //usleep(500000);

		// make sure we aren't synced
		usleep(delayList[i]);

		dStartTime = getCurTime_microseconds(CLOCK_REALTIME); 
		digitalWrite(PIN_AUTO_MODE, HIGH);

		while (1)
		{
			if(isButtonPressed(NULL))
			{
				dUSBEventTimestamp = getCurTime_microseconds(CLOCK_REALTIME);
				diff = (dUSBEventTimestamp - dStartTime); // double
				debug("-- %f s - %f s  = %f ms \n", dStartTime / 1000000.0, dUSBEventTimestamp / 1000000.0, diff / 1000.0); //print results
				printf("%d,%d,%f\n", i+1, iterations, diff/1000.0);

				struct AutoModeData data;
				data.counter = i;
				data.diff = diff;
				data.delayTime = delayList[i];

				results[i] = data;

				//digitalWrite(PIN_AUTO_MODE, LOW); //clear pin
				break;
			}

            // if there is no event within one second, cancel
            //if(getCurTime_microseconds(CLOCK_REALTIME) - dStartTime > 1000000)
            //{
            //    printf("cancelled");
            //    return;
            //}

			// maybe not ideal
			usleep(10);
		}

		// slepp for a time from delay list (i remember something about usleep being bad, i will investigate this soonTM)
		debug("delay: %d\n", delayList[i]);

		usleep(10);
	}

	digitalWrite(PIN_AUTO_MODE, LOW);
}

int checkButtonState(long long* timestamp)
{
	INPUT_EVENT ie;
	int err = -1;

	int lastState = -1;

	do
	{
		err = read(g_iInputFD, &ie, sizeof(INPUT_EVENT));

		if (ie.code == g_iButtonCode)
		{
			lastState = ie.value;

			if(timestamp)
			{
				*timestamp = timevalToMicroSeconds(&ie.time);
			}
		}
	} while(err != -1);

	return lastState;
}

int isButtonPressed(long long* timestamp)
{
	INPUT_EVENT ie;
	int err = -1;

	do
	{
		err = read(g_iInputFD, &ie, sizeof(INPUT_EVENT));

		if (ie.code == g_iButtonCode && ie.value == 1)
		{
			if(timestamp)
			{
				*timestamp = timevalToMicroSeconds(&ie.time);
			}
			return 1;
		}
	} while(err != -1);

	return 0;
}

int isButtonReleased(long long* timestamp)
{
	INPUT_EVENT ie;
	int err = -1;

	do
	{
		err = read(g_iInputFD, &ie, sizeof(INPUT_EVENT));

		if (ie.code == g_iButtonCode && ie.value == 0)
		{
			if(timestamp)
			{
				*timestamp = timevalToMicroSeconds(&ie.time);
			}
			return 1;
		}
	} while(err != -1);

	return 0;
}

/*
 * Method:    Starts main testing routine depending on the selected mode.
 * Returns:   void
 */
void start()
{
	switch(selectedDevice)
	{
		case 1:
			g_iInputFD = initJoystickControl();
			break;
		case 2:
			g_iInputFD = initMouseControl();
			break;
		case 3:
			g_iInputFD = initKeyboardControl();
			break;
		default:
			break;
	}

	if (g_iInputFD < 0)
	{
		debug("Error\n", "Device not found\n");
		return;
	}
	debug("Found device: %d\n", g_iInputFD);
	fflush(stdout);
}

void testPin(int pin)
{
	for(int i = 0; i < 1000; i++)
	{
		digitalWrite(pin, HIGH);
		usleep(1000000);
		digitalWrite(pin, LOW);
		usleep(1000000);
	}
}

void setupPins()
{
	debug("setting up pins...\n");
	pinMode(PIN_AUTO_MODE, OUTPUT);
	digitalWrite(PIN_AUTO_MODE, LOW);
}

void testStepper()
{
	// stepper stuff
	debug("this is the new shit!\n");
	debug("init stepper...\n");
	initializeStepper(200, 1, 4);
	debug("set rpm...\n");

	// 1200 skips steps
	// 960 is still ok
	setStepperRPM(960);

	debug("loop...\n");
	for(int i = 0; i < 100; i++)
	{
		debug("->\n");
		//moveStepper(200);
		rotateStepper(2400);
		//moveDistance(20.0f);
		usleep(100000);
		debug("<-\n");
		//moveStepper(-200);
		rotateStepper(-2400);
		//moveDistance(-20.0f);
		usleep(100000);
	}


	return;
}

// swap array elements
void swap(int list[], int a, int b)
{
	int temp = list[a];
	list[a] = list[b];
	list[b] = temp;
}

// https://en.wikipedia.org/wiki/Fisher%E2%80%93Yates_shuffle
void fisherYatesShuffle(int length, int list[length])
{
	for(int i = 0; i < length; i++)
	{
		swap(list, i, rand() % length);
	}
}

// create evenly distributed list of [length] delay times between [min] and [max] useconds
void createDelayList(int min, int max, int length)
{
	for(int i = 0; i < length; i++)
	{
		delayList[i] = min + (((max - min) / length) * i);
	}

	fisherYatesShuffle(length, delayList);
}

/*
 * ### WIP ###
 * move the stepper to the starting position and get the number of steps needed to press a button:
 * 1. slowly move down 'sm_steps' steps until a button press has been recognized
 * 2. move up until a button release has been recognized and count the steps needed (sm_totalSteps)
 */
void calibrateStepper()
{
	debug("calibrate stepper...\n");

	rotateStepper(200);

	const int CALIBRATION_COUNT = 10;
	int totalStepsUp = 0;
	int totalStepsDown = 0;
	int sumTotalStepsUp = 0; // sum of all steps in calibration
	int sumTotalStepsDown = 0;


	// move stepper to a reasonable position
	// move down fast until button is pressed
	while(1)
	{
		moveStepper(-sm_steps);

		if(isButtonPressed(NULL) == 1)
		{
			break;
		}
	}

	// move up fast until button is released
	while(1)
	{
		moveStepper(sm_steps);
		usleep(200000);

		if(isButtonReleased(NULL) == 1)
		{
			break;
		}
	}

	// start actual calibration
	for(int i = 0; i < CALIBRATION_COUNT; i++)
	{
		totalStepsDown = 0; // total steps to press/release a button
		totalStepsUp = 0;

		// move down step by step until button is pressed and count steps
		while(1)
		{
			moveStepper(-sm_steps);
			totalStepsDown += sm_steps;

			usleep(100000);

			if(isButtonPressed(NULL) == 1)
			{
				break;
			}

			
		}

		debug("totalSteps down: %d\n", totalStepsDown);
		sumTotalStepsDown += totalStepsDown;

		usleep(10000);

		// move up step by step until button is released and count steps
		while(1)
		{
			moveStepper(sm_steps);
			totalStepsUp += sm_steps;

			usleep(100000);

			if(isButtonReleased(NULL) == 1)
			{
				break;
			}

		}

		debug("totalSteps up: %d\n", totalStepsUp);
		sumTotalStepsUp += totalStepsUp;

		usleep(10000);
	}

	// divide sumTotalSteps by two, as we added press and release steps,
	// then divide it by the number of calibration iterations to get an average
	// and finally convert it to int as we can only move by whole steps
	sm_totalStepsDown = (int) ceil(sumTotalStepsDown / CALIBRATION_COUNT);
	sm_totalStepsUp = (int) ceil(sumTotalStepsUp / CALIBRATION_COUNT);

	debug("final totalSteps - down: %d, up: %d\n", sm_totalStepsDown, sm_totalStepsUp);
	
	return;
}

/*
 * measure the time the stepper needs to move a certain amount of steps
 * steps: number of steps to move
 * iterations: number of times to test
 * waitTime: delay time between tests in microseconds
 * result: array containing all measured time differences in microseconds
 */
void measureStepperLatency(int steps, int iterations, int waitTime, long long* result)
{
	debug("measureStepperLatency()\n");

	long long startTime;
	long long endTime;
	long long diff;

	if(steps == 0)
	{
		debug("steps too low (%d) - cancelling test\n", steps);
		return;
	}

	for(int i = 0; i < iterations; i++)
	{
		startTime = getCurTime_microseconds(CLOCK_REALTIME);
		moveStepper(-steps);
		endTime = getCurTime_microseconds(CLOCK_REALTIME);
		diff = endTime - startTime;

		result[i] = diff;

		usleep(waitTime);
		moveStepper(steps);

		usleep(waitTime);
	}

	debug("measureStepperLatency() - done\n");
}

int clearInputEvents()
{
	int lastState = -1;
	int curState = -1;

	while(1)
	{
		curState = checkButtonState(NULL);
		if(curState == -1) break;
		else if(curState == 0) lastState = 0;
		else if(curState == 1) lastState = 1;

		debug("clearing...\n");
		usleep(10);
	}

	return lastState;
}

/*
 * ### WIP ###
 * conducts the actual latency test
 * iterations: number of times to test
 * waitTime: delay time between tests in microseconds
 * result1: array containing all measured latencies from when the stepper started moving until it stopped moving
 * result2: array containing all measured latencies from when the stepper stopped moving until the usb event - ideally, these are our latencies
 */
void stepperMode(int iterations, int waitTime, struct StepperModeResult* result)
{
	debug("stepperMode()\n");

	long long startTime; // time before stepper starts moving
	long long movedTime; // time after stepper has moved
	long long endTime; // time of usb event
	long long diff1; // time it took the stepper to move
	long long diff2; // remaining time to the usb event
	long long diff3;

	int buttonState = -1;

	int stepsMoved = 0;

	int lastState = -1;

	long long *usbTime = (long long*) malloc(sizeof(long long));

	sm_totalStepsUp *= 2;
	sm_totalStepsDown *= 2;

	if(sm_totalStepsDown == 0 || sm_totalStepsUp == 0)
	{
		debug("totalSteps too low (down: %d, up: %d) - aborting test\n", sm_totalStepsDown, sm_totalStepsUp);
		return;
	}

	for(int i = 0; i < iterations; i++)
	{
		debug("iteration %d/%d\n", i + 1, iterations);

		lastState = clearInputEvents();

		while(lastState == 1)
		{
			debug("repositioning...\n");
			moveStepper(1);
			usleep(100000);
			
			if(checkButtonState(NULL) == 0) lastState = 0;
			else continue;
		}

		printf("d %d, u %d\n", sm_totalStepsDown, sm_totalStepsUp);

		stepsMoved = sm_totalStepsDown;
		startTime = getCurTime_microseconds(CLOCK_REALTIME);
		moveStepperAsync(-sm_totalStepsDown);
		movedTime = getCurTime_microseconds(CLOCK_REALTIME);
		while(1)
		{
			buttonState = checkButtonState(usbTime);
			if(buttonState == -1)
			{
				continue;
			}
			else if(buttonState == 0)
			{
				debug("!!! released (expecting pressed)\n");
				break;
			}
			else if(buttonState == 1)
			{
				endTime = getCurTime_microseconds(CLOCK_REALTIME);
				diff1 = movedTime - startTime;
				diff2 = endTime - movedTime;
				diff3 = *usbTime - startTime;

				struct StepperModeResult tempResult;
				tempResult.stepsMoved = stepsMoved;
				tempResult.startTime = startTime;
				tempResult.usbTime = *usbTime;
				tempResult.endTime = endTime;
				result[i] = tempResult;

				debug("moved: %lld, end: %lld, usb: %lld\n", diff1, diff2, diff3);
				break;
			}
		}
		usleep(waitTime);
		
		while(isButtonReleased(NULL) == 0)
		{
			moveStepper(sm_totalStepsUp);
			usleep(100000);
		}
		usleep(waitTime);
	}

	free(usbTime);

	debug("stepperMode() - done\n");
}

pthread_t startPressureMeasurement(struct PressureData* pressureData)
{
	pthread_t tid;
	
	pthread_create(&tid, NULL, pressureSensorThread, pressureData);

	return tid;
}

void* pressureSensorThread(void* args)
{
	struct PressureData* pressureData = (struct PressureData*)args;

	for(uint32_t i = 0; i < 1000000; i++)
	{
		struct PressureData p;
		p.timestamp = getCurTime_microseconds(CLOCK_REALTIME);
		p.pressure = readADC(CHAN_CONFIG_SINGLE, CHANNEL_FSR);
		pressureData[i] = p;
		usleep(100);
	}
}

void debug(const char* format, ...)
{
	return;
	va_list args;
	fprintf(stderr, "#");
	va_start(args, format);
	vfprintf(stderr, format, args);
	va_end(args);
}

int main(int argc, char *argv[])
{
	srand(time(NULL));

	wiringPiSetup();

	setupPins();

	setupSPI(SPI_CHANNEL);

    int minDelay = 10;//
    int maxDelay = 1000;//
    int mode = 0; //

    int steps = 0;
    int waitTime = 0;

    int direction = 1;

    struct TestParams params;

    int customDeviceNameSet = 0;
    char customDeviceName[256];

    g_ev = -1;

	if(argc % 2 == 1)
	{
		for(int i = 1; i < argc; i += 2)
		{
			if(strcmp(argv[i], "-m") == 0)
			{
				mode = atoi(argv[i+1]);
			}
			if(strcmp(argv[i], "-tmin") == 0)
			{
				minDelay = atoi(argv[i+1]);
			}
			if(strcmp(argv[i], "-tmax") == 0)
			{
				maxDelay = atoi(argv[i+1]);
			}
			if(strcmp(argv[i], "-n") == 0)
			{
				g_testIterations = atoi(argv[i+1]);
			}
			if(strcmp(argv[i], "-b") == 0)
			{
				g_iButtonCode = atoi(argv[i+1]);
			}
			if(strcmp(argv[i], "-d") == 0)
			{
				selectedDevice = atoi(argv[i+1]);
			}
			if(strcmp(argv[i], "-steps") == 0)
			{
				steps = atoi(argv[i+1]);
			}
			if(strcmp(argv[i], "-delay") == 0)
			{
				waitTime = atoi(argv[i+1]);
			}
			if(strcmp(argv[i], "-dir") == 0)
			{
				direction = atoi(argv[i+1]);
			}
			if(strcmp(argv[i], "-event") == 0)
			{
				g_ev = atoi(argv[i+1]);
			}
			if(strcmp(argv[i], "-name") == 0)
			{
				customDeviceNameSet = 1;
				strcpy(customDeviceName, argv[i+1]);
			}
		}
	}
	else
	{
		debug("Invalid number of arguments!\n");
		debug("Cancelling...\n");
		return 0;
	}
	
	debug("+----------------------------------+\n");
	debug("| arguments:                       |\n");
	debug("+-----------------------+----------+\n");
	debug("| mode                  | %d\n", mode);
	debug("| tmin                  | %d\n", minDelay);
	debug("| tmax                  | %d\n", maxDelay);
	debug("| test iterations       | %d\n", g_testIterations);
	debug("| button code           | %d\n", g_iButtonCode);
	debug("| selected device       | %d\n", selectedDevice);
	debug("| steps                 | %d\n", steps);
	debug("| wait time             | %d\n", waitTime);
	debug("+----------------------------------+\n");

	if(minDelay == 0 || maxDelay == 0 || g_testIterations == 0)
	{
		debug("Invalid params!\n");
		debug("Cancelling...\n");
		return 0;
	}

	if(mode != 1 && mode != 2 && mode != 4)
	{
		if(selectedDevice == 0)
		{
			debug("Select testing device type:\n");

			for(int i = 0; i < NUM_DEVICE_TYPES; i++)
			{
				debug("[%d] %s \n", (i + 1), inputDeviceNames[i].szName);
			}
			scanf("%d", &selectedDevice);
		}

		if(inputDeviceNames[selectedDevice - 1].szName == NULL)
		{
			debug("Error! No valid device selected!\n");
			return 0;
		}

		debug("%s selected\n", inputDeviceNames[selectedDevice - 1].szName);
		inputDevice = inputDeviceNames[selectedDevice - 1].id;
	}

	/*
	 * run the selected mode:
	 * 0 - stepper mode
	 * 1 - stepper latency test
	 * 2 - reset stepper
	 * 3 - automode
	 * 4 - pressure sensor test mode
	 */
	switch(mode)
	{
		case 0:
			// stepper mode: use a stepper motor to physically push a button

			debug("### stepper mode ###\n");

			if(g_testIterations == 0)
			{
				debug("invalid number of test iterations (%d) [has to be at least 1] - aborting\n", g_testIterations);
				return 0;
			}

			start();
			initializeStepper(200, 6, 5);
			setStepperRPM(sm_RPM);

			// set test params to for logging
			params.mode = 0;
			params.iterations = g_testIterations;
			params.buttonCode = g_iButtonCode;
			if(customDeviceNameSet) sprintf(params.device, "%s", customDeviceName);
			else sprintf(params.device, "%s", g_szDeviceName);
			params.waitTime = waitTime;

			calibrateStepper();

			struct StepperModeResult *sm_result = (void*) malloc(g_testIterations * sizeof(struct StepperModeResult));

			struct PressureData* pressureData = (void*)malloc(10000000 * sizeof(struct PressureData));
			pthread_t pressureThread = startPressureMeasurement(pressureData);

			stepperMode(g_testIterations, waitTime, sm_result);

			pthread_cancel(pressureThread);

			logStepperModeData(params, sm_result, g_testIterations);
			logPressureData(params, pressureData, 10000000);

			debug("%d latencies in microseconds:\n", g_testIterations);
			for(int i = 0; i < g_testIterations; i++)
			{
				printf("%d, %lld, %lld, %lld\n", sm_result[i].stepsMoved, sm_result[i].startTime, sm_result[i].endTime, sm_result[i].usbTime);
			}

			free(pressureData);
			free(sm_result);
			break;
		case 1:
			// stepper latency test mode: test how long the stepper takes to move n steps
			debug("### stepper latency test mode ###\n");

			if(g_testIterations == 0)
			{
				debug("invalid number of test iterations (%d) [has to be at least 1] - aborting\n", g_testIterations);
				return 0;
			}
			if(steps < 2)
			{
				debug("invalid number of steps (%d) [has to be at least 2] - aborting\n", steps);
				return 0;
			}

			start();
			initializeStepper(200, 6, 5);
			setStepperRPM(sm_RPM);
			long long *sl_result = (void*) malloc(g_testIterations * sizeof(long long));

			params.mode = 1;
			params.iterations = g_testIterations;
			params.waitTime = waitTime;
			params.steps = steps;

			measureStepperLatency(steps, g_testIterations, waitTime, sl_result);

			debug("%d stepper latencies in microseconds:\n", g_testIterations);
			for(int i = 0; i < g_testIterations; i++)
			{
				printf("%lld\n", sl_result[i]);
			}

			free(sl_result);
			break;
		case 2:
			// reset stepper mode: stepper will go upwards until you cancel the program
			debug("### reset stepper mode ###\n");
			start();
			initializeStepper(200, 6, 5);
			setStepperRPM(sm_RPM);

			while(1)
			{
				rotateStepper(10 * direction);
			}
			break;
		case 3:
			// auto mode: short a button on the input device via a optocoupler connected to a GPIO-pin
			// we used this mode for LagBox 1.0

			debug("### auto mode ###\n");

			// create an evenly distributed list of delays within a given range with random order
			delayList = (void*) malloc(g_testIterations * sizeof(int));
			createDelayList(minDelay, maxDelay, g_testIterations);

			struct AutoModeData* resultData = (void*) malloc(g_testIterations * sizeof(struct AutoModeData));

			start();

			params.mode = 3;
			params.iterations = g_testIterations;
			params.minDelay = minDelay;
			params.maxDelay = maxDelay;
			if(customDeviceNameSet) sprintf(params.device, "%s", customDeviceName);
			else sprintf(params.device, "%s", g_szDeviceName);
			params.buttonCode = g_iButtonCode;

			autoMode(resultData, g_testIterations);

			logAutoModeData(params, resultData, g_testIterations);

            printf("%s\n", params.device);
            printf("done\n");

			free(resultData);
			free(delayList);

			break;
		case 4:
			// pressure sensor test mode
			debug("### pressure sensor test mode ###\n");

			struct PressureData* pData = (void*)malloc(1000000 * sizeof(struct PressureData));

			start();
			initializeStepper(200, 6, 5);
			setStepperRPM(sm_RPM);
			
			printf("starting thread\n");

			pthread_t pThread = startPressureMeasurement(pData);


			for(int i = 0; i < g_testIterations;i++ ) {
				rotateStepper(10*direction);
			}

			//while(1)
			//{
			//	rotateStepper(10 * direction);
			//}

			printf("ending thread\n");

			pthread_cancel(pThread);

			printf("output...\n");

			for(uint32_t i = 0; i < 1000000; i++)
			{
				if(pData[i].timestamp == 0) break;
				printf("%d - %lld - %d\n", i, pData[i].timestamp, pData[i].pressure);
				// csv output here
			}

			free(pData);

			printf("ending...\n");

			break;
	}

	debug("Tool finished\n");
	return 0;
}
