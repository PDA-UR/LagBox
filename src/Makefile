CC=gcc
CFLAGS=-Wall

main: inputLatencyMeasureTool.c
	-mkdir ../bin
	$(CC) -Wall -c inputLatencyMeasureTool.c -lgpiod  -lrt -o ../bin/inputLatencyMeasureTool.o -std=gnu99
	$(CC) -Wall -c joystickControl.c -o ../bin/joystickControl.o -std=c99
	$(CC) -Wall -c fileLog.c -o ../bin/fileLog.o -std=c99
	$(CC) ../bin/inputLatencyMeasureTool.o ../bin/joystickControl.o ../bin/fileLog.o -lm -lgpiod -lrt -lpthread -o ../bin/inputLatencyMeasureTool

clean:
	-rm -rf ../bin
