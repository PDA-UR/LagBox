#include <pthread.h>
#include "stepper.h"
#include "wiringPi/wiringPi.h"

/*
 * small API for the drv8834 stepper motor controller
 */

int PIN_DIR;
int PIN_STEP;
int STEPS = 200;	// steps per revolution
int RPM = 60;
float DISTANCE_PER_STEP = 0.01f; // in mm

void initializeStepper(int steps, int pinDir, int pinStep)
{
	PIN_DIR = pinDir;
	PIN_STEP = pinStep;
	STEPS = steps;

	//printf("initializing stepper...\n");

	pinMode(PIN_DIR, OUTPUT);
	pinMode(PIN_STEP, OUTPUT);

	digitalWrite(PIN_DIR, HIGH);
	digitalWrite(PIN_STEP, LOW);

	//printf("done!\n");

	// NOTE: might need enable() here - set nEnable low
}

void setStepperRPM(int rpm)
{
	RPM = rpm;
}

void rotateStepper(int degrees)
{
	// positive is up, negative is down
	moveStepper(degrees * (STEPS / 360.0f));
}

// TODO measure exact distances
void moveDistance(float distance) // in mm
{
	//moveStepper(STEPS * distance * DISTANCE_PER_STEP * 40);
}

void moveStepper(int steps)
{
	steps *= 4; // seems to be necessary, maybe because of microstepping shenanigans
	int stepsRemaining = abs(steps);
	int direction = steps > 0;

	digitalWrite(PIN_DIR, direction);

	int waitTime = calculateWaitTime();

	while(stepsRemaining > 0)
	{
		digitalWrite(PIN_STEP, HIGH);
		usleep(1);
		digitalWrite(PIN_STEP, LOW);
		if(stepsRemaining > 1) usleep(waitTime - 1);
		stepsRemaining--;
	}
}

void moveStepperAsync(int steps)
{
	pthread_t tid;
	pthread_create(&tid, NULL, moveStepperThread, (void*)steps);
}

void* moveStepperThread(void* args)
{
	int *stepsptr = (int*)args;
	int steps = stepsptr;

	steps *= 4; // seems to be necessary, maybe because of microstepping shenanigans
	int stepsRemaining = abs(steps);
	int direction = steps > 0;

	digitalWrite(PIN_DIR, direction);

	int waitTime = calculateWaitTime();

	while(stepsRemaining > 0)
	{
		digitalWrite(PIN_STEP, HIGH);
		usleep(1);
		digitalWrite(PIN_STEP, LOW);
		if(stepsRemaining > 1) usleep(waitTime - 1);
		stepsRemaining--;
	}
}

// wait time between steps in microseconds
static int calculateWaitTime()
{
	// found in drv8834 arduino library
	int waitTime = 60 * 1000000L / STEPS / RPM;

	return (int)waitTime;
}