#ifndef mathTools_h__
#define mathTools_h__

#include "inputLatencyMeasureTool.h"

// Number of values stored to calculate the average
#define SMOOTHING_READINGS_SIZE 6

/*
 * Method:    Smooths input values from FSR for a better detection 
 *				of minimum in the force graph based on https://www.arduino.cc/en/Tutorial/Smoothing
 * Returns:   int
 * Parameter: int iPressure
 */
int smoothing(int iNewValue);

/*
 * Method:    Sets all global data the smoothing function is working with to zero.
 * Returns:   void
 */
void resetSmoothingData();

/*
 * Method:    Iterates through an array with size numValues and stores the corresponding
 *				smoothed values in the smoothedValues array.
 * Returns:   void
 * Parameter: int numValues - Number of entries of the the following two arrays
 * Parameter: int * smoothedValues - (empty) Array, must be allocated (size: numValues)
 * Parameter: int * pressureValues - Raw Values Array (size: numValues)
 */
void doSmoothing(int numValues, int * smoothedValues, int * pressureValues);


/*
 * Method:    Smoothed graphs are a bit ahead of time. This method searches
 *				the real local minimum in the data.
 * Returns:   int - index of pLogData->iterationTime array
 * Parameter: int nextMinimumIndex - index calculated by findSmoothedMinimum
 * Parameter: int * smoothedValues - array from doSmoothing
 * Parameter: struct LogData * pLogData
 */
int findRawDatMinimum(int nextMinimumIndex, int * smoothedValues, struct LogData *pLogData);


/*
 * Method:    This method calculates the Slope Values: s(i) = d(i) - d(i-1)
 * Returns:   void
 * Parameter: int * data - array with length 'size' and stored values
 * Parameter: int size - length of data array
 * Parameter: int * output - array of length 'size'. Empty but already allocated
 */
void calculateSlopes(int *data, int size, int *output);


/*
 * Method:    Finds local minimum in noisy data
 * Returns:   int - index of pLogData->iterationTime array
 * Parameter: struct LogData * pLogData
 * Parameter: int * slopeValues - slope values calculated 
 *				with calculateSlopes (smoothed values as input preferred)
 */
int findSmoothedMinimum(struct LogData * pLogData, int * slopeValues);

/*
 * Method:    calculates Extrema, Average out of a set of data
 * Returns:   void
 * Parameter: double * min - minimum
 * Parameter: double * max - maximum
 * Parameter: double * avg - average
 * Parameter: double * data - data <- has to have MAX_ITERATIONS_AUTO_MODE length
 */
void calculateAutoModeData(double *min, double *max, double *avg, double *data);

#endif // mathTools_h__


