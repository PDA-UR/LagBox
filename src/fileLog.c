#include "fileLog.h"
#include "sys/stat.h"
#include <time.h>

FILE *logFile_automode;

int getPollingRate()
{
	FILE * cmdlinetxt;
	int pollingRate;

   	cmdlinetxt = fopen ("/boot/cmdline.txt", "r");

   	fscanf(cmdlinetxt, "%*s %*s usbhid.mousepoll=%d %*s %*s %*s %*s %*s", &pollingRate);
   	
   	fclose(cmdlinetxt);

   	//printf("mousepoll: %d\n", pollingRate);
   	
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
	fprintf(file, "#Device:;%s\n", params.device);
	fprintf(file, "#Button:;%d\n", params.buttonCode);
	fprintf(file, "#minDelay:;%d\n", params.minDelay);
	fprintf(file, "#maxDelay:;%d\n", params.maxDelay);
	fprintf(file, "#iterations:;%d\n", params.iterations);
    
    fprintf(file, "#author:;\n");
    fprintf(file, "#vendorId:;\n");
    fprintf(file, "#productId:;\n");
    fprintf(file, "#date:;\n");
    fprintf(file, "#bInterval:;\n");
    fprintf(file, "#deviceType:;\n");
    fprintf(file, "#email:;\n");
    fprintf(file, "#public:;\n");
    fprintf(file, "#notes:;\n");
    fprintf(file, "#EAN:;\n");
    fprintf(file, "#deviceSpeed:;\n");
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

void logAutoModeData(struct TestParams params, struct AutoModeData *data, unsigned int length)
{
	char filteredName[256];

	replaceForbiddenChars(filteredName, params.device);

    memcpy(params.device, filteredName, strlen(filteredName));

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

    printf("%s\n", path);

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
