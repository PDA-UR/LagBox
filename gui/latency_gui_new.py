#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5 import QtWidgets, uic
from PyQt5.QtGui import QIcon, QPixmap, QIcon
from PyQt5.QtWidgets import QApplication, qApp
from PyQt5.QtCore import QTimer, Qt, QEvent, pyqtSignal, pyqtSlot, QThread

import sys
from subprocess import Popen, PIPE, STDOUT
import struct
import evdev
import os
import csv
from datetime import datetime
import requests
import threading
import configparser

import DataPlotter  # Accepts a .csv file of a LagBox measurement and returns a dataplot and statistical data

import RPi.GPIO as GPIO


class Constants:
    UI_FILE = 'latency_gui_800x480.ui'
    DEVICE_TYPES = ['Gamepad', 'Mouse', 'Keyboard']
    DEVICE_TYPE_IDS = {'Gamepad': 1, 'Mouse': 2, 'Keyboard': 3}
    WINDOW_TITLE = 'LagBox'
    BUTTON_NEXT_DEFAULT_NAME = 'Next >'
    BUTTON_CANCEL_DEFAULT_NAME = 'Cancel'

    # (0 = stepper mode, 1 = stepper latency test mode, 2 = stepper reset mode,
    # 3 = auto mode, 4 = pressure sensor test mode)
    MODE = 3
    NUM_TEST_ITERATIONS = 1000
    NUM_DISPLAYED_DECIMAL_PLACES = 1  # Number of decimal places displayed of the current measurement in ms

    # URL to the server where .csv files of measurement data should get uploaded
    SERVER_URL = 'https://hci.ur.de/projects/latency/upload'

    TEXT_INPUT_MAX_CHARS = 64  # Max number of chars of the input fields

    GPIO_PIN_ID = 7  # ID of the GPIO Pin where the optocoupler is connected to the Raspberry Pi


class LatencyGUI(QtWidgets.QWizard):

    device_objects = []  # Temporary storage for info about all detected input devices
    device_id = -1  # ID of the currently connected device
    device_type = 2
    button_code = -1  # Code of the button that should be used for LagBox measurements
    device_name = ''  # Name of the device. Changeable by user
    vendor_id = ''  # Vendor ID of the device
    product_id = ''  # Product ID of the device
    ean_upc = ''  # EAN (European Article Number) / UPC (Universal Product code)
    device_speed = ''

    output_file_path = ''  # File path and name of the created .csv file
    stats = ''  # Stats about the data of the current measurement (Mean, Median, Min, Max, Standard Deviation)

    authors = ''  # Optional field for storing the names of the persons who conducted the current measurement
    publish_names = False  # Flag whether the names of the authors should get published
    email = ''  # Optional field for storing the email adress of the person who conducted the measurement
    additional_notes = ''  # Optional fields for storing additional notes about the current measurement

    # Flag if the system is currently scanning for key inputs (for determining the pressed button)
    scan_for_key_inputs = True
    is_measurement_running = False  # Is the LagBox measurement currently running?

    def __init__(self):
        super().__init__()
        self.reset_gpio_pins()
        self.init_ui()

    # Make sure that the GPIO pin where the raspberry Pi is connected to the optocoupler is set to LOW on startup
    # Otherwise this could cause unwanted button presses.
    def reset_gpio_pins(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(Constants.GPIO_PIN_ID, GPIO.OUT)
        GPIO.output(Constants.GPIO_PIN_ID, GPIO.LOW)

    def init_ui(self):
        self.ui = uic.loadUi(Constants.UI_FILE, self)
        self.setWindowTitle(Constants.WINDOW_TITLE)
        #self.showFullScreen()  # Disabled because UI does not scale properly on large screens

        # Set an eventFilter on the entire application to catch key inputs
        qApp.installEventFilter(self)

        # The "Back" button needs to be disabled for each page separately
        self.currentIdChanged.connect(self.disable_back)

        self.init_ui_page_one()
        self.show()

    # Disable the "Back Button" on all pages where it is not needed
    def disable_back(self):
        # Only show an back button on page 2 (ID 1)
        if QtWidgets.QWizard.currentId(self) is not 1:
            self.button(QtWidgets.QWizard.BackButton).hide()
        else:
            self.button(QtWidgets.QWizard.BackButton).show()

    # The eventFilter catches all events. Enter presses are prevented
    # https://wiki.qt.io/How_to_catch_enter_key
    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:  # Check for any KeyPress
            # Check if pressed button is the Enter button
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                # Allow Enter Button presses in the multiline textfield
                if not self.ui.plainTextEdit_additional_notes.hasFocus():
                    return True

        return super().eventFilter(obj, event)

    # User interface for page one (Page where general settings are placed)
    def init_ui_page_one(self):
        self.reset_all_data()
        self.button(QtWidgets.QWizard.BackButton).hide()

        self.ui.setButtonText(QtWidgets.QWizard.NextButton, Constants.BUTTON_NEXT_DEFAULT_NAME)
        self.ui.setButtonText(QtWidgets.QWizard.CancelButton, Constants.BUTTON_CANCEL_DEFAULT_NAME)
        self.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_two)
        self.ui.button_refresh.clicked.connect(self.get_connected_devices)
        self.ui.comboBox_device.currentIndexChanged.connect(self.on_combobox_device_changed)

        self.init_combobox_device_type(None)
        self.check_installed_modules()
        self.get_connected_devices()

    # Check if all necessary modules for visualizing the data are installed
    def check_installed_modules(self):
        try:
            import numpy as np
            from matplotlib import pyplot as plt
            import seaborn as sns
        except ImportError as e:
            print('Missing modules:', e)
            self.ui.label_hint_missing_modules.setText('Warning: Missing python modules - Visualisaztion of data will '
                                                       'not be possible. Please install numpy, matplotlib and seaborn.')

    # When conducting another measurement, all data should get reset
    def reset_all_data(self):
        self.device_objects = []
        self.device_id = -1
        self.device_type = 2
        self.button_code = -1
        self.device_name = ''
        self.vendor_id = ''
        self.product_id = ''
        self.device_speed = ''

        self.output_file_path = ''
        self.stats = ''

        self.authors = ''
        self.publish_names = False
        self.email = ''
        self.additional_notes = ''

        self.scan_for_key_inputs = True

        self.is_measurement_running = False

    # User interface for page two (Page where the detection of the input button takes place)
    def init_ui_page_two(self):
        self.validate_inputs()
        self.get_device_bInterval()

        self.ui.button_restart_measurement.clicked.connect(self.listen_for_key_inputs)
        try:
            self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_two)
        except TypeError:
            pass
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
        try:
            self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_three)
            self.ui.button(QtWidgets.QWizard.BackButton).clicked.disconnect(self.on_page_two_back_button_pressed)
        except TypeError:
            pass

        if not self.is_measurement_running:
            self.is_measurement_running = True
            self.ui.setButtonText(QtWidgets.QWizard.NextButton, Constants.BUTTON_NEXT_DEFAULT_NAME)
            self.button(QtWidgets.QWizard.NextButton).hide()

            command = '../bin/inputLatencyMeasureTool' + \
                      ' -m ' + str(Constants.MODE) + \
                      ' -tmin 100 -tmax 10000' + \
                      ' -b ' + str(self.button_code) + \
                      ' -d ' + str(self.device_type) + \
                      ' -event ' + str(self.device_id).replace('event', '') + \
                      ' -n ' + str(Constants.NUM_TEST_ITERATIONS) + \
                      " -name '" + self.device_name + "'"

            thread = LagBoxMeasurement(command)
            thread.start()
            thread.finished.connect(self.thread_finished)
            thread.display_progress.connect(self.display_progress)
            thread.logpath_arrived.connect(self.on_logpath_arrived)

    @pyqtSlot('QString', 'QString')
    def display_progress(self, line_id, line):
        self.ui.label_press_button_again.setText('')
        self.ui.progressBar.setValue((int(line_id) / Constants.NUM_TEST_ITERATIONS) * 100)
        self.ui.label_progress.setText(str(line_id) + '/' + str(Constants.NUM_TEST_ITERATIONS))
        measured_time = float(line.split(',')[2].replace("\\n'", ''))
        self.ui.label_last_measured_time.setText(
            str(round(measured_time, Constants.NUM_DISPLAYED_DECIMAL_PLACES)) + 'ms')

        if int(line_id) == Constants.NUM_TEST_ITERATIONS:
            self.ui.label_press_button_again.setText('Measurement finished. Analysing and saving data...')

    def thread_finished(self):
        print('Thread finished')

    @pyqtSlot('QString')
    def on_logpath_arrived(self, line):
        print('Logpath arrived')
        self.output_file_path = str(line).replace("b'", '').replace("\\n'", '')

        # TODO: Verify here if measurement was successful
        self.ui.button(QtWidgets.QWizard.NextButton).setEnabled(True)

        self.create_data_plot()

    # User interface for page four (Page that displays the results of the lagbox measurement)
    def init_ui_page_four(self):
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_five)

        # Path where the log will be saved
        self.ui.label_path_name.setText(os.path.dirname(os.path.realpath(__file__)).replace('gui', 'log'))
        self.ui.label_statistics.setText(self.stats)

        try:
            image = QPixmap(self.output_file_path.replace('.csv', '.png')).scaled(1000, 190, Qt.KeepAspectRatio)
            self.ui.label_image.setPixmap(image)
        except Exception as e:
            print('PLOT IMAGE NOT AVAILABLE!', e)

        # Save additional Metadata to csv log
        self.save_additional_information_to_csv(False)

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
        self.ui.setButtonText(QtWidgets.QWizard.NextButton, 'Waiting for network connection...')
        self.ui.button(QtWidgets.QWizard.NextButton).setEnabled(False)
        self.test_connection()

        self.ui.setButtonText(QtWidgets.QWizard.CancelButton, 'Cancel Upload and Exit')
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_seven)
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.on_page_seven_next_button_pressed)

        self.get_saved_name_email()

        timer_test_connection = QTimer(self)
        timer_test_connection.timeout.connect(self.test_connection)
        timer_test_connection.start(5000)

    # User interface for page eight (Page where The user is thanked for its participation)
    def init_ui_page_eight(self):
        self.button(QtWidgets.QWizard.NextButton).hide()
        self.button(QtWidgets.QWizard.CancelButton).hide()
        self.ui.setButtonText(QtWidgets.QWizard.CancelButton, 'Finish')

    # When pressing the back button on page two, we want to keep all previously stored information
    # But the text of the navigation buttons needs to be reverted.
    def on_page_two_back_button_pressed(self):
        self.scan_for_key_inputs = False
        self.ui.setButtonText(QtWidgets.QWizard.NextButton, Constants.BUTTON_NEXT_DEFAULT_NAME)

        try:
            self.ui.button(QtWidgets.QWizard.NextButton).clicked.disconnect(self.init_ui_page_three)
        except TypeError:
            pass
        self.ui.button(QtWidgets.QWizard.NextButton).clicked.connect(self.init_ui_page_two)

    def on_page_seven_next_button_pressed(self):
        self.save_additional_information_to_csv(True)

        if self.ui.checkBox_save_name_email_locally.isChecked():
            self.save_name_email_locally()

        self.init_ui_page_eight()

    # Before the user is allowed to upload the current measurement, we need to check if a network connection is
    # available
    def test_connection(self):
        print('Checking connection...')
        try:
            r = requests.get(Constants.SERVER_URL)
            r.raise_for_status()
            print('Connection test successful!')
            self.ui.button(QtWidgets.QWizard.NextButton).setEnabled(True)
            self.ui.setButtonText(QtWidgets.QWizard.NextButton, 'Upload Results')
        except:
            print('No connection possible...')
            self.ui.setButtonText(QtWidgets.QWizard.NextButton, 'Waiting for network connection...')
            self.ui.button(QtWidgets.QWizard.NextButton).setEnabled(False)

    # https://stackoverflow.com/questions/44907415/python-configparser-create-file-if-it-doesnt-exist
    def save_name_email_locally(self):
        print('Saving name and email in a local .ini file')
        config = configparser.ConfigParser()

        if not os.path.exists('config.ini'):
            config['upload'] = {'authors': os.environ['USER'], 'email': ''}
            config.write(open('config.ini', 'w'))

        config.read('config.ini')
        config['upload']['authors'] = self.ui.lineEdit_authors.text()
        config['upload']['email'] = self.ui.lineEdit_email.text()

        with open('config.ini', 'w') as configfile:
            config.write(configfile)

    # If an .ini file containing a saved name and email exists, this data will be used to prefill the UI elements
    def get_saved_name_email(self):
        if os.path.exists('config.ini'):
            config = configparser.ConfigParser()
            config.read('config.ini')
            if config.has_option('upload', 'authors') and config.has_option('upload', 'email'):
                self.ui.lineEdit_authors.setText(config['upload']['authors'])
                self.ui.lineEdit_email.setText(config['upload']['email'])
                return
        self.ui.lineEdit_authors.setText(os.environ['USER'])

    # Fills the combobox with all possible device types defined in the constants
    def init_combobox_device_type(self, auto_detected_value):
        self.ui.comboBox_device_type.clear()  # Empty the list

        if not (auto_detected_value is None):  # Check if an auto-detected value exists
            new_list = Constants.DEVICE_TYPES.copy()
            new_list.insert(0, auto_detected_value)
            self.ui.comboBox_device_type.addItems(new_list)
        else:
            self.ui.comboBox_device_type.addItems(Constants.DEVICE_TYPES)

    # Initialize the combobox with a list of devices handed over
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
                self.device_speed = device.device_speed

                break  # No need to continue after correct device is found

    # Detect the button a user pressed in order to get the ID of that button
    def listen_for_key_inputs(self):
        if self.ui.button_restart_measurement.isEnabled():
            self.ui.label_pressed_button_id.setText('')
            self.ui.button(QtWidgets.QWizard.NextButton).setEnabled(False)
            self.ui.button_restart_measurement.setText('Measuring...')
            self.ui.button_restart_measurement.setEnabled(False)

            self.scan_for_key_inputs = True
            thread_scan_key_inputs = threading.Thread(target=self.scan_key_inputs)
            thread_scan_key_inputs.start()

    def validate_inputs(self):
        self.device_name = self.ui.lineEdit_device_name.text()
        # TODO: Remove all non-allowed chars from device name
        self.device_type = Constants.DEVICE_TYPE_IDS[str(self.ui.comboBox_device_type.currentText()).replace(' (auto-detected)', '')]

        if len(self.device_name) > Constants.TEXT_INPUT_MAX_CHARS:
            self.device_name = self.device_name[:Constants.TEXT_INPUT_MAX_CHARS]

        print("Device name:", self.device_name)
        print("Device type ID:", self.device_type)

    # Get a list of all connected devices of the computer
    def get_connected_devices(self):
        self.device_objects = []  # Reset list
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
    def save_additional_information_to_csv(self, include_personal_information):
        print('Saving additional information to CSV')
        print('Path of csv file:', self.output_file_path)

        if include_personal_information:
            self.authors = self.ui.lineEdit_authors.text()
            self.publish_names = self.ui.checkBox_allow_name_publishing.isChecked()
            self.email = self.ui.lineEdit_email.text()
            self.additional_notes = self.ui.plainTextEdit_additional_notes.toPlainText()

            if len(self.authors) > Constants.TEXT_INPUT_MAX_CHARS:
                self.authors = self.authors[:Constants.TEXT_INPUT_MAX_CHARS]
            if len(self.email) > Constants.TEXT_INPUT_MAX_CHARS:
                self.email = self.email[:Constants.TEXT_INPUT_MAX_CHARS]

        # Update data in existing csv file:
        # https://stackoverflow.com/questions/14471049/python-2-7-1-how-to-open-edit-and-close-a-csv-file

        if include_personal_information:
            changes = {  # a dictionary of changes to make
                '#author:;': '#author:;' + self.authors,
                '#email:;': '#email:;' + self.email,
                '#public:;': '#public:;' + str(self.publish_names),
                '#notes:;': '#notes:;' + self.additional_notes.replace("\n", " ")
            }
        else:
            changes = {  # a dictionary of changes to make
                '#vendorId:;': '#vendorId:;' + self.vendor_id,
                '#productId:;': '#productId:;' + self.product_id,
                '#date:;': '#date:;' + datetime.today().strftime('%d-%m-%Y'),
                '#bInterval:;': '#bInterval:;' + str(self.get_device_bInterval()),
                '#deviceType:;': '#deviceType:;' + str(self.device_type),
                '#EAN:;': '#EAN:;' + self.ui.lineEdit_ean_upc.text()
                # '#deviceSpeed:;': '#deviceSpeed:;' + self.device_speed
            }

        new_rows = []  # a holder for our modified rows when we make them

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

        # Only upload if function is called by the specific UI Page
        if include_personal_information:
            print('Ready to upload measurement')
            self.upload_measurement()

    # Upload the newly created .csv file of the latest measurement
    def upload_measurement(self):
        files = {
            'bureaucracy[0]': (self.output_file_path, open(self.output_file_path, 'rb')),
            'bureaucracy[1]': (None, self.authors),
            'bureaucracy[2]': (None, self.email),
            'bureaucracy[3]': (None, str(self.publish_names is True)),  # Convert "True"/"False" to 1 or 0
            'bureaucracy[4]': (None, 'Comments'),
            'bureaucracy[$$id]': (None, '1'),  # ???
            'id': (None, 'projects:latency:upload')
        }

        try:
            response = requests.post('https://hci.ur.de/projects/latency/upload', files=files)
            print(response.status_code, response.reason)
        # https://stackoverflow.com/questions/16511337/correct-way-to-try-except-using-python-requests-module
        except requests.exceptions.HTTPError as errh:
            print("Http Error:", errh)
        except requests.exceptions.ConnectionError as errc:
            print("Error Connecting:", errc)
        except requests.exceptions.Timeout as errt:
            print("Timeout Error:", errt)
        except requests.exceptions.RequestException as err:
            print("Request Exception", err)

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

                # The fourth row of the device info (device[3]) contains the device id needed to request info about the
                # devices speed
                device_speed = self.get_device_speed(device[3])

                device_already_in_list = False
                for existing_device in self.device_objects:
                    if existing_device.name == name:
                        device_already_in_list = True

                # TODO: under cat /proc/bus/input/devices, a device sometimes appears multiple times.
                # Verify that there is no difference between two entries
                if not device_already_in_list:
                    device_names.append(name)
                    self.device_objects.append(Device(vendor_id, product_id, name, device_id, device_type_auto_detected,
                                                      device_speed))

        self.init_combobox_device(device_names)

    # Request the device speed of the current USB device
    def get_device_speed(self, device_data):
        device_information = device_data.split('/')[1:6]
        command = 'cat /sys/' + device_information[0] + '/' + device_information[1] + '/' + \
                  device_information[2] + '/' + device_information[3] + '/' + device_information[4] + '/speed'
        print(command)

        process = Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        device_speed = process.stdout.readline().decode("utf-8") + 'M'
        device_speed = device_speed.replace("\n", " ").replace(' ', '')
        print('Speed: ' + device_speed)

        return device_speed


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
        print('Starting Key Detection')
        try:
            device = evdev.InputDevice('/dev/input/' + str(self.device_id))

            while self.scan_for_key_inputs:
                event = device.read_one()  # Get current event
                if event is not None:
                    if event.type == evdev.ecodes.EV_KEY:  # Check if the current event is a button press
                        key_event = evdev.categorize(event)
                        if key_event.keystate:  # Check if button is pressed down
                            self.button_code = key_event.scancode
                            self.ui.label_pressed_button_id.setText(str(self.button_code))
                            self.ui.button_restart_measurement.setText('Restart Button Detection')
                            self.ui.button_restart_measurement.setEnabled(True)
                            self.ui.button(QtWidgets.QWizard.NextButton).setEnabled(True)
                            self.scan_for_key_inputs = False
                            return

        except PermissionError as error:
            print(error)  # TODO: Check if this error can happen on a Raspberry Pi

    def create_data_plot(self):
        self.dataplotter = DataPlotter.DataPlotter()
        self.stats = self.dataplotter.process_filedata(self.output_file_path)
        self.init_ui_page_four()
        self.ui.next()


class LagBoxMeasurement(QThread):

    display_progress = pyqtSignal('QString', 'QString')
    logpath_arrived = pyqtSignal('QString')
    command = ''

    def __init__(self, command):
        super().__init__()
        self.command = command

    # https://www.saltycrane.com/blog/2008/09/how-get-stdout-and-stderr-using-python-subprocess-module/
    def run(self):
        print(self.command)

        process = Popen(self.command, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)

        for line in iter(process.stdout.readline, ''):
            print(line)
            line_id = str(line).split(',')[0].replace("b'", '')  # Convert line to String and remove the leading "b'"
            if line_id.isdigit():  # Only count the progress if the line is actually the result of a measurement
                self.display_progress.emit(line_id, str(line))
            if 'done' in str(line):
                break
            elif 'cancelled' in str(line):
                sys.exit('Measurement failed')
            # At the end of the measurement, the filename and path of the created .csv file is returned.
            # We save that path
            elif '/log/' in str(line):
                self.logpath_arrived.emit(str(line))
            elif len(line) is 0:
                sys.exit('Found an empty line in stdout. This should not happen')


# An object representation of all relevant data about connected USB device
class Device:

    def __init__(self, vendor_id, product_id, name, device_id, device_type, device_speed):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.name = name
        self.device_id = device_id
        self.device_type = device_type
        self.device_speed = device_speed


def main():
    app = QtWidgets.QApplication(sys.argv)
    latencyGUI = LatencyGUI()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
