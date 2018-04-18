#ifndef inputLatencyMeasureTool_h__
#define inputLatencyMeasureTool_h__

#include <pthread.h>

// Defines
// MCP Params
#define CHAN_CONFIG_SINGLE  8
#define CHAN_CONFIG_DIFF    0

#define MAX_ITERATIONS_AUTO_MODE 100
#define AUTO_MODE_DELAY 200000 // in microseconds

//constants used for running the mcp3008 via SPI
#define CHANNEL_FSR 7
#define CHANNEL_CIRC 1
#define CHANNEL_CIRC2 2
#define CHANNEL_BUTTON_SELECT 3
#define CHANNEL_BUTTON_RIGHT 4
#define SPI_CHANNEL 0

#define PIN_AUTO_MODE 11 //pin used for auto-mode
#define POLARITY_THRESHOLD 500 //Threshold for checking the logic of a game-pad

#define	AF_BASE		100

enum MODES
{
	FAST_MODE,
	LAB_MODE,
	AUTO_MODE
};

enum INPUT_DEVICES
{
	GAMEPAD,
	MOUSE,
	KEYBOARD
};

#define MAX_LOG_DATA 4096


struct MenuIdRelName
{
	int id;
	char *szName;
};

struct AutoModeData
{
	int counter;
	long long diff;
	int delayTime;
};

struct StepperModeResult
{
	int stepsMoved;
	long long startTime;
	long long endTime;
	long long usbTime;
};

struct PressureData
{
	long long timestamp;
	unsigned int pressure;
};

struct TestParams
{
	int mode;
	int minDelay;
    int maxDelay;
    int iterations;
    int buttonCode;
    char device[256];
    int steps;
    int waitTime;
};

struct LogData
{
	// Index when Button was pressed electrically
	int indexBtnContact;
	// Index when Button was pressed electrically decided by pressure values
	int indexBtnContactAlgo;
	// Index when Raspberry detected the event
	int indexUSBEventReg;
	// Index for smoothed Data Minimum (real minimum at indexBtnContact)
	int timeSmoothedMinimum;

	// Absolute time when Button was pressed
	double timeBtnContact;
	// Absolute time when measurement started (fsr value > threshold)
	double timeStart;
	// Absolute timestamp when event was detected in kernel
	double timeUSBEventReg;

	// Number of valid values in the following arrays
	int numValues;

	// Pressure values
	int *pressureValues;
	// Delta Time since timeStart
	double *iterationTimeBuff;
	// Smoothed pressure values
	int *smoothedPressureValues;
};

struct latencies
{
	double dDiffStartToEl;
	double dDiffElToOs;
	double dDiffElToOsAlgo;
	double dDiffOverall;
};

typedef struct latencies LATENCIES;


long long getCurTime_microseconds(int clk_id);

double timevalToSeconds(struct timeval *tv);

long long timevalToMicroSeconds(struct timeval *tv);

void setupSPI(int spiChannel);

int readADC(int channelConfig, int analogChannel);

void autoMode(struct AutoModeData *results, unsigned int iterations);

int checkButtonState(long long* timestamp);

int isButtonPressed(long long* timestamp);

int isButtonReleased(long long* timestamp);

void start();

void testPin(int pin);

void setupPins();

void testStepper();

void swap(int list[], int a, int b);

void fisherYatesShuffle(int length, int list[length]);

void createDelayList(int min, int max, int length);

void calibrateStepper();

void measureStepperLatency(int steps, int iterations, int waitTime, long long* result);

int clearInputEvents();

void stepperMode(int iterations, int waitTime, struct StepperModeResult* result);

pthread_t startPressureMeasurement(struct PressureData* pressureData);

void* pressureSensorThread(void* args);

void debug(const char* format, ...);

int main(int argc, char *argv[]);

extern int g_bRestartProgram;
#endif // inputLatencyMeasureTool_h__
