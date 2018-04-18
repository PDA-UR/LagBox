#include "joystickControl.h"

int g_iInputFD = 0;
int g_iNumAxes = 0;
int g_iNumButtons = 0;
char g_szDeviceName[80];
int g_ev;

int initJoystickControl()
{
	long testTypes[3] = { EV_SYN, EV_KEY, EV_ABS };
	if (findCorrectInputDevice(&g_iInputFD, testTypes, 3) == -1)
	{
		printf("ERROR >> Couldn't find matching device\n");
		return -1;
	}

	return g_iInputFD;
}

void retrieveGlobalJoystickData()
{
	ioctl(g_iInputFD, JSIOCGAXES, &g_iNumAxes);
	ioctl(g_iInputFD, JSIOCGBUTTONS, &g_iNumButtons);
	ioctl(g_iInputFD, JSIOCGNAME(80), &g_szDeviceName);
}

/*SOURCE: http://elinux.org/images/9/93/Evtest.c */
#define BITS_PER_LONG (sizeof(long) * 8)
#define NBITS(x) ((((x)-1)/BITS_PER_LONG)+1)
#define OFF(x)  ((x)%BITS_PER_LONG)
#define BIT(x)  (1UL<<OFF(x))
#define LONG(x) ((x)/BITS_PER_LONG)
#define test_bit(bit, array)	((array[LONG(bit)] >> OFF(bit)) & 1)

unsigned long bits[EV_MAX][NBITS(KEY_MAX)];

int findCorrectInputDevice(int *piFD, long *testTypes, int nTestTypes)
{
	int eventHandleId = 0;
	if(g_ev > -1) eventHandleId = g_ev;

	while (1)
	{
		char szFullEventUrl[32];
		sprintf(szFullEventUrl, EVENT_URL, eventHandleId);
		printf("Checking event: %s\n", szFullEventUrl);
		if (openKernelConnection(piFD, szFullEventUrl) == -1)
		{
			return -1;
		}

		ioctl(*piFD, EVIOCGNAME(80), &g_szDeviceName);
		printf("Device Name: %s\n", g_szDeviceName);

		memset(bits, 0, sizeof(bits));
		ioctl(*piFD, EVIOCGBIT(0, EV_MAX), bits[0]);

		char failed = 0;
		for (int i = 0; i < nTestTypes; i++)
		{
			if (!test_bit(testTypes[i], bits[0]))
			{
				failed = 1;
				break;
			}
		}
		if (!failed)
		{
			break;
		}
		eventHandleId++;
	}

	return *piFD;
}

int initMouseControl()
{
	long testTypes[3] = { EV_SYN, EV_KEY, EV_REL };
	if (findCorrectInputDevice(&g_iInputFD, testTypes, 3) == -1)
	{
		printf("ERROR >> Couldn't find matching device-types\n");
		return -1;
	}
	ioctl(g_iInputFD, EVIOCGBIT(EV_KEY, KEY_MAX), bits[EV_KEY]);
	if (!test_bit(BTN_LEFT, bits[EV_KEY]))
	{
		printf("ERROR >> Couldn't find left-click button on mouse\n");
		return -1;
	}
	return g_iInputFD;
}

int initKeyboardControl()
{
	long testTypes[3] = { EV_SYN, EV_KEY, EV_REP };
	if (findCorrectInputDevice(&g_iInputFD, testTypes, 3) == -1)
	{
		printf("ERROR >> Couldn't find matching device\n");
		return -1;
	}
	return g_iInputFD;
}

int openKernelConnection(int *piFD, char *pszSource)
{
	*piFD = open(pszSource, O_RDONLY | O_NONBLOCK);
	//printf("piFD %d\n", *piFD);
	if (*piFD < 0)
	{
		printf("ERROR >> Failed to open device\n");
		return -1;
	}

	return *piFD;
}