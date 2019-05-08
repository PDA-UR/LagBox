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
#include <wiringPi.h>
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

    int minDelay = 100;//
    int maxDelay = 10000;//
    int mode = 0; //

    int waitTime = 0;

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
			if(strcmp(argv[i], "-delay") == 0)
			{
				waitTime = atoi(argv[i+1]);
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
	 * 3 - automode
	 */
	switch(mode)
	{
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
	}

	debug("Tool finished\n");
	return 0;
}
