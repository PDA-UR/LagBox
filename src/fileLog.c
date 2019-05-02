#include "fileLog.h"
#include "sys/stat.h"
#include <time.h>

FILE *logFile_automode;
FILE *logFile_stepper;
FILE *logFile_pressure;

int getPollingRate()
{
	FILE * cmdlinetxt;
	int pollingRate;

   	cmdlinetxt = fopen ("/boot/cmdline.txt", "r");

   	fscanf(cmdlinetxt, "%*s %*s usbhid.mousepoll=%d %*s %*s %*s %*s %*s", &pollingRate);
   	
   	fclose(cmdlinetxt);

   	printf("mousepoll: %d\n", pollingRate);
   	
   	return(pollingRate);
}

void logResults(struct latencies *l)
{
	fprintf(logFile_automode, "#Electrical lag after = %f ms\n", l->dDiffStartToEl);
	fprintf(logFile_automode, "#Electrical - OS lag = %f ms\n", l->dDiffElToOs);
	fprintf(logFile_automode, "#Electrical - OS lag by Algorithm = %f ms\n", l->dDiffElToOsAlgo);
	fprintf(logFile_automode, "#Overall lag = %f ms\n", l->dDiffOverall);
	fprintf(logFile_automode, "#Device: %s\n", g_szDeviceName);
}

void writeFileHeader(FILE *file, struct TestParams params)
{
	fprintf(logFile, "#Device:;%s\n", filteredName);
	fprintf(logFile, "#Button:;%d\n", params.buttonCode);
	fprintf(logFile, "#minDelay:;%d\n", params.minDelay);
	fprintf(logFile, "#maxDelay:;%d\n", params.maxDelay);
	fprintf(logFile, "#iterations:;%d\n", params.iterations);
    
    fprintf(logFile, "#author:;\n");
    fprintf(logFile, "#vendorId:;\n");
    fprintf(logFile, "#productId:;\n");
    fprintf(logFile, "#date:;\n");
    fprintf(logFile, "#bInterval:;\n");
    fprintf(logFile, "#deviceType:;\n");
    fprintf(logFile, "#email:;\n");
    fprintf(logFile, "#public:;\n");
}

void replaceForbiddenChars(char *newString, char * pszFileName)
{
	int length = strlen(pszFileName);
	memcpy(newString, pszFileName, length);
	newString[length] = 0;
	char *pos = NULL;
	char forbiddenChars[] = {'/', ';', ' ', '	', '.', ':'};

	for(int i = 0; i < sizeof(forbiddenChars); i++)
	{
		do
		{
			pos = strchr(newString, forbiddenChars[i]);
			if (pos != NULL)
			{
				*pos = '_';
			}
		} while (pos != NULL);
	}
}

void logPressureData(struct TestParams params, struct PressureData *data, unsigned int length)
{
	char filteredName[256];

	replaceForbiddenChars(filteredName, params.device);

	FILE *logFile = openLogFile(filteredName, STR_PRESSURE);

	fprintf(logFile, "#Mode:;%d\n", params.mode);
	fprintf(logFile, "#Device:;%s\n", filteredName);
	fprintf(logFile, "#Button:;%d\n", params.buttonCode);
	fprintf(logFile, "#iterations:;%d\n", params.iterations);
	fprintf(logFile, "#waitTime:;%d\n", params.waitTime);

	fprintf(logFile, "\n");
	fprintf(logFile, "counter;timestamp;pressure\n");

	for(int i = 0; i < length; i++)
	{
		if(data[i].timestamp == 0) break;
		fprintf(logFile, "%d;%lld;%d\n", i, data[i].timestamp, data[i].pressure);
	}

	closeLogFile(logFile);
}

void logStepperLatencyData(struct TestParams params, long long* result, unsigned int length)
{
	// TODO
}

void logStepperModeData(struct TestParams params, struct StepperModeResult *data, unsigned int length)
{
	char filteredName[256];

	replaceForbiddenChars(filteredName, params.device);

	FILE *logFile = openLogFile(filteredName, STR_STEPPERMODE);

	fprintf(logFile, "#Mode:;%d\n", params.mode);
	fprintf(logFile, "#Device:;%s\n", filteredName);
	fprintf(logFile, "#Button:;%d\n", params.buttonCode);
	fprintf(logFile, "#iterations:;%d\n", params.iterations);
	fprintf(logFile, "#waitTime:;%d\n", params.waitTime);

	fprintf(logFile, "\n");
	fprintf(logFile, "steps;startTime;endTime;usbTime\n");

	for(int i = 0; i < length; i++)
	{
		fprintf(logFile, "%d;%lld;%lld;%lld\n", data[i].stepsMoved, data[i].startTime, data[i].endTime, data[i].usbTime);
	}

	closeLogFile(logFile);
}

void logAutoModeData(struct TestParams params, struct AutoModeData *data, unsigned int length)
{
	char filteredName[256];

	replaceForbiddenChars(filteredName, params.device);

	FILE *logFile = openLogFile(filteredName, STR_AUTOMODE);

    writeFileHeader(logFile, params);

	fprintf(logFile, "\n");
	fprintf(logFile, "counter;latency;delayTime\n");

	for(int i = 0; i < length; i++)
	{
		fprintf(logFile, "%d;%lld;%d\n", data[i].counter, data[i].diff, data[i].delayTime);
	}

	closeLogFile(logFile);
}

FILE *openLogFile(char *pszFileName, char *mode)
{
	char filteredName[256];
	replaceForbiddenChars(filteredName, pszFileName);

	time_t t;
	time(&t);

	char path[256];
	// http://stackoverflow.com/a/7430262 folder creation
	struct stat st_directory = {0};
	struct stat st_logfile = {0};

	int logfileNumber = 1;

	int pollingRate = getPollingRate();

	FILE *logFile;

	if (stat("../log", &st_directory) == -1)
	{
		mkdir("../log", 0777);
	}

	sprintf(path, "../log/%s_%s_%dms_%d.csv", mode, filteredName, pollingRate, logfileNumber);

	while(stat(path, &st_logfile) != -1)
	{
		logfileNumber++;
		sprintf(path, "../log/%s_%s_%dms_%d.csv", mode, filteredName, pollingRate, logfileNumber);
	}

	logFile = fopen(path, "w+");
	if (logFile == NULL)
	{
		printf("Error opening log file\n");
		return;
	}
}

void closeLogFile(FILE *file)
{
	if (fclose(file) == EOF)
	{
		printf("Error closing log file\n");
	}
}
