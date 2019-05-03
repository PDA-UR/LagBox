#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5 import QtWidgets, uic
from PyQt5.QtGui import QIcon, QPixmap

from PyQt5.QtCore import QTimer, Qt
import sys
from subprocess import Popen, PIPE, STDOUT
import struct
import evdev
import os
import time
import csv
from datetime import datetime
import DataPlotter

from PyQt5.QtWidgets import QApplication, QMainWindow, QMenu, QVBoxLayout, QSizePolicy, QMessageBox, QWidget, QPushButton
from PyQt5.QtGui import QIcon


class Constants:
    #UI_FILE = 'latency_gui.ui'
    UI_FILE = 'latency_gui_800x480.ui'
    DEVICE_TYPES = ['Gamepad', 'Mouse', 'Keyboard']
    DEVICE_TYPE_IDS = {'Gamepad': 1, 'Mouse': 2, 'Keyboard': 3}
    WINDOW_TITLE = 'LagBox'

    PLOT_X_MIN = 0  # Minimum x value of the plot
    PLOT_X_MAX = 100  # Maximum x value of the plot
    PLOT_WIDTH = 16
    PLOT_HEIGHT = 4
    PLOT_FONTSIZE = 18

    MODE = 3  # (0 = stepper mode, 1 = stepper latency test mode, 2 = stepper reset mode, 3 = auto mode, 4 = pressure sensor test mode)
    NUM_TEST_ITERATIONS = 100
    NUM_DISPLAYED_DECIMAL_PLACES = 1  # Number of decimal places displayed of the current measurement in ms


class LatencyGUI(QtWidgets.QWizard):

    device_objects = []
    device_id = -1
    device_type = 2
    button_code = -1
    device_name = ''
    vendor_id = ''
    product_id = ''

    stats = ''

    timer = None

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.ui = uic.loadUi(Constants.UI_FILE, self)
        self.setWindowTitle(Constants.WINDOW_TITLE)
        self.showFullScreen()
        self.show()

        self.init_ui_page_one()

    # User interface for page one (Page where general settings are placed)
    def init_ui_page_one(self):

        self.ui.setButtonText(QtWidgets.QWizard.NextButton, 'Next >')
        self.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_two)
        self.button(QtWidgets.QWizard.BackButton).hide()
        self.ui.button_refresh.clicked.connect(self.get_connected_devices)
        self.ui.comboBox_device.currentIndexChanged.connect(self.on_combobox_device_changed)

        self.init_combobox_device_type(None)
        self.get_connected_devices()

    # User interface for page two (Page where the detection of the input button takes place)
    def init_ui_page_two(self):
        self.validate_inputs()
        self.get_device_bInterval()

        self.ui.button_restart_measurement.clicked.connect(self.listen_for_key_inputs)
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_two)
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_three)
        self.ui.button(QtWidgets.QWizard.BackButton).clicked.connect(self.on_page_two_back_button_pressed)
        self.ui.label_selected_device.setText(self.ui.lineEdit_device_name.text())
        self.ui.label_selected_device_type.setText(str(self.ui.comboBox_device_type.currentText()))
        self.ui.setButtonText(QtWidgets.QWizard.NextButton, 'Start Measurement')
        # Disable the button until the keycode has been found out
        self.ui.button(QtWidgets.QWizard.NextButton).setEnabled(False)
        self.ui.button_restart_measurement.setEnabled(True)

        self.listen_for_key_inputs()

    # User interface for page three (Page where the LagBox measurement takes place)
    def init_ui_page_three(self):
        self.ui.setButtonText(QtWidgets.QWizard.NextButton, 'Next >')
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_three)
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_four)
        #self.ui.button(QtWidgets.QWizard.NextButton).setEnabled(False)
        self.button(QtWidgets.QWizard.BackButton).hide()

        timer_test = QTimer(self)
        timer_test.setSingleShot(True)
        timer_test.timeout.connect(self.start_measurement)
        timer_test.start(100)

    # User interface for page four (Page that displays the results of the lagbox measurement)
    def init_ui_page_four(self):
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_four)
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_five)
        self.button(QtWidgets.QWizard.BackButton).hide()

        # Path where the log will be saved
        self.ui.label_path_name.setText(os.path.dirname(os.path.realpath(__file__)).replace('gui', 'log'))

        self.ui.label_statistics.setText(self.stats)

        plot_name = '../log/AUTO_Logitech_USB-PS_2_Optical_Mouse_1ms_24.png'

        image = QPixmap(plot_name).scaledToHeight(190)
        self.ui.label_image.setPixmap(image)

        #self.init_plot()

    # User interface for page five (Page that askes the user if he wants to upload the measurements)
    def init_ui_page_five(self):
        print('Init Ui Page 5')

        self.ui.setButtonText(QtWidgets.QWizard.NextButton, 'Continue to Upload Results')
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_five)
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_six)
        self.button(QtWidgets.QWizard.BackButton).hide()

        self.ui.setButtonText(QtWidgets.QWizard.CancelButton, 'Finish without uploading results')

    # User interface for page six (Page where data about uploading the data is collected)
    def init_ui_page_six(self):
        self.ui.setButtonText(QtWidgets.QWizard.CancelButton, 'Cancel Upload and Exit')
        self.ui.setButtonText(QtWidgets.QWizard.NextButton, 'Upload Results')
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_six)
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.on_page_six_next_button_pressed)
        self.button(QtWidgets.QWizard.BackButton).hide()

        # TODO: Prefill the author field and maybe even the email field with information saved in a .ini file
        self.ui.lineEdit_authors.setText(os.environ['USER'])

        # User interface for page seven (Page where The user is thanked for its participation)

    def init_ui_page_seven(self):
        self.button(QtWidgets.QWizard.NextButton).hide()
        self.button(QtWidgets.QWizard.BackButton).hide()
        self.button(QtWidgets.QWizard.CancelButton).hide()
        self.ui.setButtonText(QtWidgets.QWizard.CancelButton, 'Finish')

    # Stop key detection if the user presses the back button and reconnect the "NextButton" to the correct function call
    def on_page_two_back_button_pressed(self):
        if self.timer is not None and self.timer.isActive():
            self.timer.stop()
            print('Stopped timer because back button was pressed')
        self.ui.setButtonText(QtWidgets.QWizard.NextButton, 'Next >')

        try:
            self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_three)
        except TypeError:
            print('back button was pressed before UI was loaded completely. No need to worry')
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_two)

    def on_page_six_next_button_pressed(self):
        self.save_additional_information_to_csv()
        self.init_ui_page_seven()

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

        # Iterate through list of available devices until the one that is currently selected is found
        for device in self.device_objects:
            if device.name == self.ui.comboBox_device.currentText():
                self.device_id = device.device_id.replace('Handlers=', '').replace("\\n'", '')
                self.init_combobox_device_type(device.device_type)
                self.vendor_id = device.vendor_id
                self.product_id = device.product_id

                break  # No need to continue after correct device is found

    def listen_for_key_inputs(self):
        if self.ui.button_restart_measurement.isEnabled():
            self.ui.button(QtWidgets.QWizard.NextButton).setEnabled(False)
            self.ui.button_restart_measurement.setText('Measuring...')
            self.ui.button_restart_measurement.setEnabled(False)
            print("Starting measurement")

            self.timer = QTimer(self)
            self.timer.timeout.connect(self.scan_key_inputs)
            self.timer.start(50)

    def validate_inputs(self):
        self.device_name = self.ui.lineEdit_device_name.text()
        # TODO: Remove all non-allowed chars from device name and set a maximum length for the string
        self.device_type = Constants.DEVICE_TYPE_IDS[str(self.ui.comboBox_device_type.currentText()).replace(' (auto-detected)', '')]

        print("Device name:", self.device_name)
        print("Device type ID:", self.device_type)

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

    # Extract the bInterval of the device
    def get_device_bInterval(self):
        print('Searching bInterval of device')
        lines = []

        # vendor_device_id = '03f0:094a'
        command = 'lsusb -vd ' + self.vendor_id + ':' + self.product_id + ' | grep bInterval'
        process = Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        for line in iter(process.stdout.readline, ''):
            if len(line) is 0:
                break
            else:
                if 'bInterval' in str(line):
                    lines.append(line.decode("utf-8").replace('\n', '').replace('bInterval', '').strip())
        print('Values for bInterval of device:')
        print(lines)

    def save_additional_information_to_csv(self):
        print('Saving additional information to CSV')

        # authors = self.ui.lineEdit_authors.text()
        # publish_names = self.ui.checkBox_allow_name_publishing.isChecked()
        # email = self.ui.lineEdit_email.text()
        # additional_notes = self.ui.plainTextEdit_additional_notes.toPlainText()
        #
        # print("Authors: ", authors)
        # print('Publish names', publish_names)
        # print('Email', email)
        # print('Notes', additional_notes)
        #
        # # https://stackoverflow.com/questions/14471049/python-2-7-1-how-to-open-edit-and-close-a-csv-file
        #
        # new_rows = []  # a holder for our modified rows when we make them
        # changes = {  # a dictionary of changes to make, find 'key' substitue with 'value'
        #     '#author:;': '#author:;' + authors,
        #     '#vendorId:;': '#vendorId:;' + self.vendor_id,
        #     '#productId:;': '#productId:;' + self.product_id,
        #     '#date:;': '#date:;' + datetime.today().strftime('%d-%m-%Y'),
        #     '#bInterval:;': '#bInterval:;' + '????',  # TODO: Find out bInterval
        #     '#deviceType:;': '#deviceType:;' + str(self.device_type),
        #     '#email:;': '#email:;' + email,
        #     '#public:;': '#public:;' + str(publish_names),
        #     '#notes:;': '#notes:;' + additional_notes
        # }
        #
        # filename = 'test.csv'
        #
        # with open(filename, 'rb') as f:
        #     reader = csv.reader(f)  # pass the file to our csv reader
        #     for row in reader:  # iterate over the rows in the file
        #         new_row = row  # at first, just copy the row
        #         for key, value in changes.items():  # iterate over 'changes' dictionary
        #             new_row = [x.replace(key, value) for x in new_row]  # make the substitutions
        #         new_rows.append(new_row)  # add the modified rows
        #
        # with open(filename, 'wb') as f:
        #     # Overwrite the old file with the modified rows
        #     writer = csv.writer(f)
        #     writer.writerows(new_rows)
        #
        # self.upload_measurement()

    # Upload the newly created .csv file of the latest measurement
    def upload_measurement(self):
        pass

    # Exract all USB devices connected to the computer and save the details of each device as an object
    def extract_relevant_devices(self, devices):
        device_names = []
        for device in devices:
            if 'usb' in device[2]:  # Only accept devices if they are listed as usb devices
                vendor_id = device[0].split(' ')[2].replace('Vendor=', '')
                product_id = device[0].split(' ')[3].replace('Product=', '')
                name = device[1].replace('"', '').replace('N: Name=', '')
                device_id = self.get_device_id(device[5])
                device_type_auto_detected = self.get_device_type(device[5])
                device_names.append(name)
                self.device_objects.append(Device(vendor_id, product_id, name, device_id, device_type_auto_detected))

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

    # This function will listen for all key inputs of a given device. As soon as the first key-down press is detected,
    # The detection loop will end.
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
                            self.button_code = key_event.scancode
                            print('ID of pressed button: ', self.button_code)
                            self.ui.label_pressed_button_id.setText(str(self.button_code))
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

    # https://www.saltycrane.com/blog/2008/09/how-get-stdout-and-stderr-using-python-subprocess-module/
    def start_measurement(self):
        command = '../bin/inputLatencyMeasureTool' + \
                  ' -m ' + str(Constants.MODE) + \
                  ' -b ' + str(self.button_code) + \
                  ' -d ' + str(self.device_type) + \
                  ' -event ' + str(self.device_id).replace('event', '') + \
                  ' -n ' + str(Constants.NUM_TEST_ITERATIONS) + \
                  " -name '" + self.device_name + "'"

        print(command)

        process = Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)

        # TODO: If the user has selected the wrong button, the UI will freeze.
        # Therefore the measurement needs to be cancelled after a certain amount of time

        for line in iter(process.stdout.readline, ''):
            print(line)
            line_id = str(line).split(',')[0].replace("b'", '')  # Convert line to String and remove the leading "b'"
            if line_id.isdigit():  # Only count the progress if the line is actually the result of a measurement
                self.ui.label_press_button_again.setText('')
                self.ui.progressBar.setValue((int(line_id) / Constants.NUM_TEST_ITERATIONS) * 100)
                self.ui.label_progress.setText(str(line_id) + '/' + str(Constants.NUM_TEST_ITERATIONS))
                measured_time = float(str(line).split(',')[2].replace("\\n'", ''))
                self.ui.label_last_measured_time.setText(str(round(measured_time, Constants.NUM_DISPLAYED_DECIMAL_PLACES)) + 'ms')

            if 'done' in str(line):
                print('Finished successful')
                break
            elif 'cancelled' in str(line):
                print('Cancelled!')
                sys.exit('Measurement failed')
            elif len(line) is 0:
                break  # As soon as no more data is sent, stdout will only return empty lines

        print("Reached end of loop")
        self.dataplotter = DataPlotter.DataPlotter()
        self.stats = self.dataplotter.process_filedata('Test')
        print(self.stats)

        # TODO: Verify here if measurement was successful
        self.ui.button(QtWidgets.QWizard.NextButton).setEnabled(True)


# An object representation of all relevant data about connected USB device
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
