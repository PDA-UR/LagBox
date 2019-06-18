#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import numpy as np


# All Constants are placed in their own class to find them more easily
class Constants:
    CSV_DELIMITER = ';'
    PLOT_X_MIN = 0  # Minimum x value of the plot
    # PLOT_X_MAX = 100  # Maximum x value of the plot
    PLOT_WIDTH = 9
    PLOT_HEIGHT = 2
    PLOT_OUTPUT_DPI = 300
    PLOT_FONTSIZE = 16


class DataPlotter:

    def __init__(self):
        # When starting the script, it is checked if the filename is passed over as an argument
        if len(sys.argv) > 1:
            file_path = sys.argv[1]
            print('Received filename argument:', file_path)
            self.process_filedata(file_path)

    # Reads in a csv file and hands the data over at the end
    def process_filedata(self, file_path):

        try:
            current_file = open(file_path, 'r').readlines()  # Open the csv File
        except:
            sys.exit("File missing: " + file_path)

        comment_lines = []  # All lines containing a comment (==> Metadata about the measurement)
        measurement_rows = []  # All lines containing actual measurement data

        for i in range(len(current_file)):
            if current_file[i][0] is '#':  # If row is a comment
                comment_lines.append(current_file[i])
            elif current_file[i] == 'counter;latency;delayTime\n':  # If row is header of measurements
                # Take all rows of the file starting by the first line after the header
                measurement_rows = current_file[i + 1:len(current_file)]
                break  # No need to continue the loop

        # The csv file is now read in and relevant parts are extracted. Now the data needs to be processed further
        latencies = self.parse_measurements(measurement_rows)
        stats = self.get_stats_about_data(latencies)
        self.generate_plot(file_path, latencies)

        return stats

    # Parse the bare rows from the .csv file and extract only the relevant data
    def parse_measurements(self, measurement_rows):
        latencies = []

        for i in range(len(measurement_rows)):
            row_values = measurement_rows[i].split(Constants.CSV_DELIMITER)
            latencies.append(float(row_values[1]) / 1000)  # Divide by 1000 to get ms

        # for i in range(len(latencies)):
        #     if latencies[i] > Constants.PLOT_X_MAX:  # Check if values will get clipped
        #         print("WARNING: One or more measured latencies exceed the defined limit of the plots x-axis and will "
        #               "not be displayed!")
        #         break

        return latencies

    # Calculate mean, median, standard deviation, etc.
    def get_stats_about_data(self, latencies):
        mean = np.mean(latencies)
        median = np.median(latencies)
        minimum = min(latencies)
        maximum = max(latencies)
        standard_deviation = np.std(latencies)

        # TODO: Calculate additional stats (maybe ttest, ...)

        return ('<b>Mean:</b> ' + str(round(mean, 3)) + 'ms ' +
                '<b>Median:</b> ' + str(round(median, 3)) + 'ms ' +
                '<b>Standard Deviation:</b> ' + str(round(standard_deviation, 3)) + 'ms' +
                '<br>' +
                '<b>Minimum:</b> ' + str(round(minimum, 3)) + 'ms ' +
                '<b>Maximum:</b> ' + str(round(maximum, 3)) + 'ms ')

    # Generate a plot from the extracted latencies
    def generate_plot(self, file_path, latencies):
        try:
            print('Importing modules')
            from matplotlib import pyplot as plt
            import seaborn as sns
        except ImportError:
            print('Pyplot and/or Seaborn not installed')
            return

        #plt.rcParams.update({'font.size': Constants.PLOT_FONTSIZE})
        plt.figure(figsize=[Constants.PLOT_WIDTH, Constants.PLOT_HEIGHT])
        sns.set(font_scale=1.5)

        # TODO: If we could guarantee here that at least seaborn version 0.9 is installed, we should add "dodge=True"
        ax = sns.swarmplot(x=latencies, hue=None, palette="colorblind", marker="H", orient="h", alpha=1, zorder=0)

        # plt.title("TEST")
        plt.xlabel("latency (ms)")
        #plt.xlim(Constants.PLOT_X_MIN, Constants.PLOT_X_MAX)
        plt.xlim(0, max(latencies) * 1.1)  # Leave 10% empty space on the right

        axes = plt.gca()

        plt.savefig(file_path.replace('.csv', '.png'), dpi=Constants.PLOT_OUTPUT_DPI, bbox_inches="tight")
        print("Plot created successfully")


def main():
    dataplotter = DataPlotter()
    sys.exit()


if __name__ == '__main__':
    main()
