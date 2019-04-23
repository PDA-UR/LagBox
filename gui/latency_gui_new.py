#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5 import QtWidgets, uic
import sys


class LatencyGUI(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        print("Hallo")
        self.initUI()

    def initUI(self):
        self.ui = uic.loadUi("latency_gui.ui", self)
        self.show()


def main():
    app = QtWidgets.QApplication(sys.argv)
    latencyGUI = LatencyGUI()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()