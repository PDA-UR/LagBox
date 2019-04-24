#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5 import QtWidgets, uic
import sys
from subprocess import Popen, PIPE, STDOUT

class Constants:
    DEVICE_TYPES = ["Gamepad", "Mouse", "Keyboard"]


class LatencyGUI(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.ui = uic.loadUi("latency_gui.ui", self)
        self.show()
        self.init_combobox()
        self.ui.button_start_measurement.clicked.connect(self.on_measurement_started_button_pressed)

    def init_combobox(self):
        self.ui.comboBox_device_type.addItems(Constants.DEVICE_TYPES)
        self.ui.comboBox_device_type.setCurrentIndex(0)

    def on_measurement_started_button_pressed(self):
        print("Starting measurement")
        self.validate_inputs()

    def validate_inputs(self):
        authors = self.ui.lineEdit_authors.text()
        device_name = self.ui.lineEdit_device_name.text()
        device_type = str(self.ui.comboBox_device_type.currentText())

        print("Authors: ", authors)
        print("Device name: ", device_name)
        print("Device type: ", device_type)

        self.start_measurement()

    # https://www.saltycrane.com/blog/2008/09/how-get-stdout-and-stderr-using-python-subprocess-module/
    def start_measurement(self):
        command = 'ping google.com -c 5'
        process = Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)

        for line in iter(process.stdout.readline, ''):
            if len(line) is 0:
                break
            print(line)

        print("Reached end of loop")



class Device():

    def __init__(self, vendor_id, product_id, name):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.name = name


def main():
    app = QtWidgets.QApplication(sys.argv)
    latencyGUI = LatencyGUI()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()