#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import numpy as np

# All Constants are placed in their own class to find them more easily
class Constants:
    CSV_DELIMITER = ';'
    PLOT_X_MIN = 0  # Minimum x value of the plot
    PLOT_X_MAX = 100  # Maximum x value of the plot
    PLOT_WIDTH = 9
    PLOT_HEIGHT = 2
    PLOT_OUTPUT_DPI = 300
    PLOT_FONTSIZE = 12


class Result:

    def __init__(self):
        self.name = ''
        self.minDelay = 100
        self.maxDelay = 10000
        self.iterations = 1000
        self.authors = ''
        self.vendorID = ''
        self.productID = ''
        self.date = ''
        self.bInterval = 1000
        self.deviceType = 'Mouse'
        self.mean = 0.0
        self.median = 0.0
        self.min = 0.0
        self.max = 0.0
        self.standardDeviation = 0.0


class DataPlotter:

    result = Result()

    # Reads in a csv file and hands the data over at the end
    def process_filedata(self, file_path):

        print(file_path)

        try:
            current_file = open(file_path, 'r').readlines()  # Open the csv File
        except:
            sys.exit("file missing: " + file_path)

        comment_lines = []  # All lines containing a comment (==> Metadata about the measurement)
        measurement_rows = []  # All lines containing actual measurement data

        for i in range(len(current_file)):
            if current_file[i][0] is '#':  # If row is a comment
                comment_lines.append(current_file[i])
            elif current_file[i] == 'counter;latency;delayTime\n':  # If row is header of measurements
                # Take all rows of the file starting by the first line after the header
                measurement_rows = current_file[i + 1:len(current_file)]
                break  # No need to continue the loop

        # print(comment_lines)
        # print(measurement_rows)

        # The csv file is now read in and relevant parts are extracted. Now the data needs to be processed further
        latencies = self.parse_measurements(measurement_rows)

        self.parse_comments(comment_lines)
        stats = self.get_stats_about_data(latencies)
        self.generate_plot(file_path, latencies)

        return stats

    # Parse the bare rows from the .csv file and extract only the relevant data
    def parse_measurements(self, measurement_rows):
        latencies = []

        for i in range(len(measurement_rows)):
            row_values = measurement_rows[i].split(Constants.CSV_DELIMITER)
            latencies.append(float(row_values[1]) / 1000)  # Divide by 1000 to get ms

        for i in range(len(latencies)):
            if latencies[i] > Constants.PLOT_X_MAX:  # Check if values will get clipped
                print("WARNING: One or more measured latencies exceed the defined limit of the plots x-axis and will "
                      "not be displayed!")
                break

        return latencies

    # Interpret the comment lines of the .csv file. They contain relevant metadata about the measurement
    def parse_comments(self, comment_lines):
        print("Comments:")
        for comment_line in comment_lines:
            key = comment_line.split(';')[0].replace('#', '')
            value = comment_line.split(';')[1]
            print(key, value)
            if key == "Device":
                self.result.name = value
            elif key == "minDelay":
                self.result.minDelay = value
            elif key == "maxDelay":
                self.result.maxDelay = value
            elif key == "iterations":
                self.result.iterations = value
            elif key == "":  # TODO: ADD ALL OTHER METADATA
                pass

    # Calculate mean, median, standard deviation, etc.
    def get_stats_about_data(self, latencies):
        mean = np.mean(latencies)
        median = np.median(latencies)
        minimum = min(latencies)
        maximum = max(latencies)
        standard_deviation = np.std(latencies)

        # TODO: Calculate additional stats (maybe ttest, ...)

        self.result.mean = mean
        self.result.median = median
        self.result.min = minimum
        self.result.max = maximum
        self.result.standardDeviation = standard_deviation

        return ('Mean: ' + str(round(mean, 3)) +
                ' Median: ' + str(round(median, 3)) +
                ' Minimum: ' + str(round(minimum, 3)) +
                '\nMaximum: ' + str(round(maximum, 3)) +
                ' Standard Deviation: ' + str(round(standard_deviation, 3)))

    # Generate a plot from the extracted latencies
    def generate_plot(self, file_path, latencies):
        try:
            print('Importing modules')
            from matplotlib import pyplot as plt
            import seaborn as sns
        except ImportError:
            print('Pyplot and/or Seaborn not installed')
            return

        plt.rcParams.update({'font.size': Constants.PLOT_FONTSIZE})
        plt.figure(figsize=[Constants.PLOT_WIDTH, Constants.PLOT_HEIGHT])

        # ax = sns.pointplot((values["latency"]), values["polling"], join=False, palette="dark", markers="D", scale=.75,
        # ci="sd", zorder=1, errwidth=0.5, capsize=.2, ax =axes)
        # ax = sns.swarmplot((values["latency"]), values["polling"], hue=None, palette="colorblind", size=1, dodge=True,
        # marker="H",orient="h", alpha=1, zorder=0)

        ax = sns.swarmplot(x=latencies, hue=None, palette="colorblind", marker="H", orient="h", alpha=1,
                           zorder=0)

        # plt.title("TEST")
        plt.xlabel("latency (ms)")
        plt.xlim(Constants.PLOT_X_MIN, Constants.PLOT_X_MAX)
        # plt.xlim(left=0)

        axes = plt.gca()

        plt.savefig(file_path.replace('.csv', '.png'), dpi=Constants.PLOT_OUTPUT_DPI, bbox_inches="tight")
        print("Plot created successfully")


def main():
    dataplotter = DataPlotter()
    sys.exit()


if __name__ == '__main__':
    main()
