#ifndef fileLog_h__
#define fileLog_h__

#include <stdio.h>

#include "joystickControl.h"
#include "inputLatencyMeasureTool.h"

#define STR_AUTOMODE "AUTO"

extern FILE *g_pLogFile;

/*
 * Method:    Writes data of latencies struct to the file (g_pLogFile)
 * Returns:   void
 * Parameter: struct latencies * l - Data to write
 */
void logResults(struct latencies *l);

void writeFileHeader(FILE *file, struct TestParams params);

/*
 * Method:    Opens File in LAB_MODE folder
 *				Filename: pszFileName_day-month-year_hour-min-sec
 * Returns:   void
 * Parameter: char * pszFileName
 */
FILE *openLogFile(char *pszFileName, char *mode);

void logAutoModeData(struct TestParams params, struct AutoModeData *data, unsigned int length);

/*
 * Method:    closeLogFile
 * Returns:   void
 */
void closeLogFile(FILE *file);

/*
 * Method:    Writes a new line to AUTO_MODE log file
 * Returns:   void
 * Parameter: char * fileName - file to write to
 * Parameter: double diff - data to write
 * Parameter: int writeHeader - writes the header for collumns
 */
void addTimeDiffToLogFile(char *fileName, int counter, double diff, int delayTime);

/*
 * Method:    Writes data of pLogData to file
 * Returns:   void
 * Parameter: LATENCIES * results
 * Parameter: struct LogData * pLogData
 */
void logDataToFile(LATENCIES *results, struct LogData * pLogData);
#endif // fileLog_h__


