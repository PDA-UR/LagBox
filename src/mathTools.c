#include "mathTools.h"

int g_iReadings[SMOOTHING_READINGS_SIZE];
int g_iIndex = 0;
int g_iTotal = 0;
int g_numValuesAbs = 0;

int smoothing(int iNewValue)
{
	g_iTotal -= g_iReadings[g_iIndex];
	g_iReadings[g_iIndex] = iNewValue;
	g_iTotal += g_iReadings[g_iIndex];
	g_iIndex++;
	if (g_iIndex >= SMOOTHING_READINGS_SIZE)
	{
		g_iIndex = 0;
	}
	int iAverage = g_iTotal / SMOOTHING_READINGS_SIZE;
	if (g_numValuesAbs++ < SMOOTHING_READINGS_SIZE)
	{
// 		printf("iTotal: %d, iIndex: %d, iNewValue: %d\n", g_iTotal, g_iIndex, iNewValue);
// 		for (int i = 0; i < SMOOTHING_READINGS_SIZE; i++)
// 		{
// 			printf("IREadings %d: %d\n", i, g_iReadings[i]);
// 		}
		return g_iTotal / g_numValuesAbs;
	}
	return iAverage;
}

void resetSmoothingData()
{
	for (int i = 0; i < SMOOTHING_READINGS_SIZE; i++)
	{
		g_iReadings[i] = 0;
	}
	g_iIndex = 0;
	g_iTotal = 0;
	g_numValuesAbs = 0;
}

void calculateSlopes(int *data, int size, int *output)
{
	output[0] = 0;
	for (int i = 1; i < size; i++)
	{
		output[i] = data[i] - data[i - 1];
	}
}

int findRawDatMinimum(int nextMinimumIndex, int * smoothedValues, struct LogData *pLogData)
{
	double deltaTimeToPast = 1.0f;/*(timeValues[usbregIndex] - timeValues[nextMinimumIndex]) * 0.3f;*/

	int curIndex = nextMinimumIndex;
	int minimumIndexRaw = -1;
	int minRawValueSoFar = smoothedValues[nextMinimumIndex];
	while (pLogData->iterationTimeBuff[nextMinimumIndex] - pLogData->iterationTimeBuff[curIndex] < deltaTimeToPast && --curIndex >= 0)
	{
		if (pLogData->pressureValues[curIndex] < minRawValueSoFar)
		{
			minimumIndexRaw = curIndex;
			minRawValueSoFar = pLogData->pressureValues[curIndex];
		}
	}
	if (minimumIndexRaw < 0)
	{
		return nextMinimumIndex;
	}
	return minimumIndexRaw;
}

void doSmoothing(int numValues, int * smoothedValues, int * pressureValues)
{
	for (int i = 0; i < numValues; i++)
	{
		//printf("Time: %lf | PV: %d\n", timeValues[i], pressureValues[i]);
		smoothedValues[i] = smoothing(pressureValues[i]);

	}
}

int findSmoothedMinimum(struct LogData *pLogData, int *slopeValues)
{
	int curIndex = pLogData->indexUSBEventReg;
	int nextMinimumIndex = -1;
	while (pLogData->iterationTimeBuff[pLogData->indexUSBEventReg] - pLogData->iterationTimeBuff[curIndex] < 35.0f && nextMinimumIndex < 0 && --curIndex >= 0) // max. 35ms in the past
	{
		// Some devices actually have latencies below 1 ms
// 		if (pLogData->iterationTimeBuff[pLogData->indexUSBEventReg] - pLogData->iterationTimeBuff[curIndex] < 0.5f)
// 		{
// 			continue;
// 		}

		if (slopeValues[curIndex] < 0)
		{
			if (curIndex - 1 >= 0 && slopeValues[curIndex - 1] <= -1)
			{
				int sumSlopes = 0;
				for (int i = 0; i < 20; i++) // ~1,5ms
				{
					sumSlopes += slopeValues[curIndex - i];
				}
				if (sumSlopes <= -16) {
					nextMinimumIndex = curIndex;
				}
				else
				{
					continue;
				}
				break;
			}
		}
	}
	return nextMinimumIndex;
}

void calculateAutoModeData(double *min, double *max, double *avg, double *data)
{
	*min = data[0];
	*max = data[0];
	*avg = 0;
	for (int i = 0; i < MAX_ITERATIONS_AUTO_MODE; i++)
	{
		*avg += data[i];
		if (data[i] < *min)
		{
			*min = data[i];
		}
		if (data[i] > *max)
		{
			*max = data[i];
		}
	}
	*avg = *avg / MAX_ITERATIONS_AUTO_MODE;
}
