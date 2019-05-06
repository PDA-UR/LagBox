#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5 import QtWidgets, uic
from PyQt5.QtGui import QIcon, QPixmap

from PyQt5.QtCore import QTimer, Qt, QEvent
import sys
from subprocess import Popen, PIPE, STDOUT
import struct
import evdev
import os
import time
import csv
from datetime import datetime
import requests

import DataPlotter

from PyQt5.QtWidgets import QApplication, QMainWindow, QMenu, QVBoxLayout, QSizePolicy, QMessageBox, QWidget, QPushButton, qApp
from PyQt5.QtGui import QIcon


class Constants:
    UI_FILE = 'latency_gui_800x480.ui'
    DEVICE_TYPES = ['Gamepad', 'Mouse', 'Keyboard']
    DEVICE_TYPE_IDS = {'Gamepad': 1, 'Mouse': 2, 'Keyboard': 3}
    WINDOW_TITLE = 'LagBox'
    BUTTON_NEXT_DEFAULT_NAME = 'Next >'

    MODE = 3
    # (0 = stepper mode, 1 = stepper latency test mode, 2 = stepper reset mode,
    # 3 = auto mode, 4 = pressure sensor test mode)
    NUM_TEST_ITERATIONS = 100
    NUM_DISPLAYED_DECIMAL_PLACES = 1  # Number of decimal places displayed of the current measurement in ms

    SERVER_URL = 'https://hci.ur.de/projects/latency/upload'  # URL to the server where .csv files of measurement data should get uploaded

class LatencyGUI(QtWidgets.QWizard):

    device_objects = []
    device_id = -1
    device_type = 2
    button_code = -1
    device_name = ''
    vendor_id = ''
    product_id = ''

    output_file_path = ''  # Filepath and name of the created .csv file
    stats = ''

    authors = ''
    publish_names = False
    email = ''
    additional_notes = ''

    timer = None
    is_measurement_running = False
    measurement_finished = False

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.ui = uic.loadUi(Constants.UI_FILE, self)
        self.setWindowTitle(Constants.WINDOW_TITLE)
        self.showFullScreen()

        # Set an eventFilter on the entire application
        qApp.installEventFilter(self)

        self.currentIdChanged.connect(self.disable_back)

        self.init_ui_page_one()
        self.show()

    def disable_back(self):
        print('Page ID:', QtWidgets.QWizard.currentId(self))

        # Only show an back button on page 2 (ID 1)
        if QtWidgets.QWizard.currentId(self) is not 1:
            self.button(QtWidgets.QWizard.BackButton).hide()
        else:
            print('Showing Back Button')
            self.button(QtWidgets.QWizard.BackButton).show()

    # The eventFilter catches all events. Enter presses are prevented
    # https://wiki.qt.io/How_to_catch_enter_key
    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                return True

        return super().eventFilter(obj, event)

    # User interface for page one (Page where general settings are placed)
    def init_ui_page_one(self):
        self.reset_all_data()
        self.button(QtWidgets.QWizard.BackButton).hide()

        self.ui.setButtonText(QtWidgets.QWizard.NextButton, Constants.BUTTON_NEXT_DEFAULT_NAME)
        self.ui.setButtonText(QtWidgets.QWizard.CancelButton, 'Cancel')
        self.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_two)
        self.ui.button_refresh.clicked.connect(self.get_connected_devices)
        self.ui.comboBox_device.currentIndexChanged.connect(self.on_combobox_device_changed)

        self.init_combobox_device_type(None)
        self.get_connected_devices()

    def reset_all_data(self):
        self.device_objects = []
        self.device_id = -1
        self.device_type = 2
        self.button_code = -1
        self.device_name = ''
        self.vendor_id = ''
        self.product_id = ''

        self.output_file_path = ''  # Filepath and name of the created .csv file
        self.stats = ''

        self.authors = ''
        self.publish_names = False
        self.email = ''
        self.additional_notes = ''

        self.timer = None
        self.is_measurement_running = False
        self.measurement_finished = False


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

        self.ui.label_pressed_button_id.setText('')

        # Disable the button until the keycode has been found out
        self.ui.button(QtWidgets.QWizard.NextButton).setEnabled(False)
        self.ui.button_restart_measurement.setEnabled(True)

        self.listen_for_key_inputs()

    # User interface for page three (Page where the LagBox measurement takes place)
    def init_ui_page_three(self):
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_three)
        self.ui.button(QtWidgets.QWizard.BackButton).clicked.disconnect(self.on_page_two_back_button_pressed)

        if not self.is_measurement_running:
            self.is_measurement_running = True
            self.ui.setButtonText(QtWidgets.QWizard.NextButton, Constants.BUTTON_NEXT_DEFAULT_NAME)
            self.button(QtWidgets.QWizard.NextButton).hide()

            # Measurement can only start after UI has loaded completely
            timer_start_measurement = QTimer(self)
            timer_start_measurement.setSingleShot(True)
            timer_start_measurement.timeout.connect(self.start_measurement)
            timer_start_measurement.start(100)

    # User interface for page four (Page that displays the results of the lagbox measurement)
    def init_ui_page_four(self):
        # self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_three)
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_five)

        # Path where the log will be saved
        self.ui.label_path_name.setText(os.path.dirname(os.path.realpath(__file__)).replace('gui', 'log'))

        self.ui.label_statistics.setText(self.stats)

        try:
            image = QPixmap(self.output_file_path.replace('.csv', '.png')).scaled(1000, 190, Qt.KeepAspectRatio)
            self.ui.label_image.setPixmap(image)
        except error:
            print('PLOT IMAGE NOT AVAILABLE!', error)

    # User interface for page five (Page that askes the user if he wants to upload the measurements)
    def init_ui_page_five(self):
        self.ui.setButtonText(QtWidgets.QWizard.NextButton, 'Continue to Upload Results')
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_five)
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_six)

        self.ui.setButtonText(QtWidgets.QWizard.CancelButton, 'Exit application without uploading results')

        #TODO: Add custom button to restart the application to conduct a new measurement
        #self.setOption(QtWidgets.QWizard.HaveCustomButton1, True)
        #self.ui.setButtonText(QtWidgets.QWizard.CustomButton1, 'Start a new measurement without uploading results')
        #self.button(QtWidgets.QWizard.CustomButton1).clicked.connect(self.restart_application)

    def restart_application(self):
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_six)
        self.setOption(QtWidgets.QWizard.HaveCustomButton1, False)
        self.init_ui_page_one()
        QtWidgets.QWizard.restart(self)

    # Init UI for page six (Accept the conditions for uploading measurements)
    def init_ui_page_six(self):
        self.setOption(QtWidgets.QWizard.HaveCustomButton1, False)

        self.ui.setButtonText(QtWidgets.QWizard.NextButton, 'Accept')
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_six)
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_seven)
        self.ui.setButtonText(QtWidgets.QWizard.CancelButton, 'Finish without uploading results')

    # User interface for page seven (Page where data about uploading the data is collected)
    def init_ui_page_seven(self):
        self.ui.setButtonText(QtWidgets.QWizard.CancelButton, 'Cancel Upload and Exit')
        self.ui.setButtonText(QtWidgets.QWizard.NextButton, 'Upload Results')
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_seven)
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.on_page_seven_next_button_pressed)

        # TODO: Prefill the author field and maybe even the email field with information saved in a .ini file
        self.ui.lineEdit_authors.setText(os.environ['USER'])

    # User interface for page eight (Page where The user is thanked for its participation)
    def init_ui_page_eight(self):
        self.button(QtWidgets.QWizard.NextButton).hide()
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

    def on_page_seven_next_button_pressed(self):
        self.save_additional_information_to_csv()
        self.init_ui_page_eight()

    # Fills the combobox with all possible device types defined in the constants
    def init_combobox_device_type(self, auto_detected_value):
        self.ui.comboBox_device_type.clear()  # Empty the list

        if not (auto_detected_value is None):  # Check if an auto-detected value exists
            new_list = Constants.DEVICE_TYPES.copy()
            new_list.insert(0, auto_detected_value)
            self.ui.comboBox_device_type.addItems(new_list)
        else:
            self.ui.comboBox_device_type.addItems(Constants.DEVICE_TYPES)

    # Initialize the combobox with a list of deviced handed over
    def init_combobox_device(self, devices):
        self.ui.comboBox_device.clear()
        self.ui.comboBox_device.addItems(devices)
        self.ui.comboBox_device_type.setCurrentIndex(0)

    # If the user selects a different device in the combobox, all variables will get updated with new data
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

    # Detect the button a user pressed in order to get the ID of that button
    def listen_for_key_inputs(self):
        if self.ui.button_restart_measurement.isEnabled():
            self.ui.label_pressed_button_id.setText('')
            self.ui.button(QtWidgets.QWizard.NextButton).setEnabled(False)
            self.ui.button_restart_measurement.setText('Measuring...')
            self.ui.button_restart_measurement.setEnabled(False)
            print("Starting Button detection")

            self.timer = QTimer(self)
            self.timer.timeout.connect(self.scan_key_inputs)
            self.timer.start(50)

    def validate_inputs(self):
        self.device_name = self.ui.lineEdit_device_name.text()
        # TODO: Remove all non-allowed chars from device name and set a maximum length for the string
        self.device_type = Constants.DEVICE_TYPE_IDS[str(self.ui.comboBox_device_type.currentText()).replace(' (auto-detected)', '')]

        print("Device name:", self.device_name)
        print("Device type ID:", self.device_type)


    # Get a list of all connected devices of the computer
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
        lines = []

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

        # TODO: Find correct bInterval value if there are multiple
        return lines[0]

    # if a user chooses to share and upload his/her measurement results, additional data like the users name and
    # email-adress will be saved to the csv file
    def save_additional_information_to_csv(self):
        print('Saving additional information to CSV')
        print('Path of csv file:', self.output_file_path)

        self.authors = self.ui.lineEdit_authors.text()
        self.publish_names = self.ui.checkBox_allow_name_publishing.isChecked()
        self.email = self.ui.lineEdit_email.text()
        self.additional_notes = self.ui.plainTextEdit_additional_notes.toPlainText()

        print("Authors: ", self.authors)
        print('Publish names', self.publish_names)
        print('Email', self.email)
        print('Notes', self.additional_notes)

        # Update data in existing csv file:
        # https://stackoverflow.com/questions/14471049/python-2-7-1-how-to-open-edit-and-close-a-csv-file

        new_rows = []  # a holder for our modified rows when we make them
        changes = {  # a dictionary of changes to make, find 'key' substitue with 'value'
            '#author:;': '#author:;' + self.authors,
            '#vendorId:;': '#vendorId:;' + self.vendor_id,
            '#productId:;': '#productId:;' + self.product_id,
            '#date:;': '#date:;' + datetime.today().strftime('%d-%m-%Y'),
            '#bInterval:;': '#bInterval:;' + str(self.get_device_bInterval()),
            '#deviceType:;': '#deviceType:;' + str(self.device_type),
            '#email:;': '#email:;' + self.email,
            '#public:;': '#public:;' + str(self.publish_names),
            '#notes:;': '#notes:;' + self.additional_notes.replace("\n", " ")
        }

        with open(self.output_file_path, 'r') as f:
            reader = csv.reader(f)  # pass the file to our csv reader
            for row in reader:  # iterate over the rows in the file
                new_row = row  # at first, just copy the row
                for key, value in changes.items():  # iterate over 'changes' dictionary
                    new_row = [x.replace(key, value) for x in new_row]  # make the substitutions
                new_rows.append(new_row)  # add the modified rows

        with open(self.output_file_path, 'w') as f:
            # Overwrite the old file with the modified rows
            writer = csv.writer(f)
            writer.writerows(new_rows)

        self.upload_measurement()

    # Upload the newly created .csv file of the latest measurement
    def upload_measurement(self):
        print('Pausing at upload')
        return
        data = {'bureaucracy[0]': self.output_file_path,
                'bureaucracy[1]': self.authors,
                'bureaucracy[2]': self.email,
                'bureaucracy[3]': int(self.publish_names is True),  # Convert "True"/"False" to 1 or 0
                'bureaucracy[4]': self.additional_notes,
                'bureaucracy[$$id]': '1',
                'id': 'projects:latency:upload'}
        print('Data:', data)

        r = requests.post(Constants.SERVER_URL, data=data)
        print(r.status_code, r.reason)

    # Extract all USB devices connected to the computer and save the details of each device as an object
    def extract_relevant_devices(self, devices):
        device_names = []
        for device in devices:
            if 'usb' in device[2]:  # Only accept devices if they are listed as usb devices
                vendor_id = device[0].split(' ')[2].replace('Vendor=', '')
                product_id = device[0].split(' ')[3].replace('Product=', '')
                name = device[1].replace('"', '').replace('N: Name=', '')
                device_id = self.get_device_id(device[5])
                device_type_auto_detected = self.get_device_type(device[5])

                device_already_in_list = False
                for existing_device in self.device_objects:
                    if existing_device.name == name:
                        device_already_in_list = True

                # TODO: under cat /proc/bus/input/devices, a device sometimes appears multiple times.
                # Verify that there is no difference between two entries
                if not device_already_in_list:
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

                            # self.ui.button(QtWidgets.QWizard.NextButton).setFocusPolicy(Qt.NoFocus)
                            self.ui.button(QtWidgets.QWizard.NextButton).setEnabled(True)

                # End loop after 25ms. The QTimer will restart it every 50ms.
                # Therefore an additional 25ms remain for the user to interact with the UI in other ways.
                if time.time() - time_start > 0.025:
                    return

        except PermissionError as error:
            print(error)  # TODO: Check if this error can happen on a Raspberry Pi

    # https://www.saltycrane.com/blog/2008/09/how-get-stdout-and-stderr-using-python-subprocess-module/
    def start_measurement(self):
        print('Start Measurement')

        command = '../bin/inputLatencyMeasureTool' + \
                  ' -m ' + str(Constants.MODE) + \
                  ' -tmin 100 -tmax 10000' + \
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
                self.ui.label_press_button_again.setText('Measurement finished. Analysing and saving data...')
                break
            elif 'cancelled' in str(line):
                sys.exit('Measurement failed')
            elif '/log/' in str(line):
                self.output_file_path = str(line).replace("b'", '').replace("\\n'", '')
            elif len(line) is 0:
                sys.exit('Found an empty line in stdout. This should not happen')
                #break  # As soon as no more data is sent, stdout will only return empty lines

        if not self.measurement_finished:
            self.measurement_finished = True
            timer_create_data_plot = QTimer(self)
            timer_create_data_plot.setSingleShot(True)
            timer_create_data_plot.timeout.connect(self.create_data_plot)
            timer_create_data_plot.start(100)


        # TODO: Verify here if measurement was successful
        self.ui.button(QtWidgets.QWizard.NextButton).setEnabled(True)

    def create_data_plot(self):
        self.dataplotter = DataPlotter.DataPlotter()
        self.stats = self.dataplotter.process_filedata(self.output_file_path)
        # print(self.stats)
        self.init_ui_page_four()
        self.ui.next()


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
