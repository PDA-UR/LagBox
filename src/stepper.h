#ifndef stepper_h__
#define stepper_h__

void initializeStepper(int steps, int pinDir, int pinStep);

void setStepperRPM(int rpm);

void rotateStepper(int degrees);

void moveDistance(float distance);

void moveStepper(int steps);

void moveStepperAsync(int steps);

void* moveStepperThread(void* args);

static int calculateWaitTime();

#endif