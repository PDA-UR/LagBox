#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5 import QtWidgets, uic
import sys
from subprocess import Popen, PIPE, STDOUT
import struct
import evdev
import os


class Constants:
    DEVICE_TYPES = ["Gamepad", "Mouse", "Keyboard"]
    WINDOW_TITLE = 'LagBox'


class LatencyGUI(QtWidgets.QWizard):

    device_objects = []
    device_id = -1

    def __init__(self):
        super().__init__()
        self.init_ui_page_one()

    # User interface for page one
    def init_ui_page_one(self):
        self.ui = uic.loadUi("latency_gui.ui", self)
        self.setWindowTitle(Constants.WINDOW_TITLE)
        self.show()
        self.init_combobox_device_type()
        self.button(QtWidgets.QWizard.NextButton).clicked.connect(self.validate_inputs)
        self.ui.button_refresh.clicked.connect(self.get_connected_devices)
        self.ui.comboBox_device.currentIndexChanged.connect(self.on_combobox_device_changed)
        self.ui.lineEdit_authors.setText(os.environ['USER'])
        self.get_connected_devices()

    # User interface for page two
    def init_ui_page_two(self):
        self.ui.button_start_listening.clicked.connect(self.on_start_listening_button_pressed)
        self.ui.setButtonText(QtWidgets.QWizard.FinishButton, 'Start Measurement')
        self.ui.label_selected_device.setText(self.ui.lineEdit_device_name.text())
        self.ui.label_selected_device_type.setText(str(self.ui.comboBox_device_type.currentText()))

    # Fills the combobox with all possible device types defined in the constants
    def init_combobox_device_type(self):
        self.ui.comboBox_device_type.addItems(Constants.DEVICE_TYPES)
        self.ui.comboBox_device_type.setCurrentIndex(0)

    def init_combobox_device(self, devices):
        self.ui.comboBox_device.clear()
        self.ui.comboBox_device.addItems(devices)
        self.ui.comboBox_device_type.setCurrentIndex(0)

    def on_combobox_device_changed(self):
        self.ui.lineEdit_device_name.setText(str(self.ui.comboBox_device.currentText()))
        for device in self.device_objects:
            print(device.name)
            print(self.ui.comboBox_device.currentText())
            if device.name == self.ui.comboBox_device.currentText():
                print('in loop')
                self.device_id = device.device_id
                break

    def on_start_listening_button_pressed(self):
        print("Starting measurement")
        #self.ui.button_start_listening.setText('Listening...')
        self.get_pressed_button()

    def validate_inputs(self):
        authors = self.ui.lineEdit_authors.text()
        device_name = self.ui.lineEdit_device_name.text()
        device_type = str(self.ui.comboBox_device_type.currentText())

        print("Authors: ", authors)
        print("Device name: ", device_name)
        print("Device type: ", device_type)

        self.init_ui_page_two()

    def get_connected_devices(self):
        lines = []

        command = 'cat /proc/bus/input/devices'
        process = Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        empty_lines = 0
        for line in iter(process.stdout.readline, ''):
            if len(line) is 0:
                empty_lines += 1
                if empty_lines > 3:
                    break
            else:
                empty_lines = 0
                lines.append(line.decode("utf-8").replace('\n', ''))

        devices = []

        current_device = []
        for i in range(len(lines)):
            if len(lines[i]) > 0:
                current_device.append(lines[i])
            else:
                devices.append(current_device.copy())
                current_device.clear()

        # print(devices)
        self.extract_relevant_devices(devices)

    def extract_relevant_devices(self, devices):
        device_names = []
        for device in devices:
            if 'usb' in device[2]:  # Only accept devices if they are listed as usb devices
                vendor_id = device[0].split(' ')[2].replace('Vendor=', '')
                product_id = device[0].split(' ')[3].replace('Product=', '')
                name = device[1].replace('"', '').replace('N: Name=', '')
                device_id = self.get_device_id(device[5])
                # print('Device ID: ', device_id)
                device_names.append(name)
                self.device_objects.append(Device(vendor_id, product_id, name, device_id))

        self.init_combobox_device(device_names)

    def get_device_id(self, line):
        for part in line.split(' '):
            if 'event' in part:
                return part

    def get_pressed_button(self):
        try:
            device = evdev.InputDevice('/dev/input/' + str(self.device_id))

            for event in device.read_loop():
                if event.type == evdev.ecodes.EV_KEY:
                    key_event = evdev.categorize(event)
                    if key_event.keystate:
                        button_code = key_event.scancode
                        print('ID of pressed button:_', button_code)
                        self.ui.label_pressed_button_id.setText(str(button_code))
                        break

        except PermissionError as error:
            print(error)  # TODO: Check if this error can happen on a Raspberry Pi

    def start_measurement(self):
        pass
        # https://www.saltycrane.com/blog/2008/09/how-get-stdout-and-stderr-using-python-subprocess-module/
        # command = 'ping google.com -c 5'
        # process = Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        #
        # for line in iter(process.stdout.readline, ''):
        #     if len(line) is 0:
        #         break
        #     print(line)
        #
        # print("Reached end of loop")


class Device:

    def __init__(self, vendor_id, product_id, name, device_id):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.name = name
        self.device_id = device_id


def main():
    app = QtWidgets.QApplication(sys.argv)
    latencyGUI = LatencyGUI()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()