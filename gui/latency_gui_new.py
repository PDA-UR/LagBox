#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QTimer
import sys
from subprocess import Popen, PIPE, STDOUT
import struct
import evdev
import os
import time

# from PyQt5.QtWidgets import QApplication, QMainWindow, QMenu, QVBoxLayout, QSizePolicy, QMessageBox, QWidget, QPushButton
#from PyQt5.QtGui import QIcon

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from matplotlib import pyplot as plt
# import seaborn as sns

import random



class Constants:
    UI_FILE = 'latency_gui.ui'
    DEVICE_TYPES = ['Gamepad', 'Mouse', 'Keyboard']
    WINDOW_TITLE = 'LagBox'

    PLOT_X_MIN = 0  # Minimum x value of the plot
    PLOT_X_MAX = 100  # Maximum x value of the plot
    PLOT_WIDTH = 16
    PLOT_HEIGHT = 4
    PLOT_FONTSIZE = 18


# Parts of code of following class based on https://pythonspot.com/pyqt5-matplotlib/
class PlotCanvas(FigureCanvas):

    def __init__(self, parent=None):
        print('Init plot')
        fig = Figure(figsize=(7, 3), dpi=100)
        #self.axes = fig.add_subplot(111)

        FigureCanvas.__init__(self, fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        self.plot()

    def plot(self):
        latencies = [random.random() for i in range(25)]
        # ax = self.figure.add_subplot(111)
        # ax.plot(data, 'r-')
        # ax.set_title('PyQt Matplotlib Example')
        # self.draw()

        plt.rcParams.update({'font.size': Constants.PLOT_FONTSIZE})
        plt.figure(figsize=[Constants.PLOT_WIDTH, Constants.PLOT_HEIGHT])
        ax = sns.swarmplot(x=latencies, hue=None, palette="colorblind", dodge=True, marker="H", orient="h", alpha=1,
                           zorder=0)
        self.draw()

        # plt.title("TEST")
        plt.xlabel("latency (ms)")
        plt.xlim(Constants.PLOT_X_MIN, Constants.PLOT_X_MAX)

        axes = plt.gca()


class LatencyGUI(QtWidgets.QWizard):

    device_objects = []
    device_id = -1

    timer = None

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_ui_page_one()

    def init_ui(self):
        self.ui = uic.loadUi(Constants.UI_FILE, self)
        self.setWindowTitle(Constants.WINDOW_TITLE)

        #dataplot = PlotCanvas(self)
        #dataplot.move(50, 100)

        self.show()

    # User interface for page one (Page where general settings are placed)
    def init_ui_page_one(self):
        self.ui.setButtonText(QtWidgets.QWizard.NextButton, 'Next >')
        self.init_combobox_device_type(None)
        self.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_two)
        self.ui.button_refresh.clicked.connect(self.get_connected_devices)
        self.ui.comboBox_device.currentIndexChanged.connect(self.on_combobox_device_changed)
        #self.ui.lineEdit_authors.setText(os.environ['USER'])
        self.get_connected_devices()

    # User interface for page two (Page where the detection of the input button takes place)
    def init_ui_page_two(self):
        print('Init UI page 2')
        self.ui.button_restart_measurement.clicked.connect(self.listen_for_key_inputs)

        self.ui.setButtonText(QtWidgets.QWizard.NextButton, 'Start Measurement')
        self.ui.button(QtWidgets.QWizard.NextButton).setEnabled(False)  # Disable the button until the keycode has been found out

        self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_two)
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_three)

        self.ui.button(QtWidgets.QWizard.BackButton).clicked.connect(self.on_page_two_back_button_pressed)
        self.ui.label_selected_device.setText(self.ui.lineEdit_device_name.text())
        self.ui.label_selected_device_type.setText(str(self.ui.comboBox_device_type.currentText()))

        self.ui.button_restart_measurement.setEnabled(True)
        self.listen_for_key_inputs()

    # User interface for page three (Page where the LagBox measurement takes place)
    def init_ui_page_three(self):
        print('Init UI page 3')
        self.ui.setButtonText(QtWidgets.QWizard.NextButton, 'Next >')
        self.ui.button(QtWidgets.QWizard.NextButton).setEnabled(True)
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_three)
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_four)

    # User interface for page four (Page that displays the results of the lagbox measurement)
    def init_ui_page_four(self):
        print('Init UI page 4')
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_four)
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_five)

    # User interface for page five (Page that askes the user if he wants to upload the measurements)
    def init_ui_page_five(self):
        print('Init UI page 5')
        self.ui.setButtonText(QtWidgets.QWizard.NextButton, 'Upload Results')
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_five)
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_six)

        self.ui.setButtonText(QtWidgets.QWizard.CancelButton, 'Finish')
        # self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.quit_application)

    def init_ui_page_six(self):
        print('Init UI page 6')
        pass

    # User interface for page six (Page where data about uploading the data is collected)
    def init_ui_page_six(self):
        # TODO: Prefill the author field and maybe even the email field with information saved in a .ini file
        pass

    def on_page_two_next_button_pressed(self):
        pass
        #self.init_ui_page_three()

    def on_page_two_back_button_pressed(self):
        if self.timer is not None and self.timer.isActive():
            self.timer.stop()
            print('Stopped timer because back button was pressed')
        self.ui.setButtonText(QtWidgets.QWizard.NextButton, 'Next >')
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_three)
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_two)

    # Fills the combobox with all possible device types defined in the constants
    def init_combobox_device_type(self, auto_detected_value):
        self.ui.comboBox_device_type.clear()  # Empty the list

        if not (auto_detected_value is None):  # Check if an auto-detected value exists
            new_list = Constants.DEVICE_TYPES.copy()
            new_list.insert(0, auto_detected_value)
            self.ui.comboBox_device_type.addItems(new_list)
        else:
            self.ui.comboBox_device_type.addItems(Constants.DEVICE_TYPES)

    def init_combobox_device(self, devices):
        self.ui.comboBox_device.clear()
        self.ui.comboBox_device.addItems(devices)
        self.ui.comboBox_device_type.setCurrentIndex(0)

    def on_combobox_device_changed(self):
        # Copy the name of the device into the text field to allow the user to change the displayed name
        self.ui.lineEdit_device_name.setText(str(self.ui.comboBox_device.currentText()))

        #
        for device in self.device_objects:
            if device.name == self.ui.comboBox_device.currentText():
                self.device_id = device.device_id
                self.init_combobox_device_type(device.device_type)

                break

    def listen_for_key_inputs(self):
        if self.ui.button_restart_measurement.isEnabled():
            self.ui.button_restart_measurement.setText('Measuring...')
            self.ui.button_restart_measurement.setEnabled(False)
            print("Starting measurement")

            self.timer = QTimer(self)
            self.timer.timeout.connect(self.scan_key_inputs)
            self.timer.start(50)

    def validate_inputs(self):
        #authors = self.ui.lineEdit_authors.text()
        device_name = self.ui.lineEdit_device_name.text()
        device_type = str(self.ui.comboBox_device_type.currentText())

        #print("Authors: ", authors)
        print("Device name: ", device_name)
        print("Device type: ", device_type)

    def get_connected_devices(self):
        lines = []

        command = 'cat /proc/bus/input/devices'  # Get data about all connected devices
        process = Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        empty_lines = 0
        for line in iter(process.stdout.readline, ''):
            if len(line) is 0:  # Count all empty lines
                empty_lines += 1
                if empty_lines > 3:
                    # In the list of available devices, between two different devices there are always three blank
                    # lines. After all devices are listed, only blank lines are printed out. Therefore, if more than
                    # three blank lines are found, we can stop because we know we reached the end.
                    break
            else:
                empty_lines = 0  # Reset the empty line counter
                lines.append(line.decode("utf-8").replace('\n', ''))

        devices = []

        current_device = []
        for i in range(len(lines)):
            if len(lines[i]) > 0:
                current_device.append(lines[i])
            else:
                devices.append(current_device.copy())
                current_device.clear()

        self.extract_relevant_devices(devices)

    # Exract all USB devices connected to the computer and save the details of each device as an object
    def extract_relevant_devices(self, devices):
        device_names = []
        for device in devices:
            if 'usb' in device[2]:  # Only accept devices if they are listed as usb devices
                vendor_id = device[0].split(' ')[2].replace('Vendor=', '')
                product_id = device[0].split(' ')[3].replace('Product=', '')
                name = device[1].replace('"', '').replace('N: Name=', '')
                device_id = self.get_device_id(device[5])
                device_type = self.get_device_type(device[5])
                # print('Device type:', device_type)
                device_names.append(name)
                self.device_objects.append(Device(vendor_id, product_id, name, device_id, device_type))

        self.init_combobox_device(device_names)

    # Extract the ID of the device (eventXX) from the device details by searching for the corresponding keyword
    def get_device_id(self, line):
        for part in line.split(' '):
            if 'event' in part:
                return part

    # Auto-detect the type of the device by searching for the corresponding keywords in the device details
    def get_device_type(self, line):
        if 'kbd' in line:
            return 'Keyboard (auto-detected)'
        if 'mouse' in line:
            return 'Mouse (auto-detected)'
        if 'js' in line:
            return 'Gamepad (auto-detected)'
        return None

    def scan_key_inputs(self):
        try:
            device = evdev.InputDevice('/dev/input/' + str(self.device_id))
            time_start = time.time()  # Remember start time

            while True:
                event = device.read_one()  # Get current event
                if event is not None:
                    if event.type == evdev.ecodes.EV_KEY:  # Check if the current event is a button press
                        key_event = evdev.categorize(event)
                        if key_event.keystate:  # Check if button is pressed down
                            button_code = key_event.scancode
                            print('ID of pressed button: ', button_code)
                            self.ui.label_pressed_button_id.setText(str(button_code))
                            self.timer.stop()  # Stop the timer so that this function is not called again
                            self.ui.button_restart_measurement.setText('Restart Button Detection')
                            self.ui.button_restart_measurement.setEnabled(True)
                            self.ui.button(QtWidgets.QWizard.NextButton).setEnabled(True)

                # End loop after 25ms. The QTimer will restart it every 50ms.
                # Therefore an additional 25ms remain for the user to interact with the UI in other ways.
                if time.time() - time_start > 0.025:
                    return

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

    def __init__(self, vendor_id, product_id, name, device_id, device_type):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.name = name
        self.device_id = device_id
        self.device_type = device_type


def main():
    app = QtWidgets.QApplication(sys.argv)
    latencyGUI = LatencyGUI()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()