#ifndef joystickControl_h__
#define joystickControl_h__

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <linux/joystick.h>
#include <linux/input.h>

#define JOY_DEV0 "/dev/input/js0"
#define EVENT_URL "/dev/input/event%d"

// Input file descriptor
extern int g_iInputFD;

// Joystick only - Number of axes
extern int g_iNumAxes;

// Joystick only - Number of buttons
extern int g_iNumButtons;

// Name of input device
extern char g_szDeviceName[80];


extern int g_ev;


/*Shortcut TYPEDEFS*/
typedef struct js_event JS_EVENT;
typedef struct input_event INPUT_EVENT;


/*
 * Method:    Only for Game pads - sets g_iNumAxes, g_iNumButtons and g_szDeviceName
 * Returns:   void
 */
void retrieveGlobalJoystickData();

int findCorrectInputDevice(int *piFD, long *testTypes, int nTestTypes);

/*
 * Method:    Loads the joystick event driver file
 *				and directly calls retrieveGlobalJoystickData
 * Returns:   int - if error: -1 else g_iInputFD
 */
int initJoystickControl();

/*
 * Method:    Loads mouse file descriptor if it finds one (if not error)
 *				Mouse is defined as device with left click button
 * Returns:   int - if error -1 else g_iInputFD
 */
int initMouseControl();

/*
 * Method:    Loads keyboard file descriptor. Keyboard defined as device with
 *				repetitive keys TODO: like mouse ENTER Key?
 * Returns:   int - if error -1 else g_iInputFD
 */
int initKeyboardControl();

/*
 * Method:    openKernelConnection - indirectly called by init methods above
 * Returns:   int - if error -1 else g_iInputFD
 * Parameter: int * piFD - pointer where fileDescriptor should be stored (at the end same as return value)
 * Parameter: char * pszSource - /dev/input/EVENT_URL+id or /dev/input/js+id
 */
int openKernelConnection(int *piFD, char *pszSource);

#endif // joystickControl_h__