#ifndef GPIO_h
#define GPIO_h

#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>

#define PIN_LED_BUILTIN 953
#define PIN_BTN_BUILTIN 957
#define OUTPUT 0
#define INPUT 1
#define LOW 0
#define HIGH 1

#define STR_DIRECTION_OUT "out"
#define STR_DIRECTION_IN "in"

//const char *str_direction[2] = {"out", "in"};

void reservePin(int pin, int direction);

void unreservePin(int pin);

void digitalWrite(int pin, int value);

int digitalRead(int pin);

#endif