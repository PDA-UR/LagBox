#include "GPIO.h"

int GPIO_file[1024]; // size is wrong but good enough for now

void reservePin(int pin, int direction)
{
	char str_pin[32];
	sprintf(str_pin, "%d", pin);

	char path_direction[64];
	sprintf(path_direction, "/sys/class/gpio/gpio%d/direction", pin);

	int fd_export = open("/sys/class/gpio/export", O_WRONLY);
	write(fd_export, str_pin, sizeof(str_pin));
	close(fd_export);

	int fd_direction = open(path_direction, O_WRONLY);
	write(fd_direction, direction == INPUT ? STR_DIRECTION_IN : STR_DIRECTION_OUT, direction == INPUT ? 2 : 3);
	close(fd_direction);

	char path_file[32];
	sprintf(path_file, "/sys/class/gpio/gpio%d/value", pin);
	GPIO_file[pin] = open(path_file, O_WRONLY);
}

void unreservePin(int pin)
{
	close(GPIO_file[pin]);

    char str_pin[32];
    sprintf(str_pin, "%d", pin);

    int fd_export = open("/sys/class/gpio/unexport", O_WRONLY);
    write(fd_export, str_pin, sizeof(str_pin));
    close(fd_export);
}

void digitalWrite(int pin, int value)
{
	/*char path[32];
	sprintf(path, "/sys/class/gpio/gpio%d/value", pin);
	int fd = open(path, O_WRONLY);*/

	char buf[1];
	sprintf(buf, "%d", value);

	
	write(GPIO_file[pin], buf, 1);
	//close(fd);
}

int digitalRead(int pin)
{
	//char path[32];
	//sprintf(path, "/sys/class/gpio/gpio%d/value", pin);

	char buf;

	//int fd = open(path, O_RDONLY);
	read(GPIO_file[pin], &buf, 1);
	//close(fd);

	printf("a %x\n", buf);

	return buf == '0' || buf == 0x00 ? LOW : HIGH;
}